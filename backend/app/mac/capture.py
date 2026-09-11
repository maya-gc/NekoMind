"""Bounded PCM capture. PortAudio callback never blocks on disk or controller locks."""

import json
import os
import time
import wave
from collections import deque
from pathlib import Path
from queue import Full, Queue
from threading import Thread

from app.services.audio_quality import assess_audio_quality

MAX_BYTES = 16000 * 2 * 1800
CONFIRMED_CHUNK_BYTES = 512 * 1024


class MacRecorder:
    def __init__(self, directory: Path, *, device=None, stream_factory=None, device_api=None):
        self.directory, self.device, self.factory = directory, device, stream_factory
        self.device_api = device_api
        self.stream = None
        self.writer = None
        self.queue = None
        self.error = None
        self.path = None
        self.byte_count = 0
        self.confirmed_bytes = 0
        self._written_bytes = 0
        self._confirmed_chunks = []
        self._voice = {"level": 0, "clipping": False, "quality": "unknown"}
        self._voice_window = deque(maxlen=8)
        self.paused = False
        self.calibration = self._load_calibration()

    def _callback(self, data, frames, time_info, status):
        if status:
            self.error = "capture_overflow"
            return
        self.byte_count += len(data)
        if self.byte_count > MAX_BYTES:
            self.error = "capture_limit"
            return
        peak = (
            max(
                abs(int.from_bytes(data[index : index + 2], "little", signed=True))
                for index in range(0, len(data) - 1, 2)
            )
            if data
            else 0
        )
        clipping = peak >= 32700
        level = min(100, round(peak / 32767 * 100))
        instant_quality = "unknown"
        if clipping:
            instant_quality = "clipping"
        elif 0 < level < 3:
            instant_quality = "low"
        elif level > 0:
            instant_quality = "ok"
        self._voice_window.append(instant_quality)
        quality = instant_quality
        if "clipping" in self._voice_window:
            quality = "clipping"
        elif sum(1 for item in self._voice_window if item == "low") >= 3:
            quality = "low"
        elif any(item == "ok" for item in self._voice_window):
            quality = "ok"
        self._voice = {
            "level": level,
            "clipping": clipping,
            "quality": quality,
        }
        try:
            self.queue.put_nowait(bytes(data))
        except Full:
            self.error = "capture_storage_slow"

    def voice(self):
        if self.writer is None or self.stream is None or self.paused:
            return None
        return dict(self._voice)

    def _manifest_path(self, sid):
        return self.directory / f"capture_{sid}.manifest.json"

    def _raw_path(self, sid):
        return self.directory / f"capture_{sid}.raw"

    def _calibration_path(self):
        return self.directory / "calibration.json"

    def _atomic_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _load_calibration(self):
        path = self._calibration_path()
        if not path.exists():
            return None
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def _save_calibration(self, payload):
        self.calibration = payload
        self._atomic_json(self._calibration_path(), payload)

    def _device_module(self):
        if self.device_api is not None:
            return self.device_api
        import sounddevice

        return sounddevice

    def _query_device(self):
        api = self._device_module()
        info = api.query_devices(self.device, "input")
        if not isinstance(info, dict):
            raise RuntimeError("capture_device_unavailable")  # noqa: TRY004
        return info

    def _device_id(self, info):
        name = str(info.get("name") or self.device or "default")
        hostapi = info.get("hostapi", "default")
        index = info.get("index", self.device if self.device is not None else "default")
        rate = int(float(info.get("default_samplerate") or 16000))
        return f"input:{hostapi}:{index}:{name}:{rate}"

    def _check_input_settings(self):
        api = self._device_module()
        api.check_input_settings(
            device=self.device,
            samplerate=16000,
            channels=1,
            dtype="int16",
        )

    def _stream_factory(self):
        if self.factory is not None:
            return self.factory
        return self._device_module().RawInputStream

    def _invalidate_calibration_if_device_changed(self):
        if not self.calibration:
            return
        try:
            device_id = self._device_id(self._query_device())
        except Exception:  # noqa: BLE001 - capture start will surface device failures
            return
        if self.calibration.get("device_id") != device_id:
            payload = {**self.calibration, "status": "error", "valid": False}
            payload["message"] = "Microfone mudou; refaca a calibracao."
            self._save_calibration(payload)

    def _manifest_payload(self):
        return {
            "version": 1,
            "chunk_bytes": CONFIRMED_CHUNK_BYTES,
            "path": str(self.path),
            "confirmed_bytes": self.confirmed_bytes,
            "chunks": self._confirmed_chunks,
        }

    def _persist_manifest(self):
        if self.path is None:
            return
        sid = self.path.stem.removeprefix("capture_")
        self._atomic_json(self._manifest_path(sid), self._manifest_payload())

    def _validate_manifest(self, sid, payload):
        if not isinstance(payload, dict) or payload.get("chunk_bytes") != CONFIRMED_CHUNK_BYTES:
            raise RuntimeError("capture_recovery_missing")
        chunks = payload.get("chunks", payload.get("confirmed_chunks"))
        if not isinstance(chunks, list):
            raise RuntimeError("capture_recovery_missing")  # noqa: TRY004
        expected_path = self._raw_path(sid)
        raw_path = Path(str(payload.get("path") or ""))
        if raw_path.resolve(strict=False) != expected_path.resolve(strict=False):
            raise RuntimeError("capture_recovery_missing")
        if raw_path.name != f"capture_{sid}.raw":
            raise RuntimeError("capture_recovery_missing")
        if raw_path.parent.resolve(strict=False) != self.directory.resolve(strict=False):
            raise RuntimeError("capture_recovery_missing")
        if raw_path.is_symlink():
            raise RuntimeError("capture_recovery_missing")
        expected_offset = 0
        validated = []
        for sequence, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                raise RuntimeError("capture_recovery_missing")  # noqa: TRY004
            if (
                chunk.get("sequence") != sequence
                or chunk.get("offset") != expected_offset
                or chunk.get("byte_size") != CONFIRMED_CHUNK_BYTES
                or Path(str(chunk.get("path") or "")).resolve(strict=False)
                != expected_path.resolve(strict=False)
            ):
                raise RuntimeError("capture_recovery_missing")
            validated.append(
                {
                    "sequence": sequence,
                    "offset": expected_offset,
                    "byte_size": CONFIRMED_CHUNK_BYTES,
                    "path": str(expected_path),
                }
            )
            expected_offset += CONFIRMED_CHUNK_BYTES
        if chunks and not expected_path.exists():
            raise RuntimeError("capture_recovery_missing")
        if expected_path.exists() and expected_path.stat().st_size < expected_offset:
            raise RuntimeError("capture_recovery_missing")
        return {
            "confirmed_bytes": expected_offset,
            "chunks": validated,
            "path": str(expected_path),
        }

    def recovery_manifest(self, sid):
        path = self._manifest_path(sid)
        if not path.exists():
            raw_path = self._raw_path(sid)
            return {"confirmed_bytes": 0, "chunks": [], "path": str(raw_path)}
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            raise RuntimeError("capture_recovery_missing") from exc
        return self._validate_manifest(sid, payload)

    def _confirm_boundaries(self, handle):
        while self._written_bytes - self.confirmed_bytes >= CONFIRMED_CHUNK_BYTES:
            handle.flush()
            os.fsync(handle.fileno())
            sequence = self.confirmed_bytes // CONFIRMED_CHUNK_BYTES
            self._confirmed_chunks.append(
                {
                    "sequence": sequence,
                    "offset": self.confirmed_bytes,
                    "byte_size": CONFIRMED_CHUNK_BYTES,
                    "path": str(self.path),
                }
            )
            self.confirmed_bytes += CONFIRMED_CHUNK_BYTES
            self._persist_manifest()

    def _write(self, handle, capture_queue):
        try:
            with handle:
                while True:
                    data = capture_queue.get()
                    if data is None:
                        break
                    handle.write(data)
                    self._written_bytes += len(data)
                    self._confirm_boundaries(handle)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            self.error = "capture_storage_failed"

    def _open_stream(self):
        try:
            factory = self._stream_factory()
            self.stream = factory(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=480,
                device=self.device,
                callback=self._callback,
            )
            self.stream.start()
            self.paused = False
            self.check()
        except Exception:
            self._close_stream()
            raise

    def _close_stream(self):
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    def _open_writer(self, mode):
        handle = self.path.open(mode)
        self.writer = Thread(target=self._write, args=(handle, self.queue), daemon=True)
        self.writer.start()

    def start(self, sid):
        if self.writer is not None:
            raise RuntimeError("capture_already_active")
        self._invalidate_calibration_if_device_changed()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"capture_{sid}.raw"
        self.queue = Queue(maxsize=128)
        self.error, self.byte_count = None, 0
        self.confirmed_bytes = self._written_bytes = 0
        self._confirmed_chunks = []
        self._voice = {"level": 0, "clipping": False, "quality": "unknown"}
        self._voice_window.clear()
        self._open_writer("xb")
        try:
            self._open_stream()
        except Exception:
            self.abort()
            raise

    def recover(self, sid, *, confirmed_bytes):
        if self.writer is not None:
            raise RuntimeError("capture_already_active")
        if confirmed_bytes < 0 or confirmed_bytes % CONFIRMED_CHUNK_BYTES:
            raise RuntimeError("capture_invalid_cursor")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self._raw_path(sid)
        durable_manifest = self.recovery_manifest(sid)
        durable_cursor = int(durable_manifest["confirmed_bytes"])
        if confirmed_bytes < durable_cursor:
            raise RuntimeError("capture_invalid_cursor")
        if not self.path.exists() or self.path.stat().st_size < confirmed_bytes:
            raise RuntimeError("capture_recovery_missing")
        with self.path.open("r+b") as handle:
            handle.truncate(confirmed_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        self.queue = Queue(maxsize=128)
        self.error, self.byte_count = None, confirmed_bytes
        self.confirmed_bytes = self._written_bytes = confirmed_bytes
        self._confirmed_chunks = [
            {
                "sequence": sequence,
                "offset": sequence * CONFIRMED_CHUNK_BYTES,
                "byte_size": CONFIRMED_CHUNK_BYTES,
                "path": str(self.path),
            }
            for sequence in range(confirmed_bytes // CONFIRMED_CHUNK_BYTES)
        ]
        self._voice = {"level": 0, "clipping": False, "quality": "unknown"}
        self._voice_window.clear()
        self._persist_manifest()
        self._open_writer("ab")
        try:
            self._open_stream()
        except Exception:
            self.abort()
            raise

    def pause(self):
        self.check()
        self._close_stream()
        self.paused = True

    def resume(self):
        self.check()
        if not self.paused:
            raise RuntimeError("capture_not_paused")
        self._open_stream()

    def check(self):
        if self.error:
            raise RuntimeError(self.error)
        if self.writer is not None and not self.writer.is_alive():
            raise RuntimeError("capture_writer_failed")
        if not self.paused and self.stream is not None and not self.stream.active:
            raise RuntimeError("capture_device_lost")

    def _close_writer(self):
        if self.writer is not None:
            writer = self.writer
            if writer.is_alive():
                try:
                    self.queue.put(None, timeout=2)
                except Full:
                    self.error = "capture_storage_slow"
                writer.join(timeout=5)
                if writer.is_alive():
                    self.error = "capture_storage_timeout"
            if not writer.is_alive():
                self.writer = None

    def finish(self):
        if self.writer is None:
            raise RuntimeError("capture_not_active")
        try:
            self._close_stream()
        finally:
            self._close_writer()
        if self.error:
            raise RuntimeError(self.error)
        return self.path

    def confirmed_chunks(self):
        return list(self._confirmed_chunks)

    def final_remainder(self):
        if self.path is None:
            return None
        remainder = self._written_bytes - self.confirmed_bytes
        if remainder <= 0:
            return None
        return {
            "sequence": self.confirmed_bytes // CONFIRMED_CHUNK_BYTES,
            "offset": self.confirmed_bytes,
            "byte_size": remainder,
            "path": str(self.path),
        }

    def abort(self):
        try:
            self._close_stream()
        except Exception:  # noqa: BLE001 - always close PortAudio and propagate failure
            self.error = "capture_close_failed"
        finally:
            self._close_writer()

    def probe(self):
        components = []
        device_id = None
        try:
            info = self._query_device()
            device_id = self._device_id(info)
            components.append(
                {
                    "component": "microphone",
                    "status": "ready",
                    "message": str(info.get("name") or "Input device available"),
                }
            )
        except Exception:  # noqa: BLE001 - diagnostic result must be serializable
            components.append(
                {
                    "component": "microphone",
                    "status": "error",
                    "message": "Input device unavailable",
                }
            )
        try:
            self._check_input_settings()
            components.append(
                {
                    "component": "permission",
                    "status": "ready",
                    "message": "Input settings accepted",
                }
            )
        except Exception:  # noqa: BLE001 - privacy/permission details are platform-specific
            components.append(
                {
                    "component": "permission",
                    "status": "error",
                    "message": "Microphone permission or settings rejected",
                }
            )
        captured = bytearray()

        def callback(data, frames, time_info, status):
            if not status:
                captured.extend(bytes(data))

        stream = None
        try:
            stream = self._stream_factory()(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=480,
                device=self.device,
                callback=callback,
            )
            stream.start()
            if self.factory is None:
                time.sleep(0.1)
            status = "ready" if captured else "error"
            components.append(
                {
                    "component": "capture",
                    "status": status,
                    "message": "Short input probe captured audio"
                    if captured
                    else "Short input probe captured no audio",
                }
            )
        except Exception:  # noqa: BLE001 - diagnostic result must not crash bridge
            components.append(
                {
                    "component": "capture",
                    "status": "error",
                    "message": "Short input probe failed",
                }
            )
        finally:
            if stream is not None:
                try:
                    stream.stop()
                finally:
                    stream.close()
        self._last_device_id = device_id
        return components

    def calibrate(self, *, duration_seconds=3.0, detector=None):
        components = self.probe()
        device_id = getattr(self, "_last_device_id", None)
        if any(item.get("status") == "error" for item in components):
            result = {
                "status": "error",
                "device_id": device_id,
                "quality": "unknown",
                "message": "Calibracao falhou no autoteste do microfone.",
                "duration_seconds": 0,
                "valid": False,
            }
            self._save_calibration(result)
            return result
        self.directory.mkdir(parents=True, exist_ok=True)
        captured = bytearray()

        def callback(data, frames, time_info, status):
            if not status and len(captured) < 16000 * 2 * max(duration_seconds, 0.1):
                captured.extend(bytes(data))

        stream = None
        raw_path = self.directory / "calibration_sample.raw"
        wav_path = self.directory / "calibration_sample.wav"
        started = time.monotonic()
        try:
            stream = self._stream_factory()(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=480,
                device=self.device,
                callback=callback,
            )
            stream.start()
            time.sleep(max(0.0, duration_seconds))
            pcm = bytes(captured)
            raw_path.write_bytes(pcm)
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(pcm)
            quality = assess_audio_quality(wav_path)["quality"] if pcm else "no_speech"
            if detector is None:
                try:
                    import webrtcvad
                except ImportError:
                    detector = None
                else:
                    detector = webrtcvad.Vad(2)
            voiced = 0
            if detector is not None:
                frame_size = 960
                voiced = sum(
                    bool(detector.is_speech(pcm[offset : offset + frame_size], 16000))
                    for offset in range(0, len(pcm) - frame_size + 1, frame_size)
                )
            if voiced <= 0 and quality in {"ok", "low"}:
                quality = "no_speech"
            valid = quality == "ok" and (detector is None or voiced > 0)
            result = {
                "status": "ready" if valid else "error",
                "device_id": device_id,
                "quality": quality,
                "message": "Calibracao concluida."
                if valid
                else "Calibracao sem fala valida; tente novamente.",
                "duration_seconds": round(time.monotonic() - started, 3),
                "valid": valid,
            }
            self._save_calibration(result)
            return result
        except Exception:  # noqa: BLE001 - calibration returns an operator-facing status
            result = {
                "status": "error",
                "device_id": device_id,
                "quality": "unknown",
                "message": "Calibracao falhou.",
                "duration_seconds": round(time.monotonic() - started, 3),
                "valid": False,
            }
            self._save_calibration(result)
            return result
        finally:
            if stream is not None:
                try:
                    stream.stop()
                finally:
                    stream.close()
            for path in (raw_path, wav_path):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
