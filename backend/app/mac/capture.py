"""Bounded PCM capture. PortAudio callback never blocks on disk or controller locks."""

from pathlib import Path
from queue import Full, Queue
from threading import Thread

MAX_BYTES = 16000 * 2 * 1800


class MacRecorder:
    def __init__(self, directory: Path, *, device=None, stream_factory=None):
        self.directory, self.device, self.factory = directory, device, stream_factory
        self.stream = None
        self.writer = None
        self.queue = None
        self.error = None
        self.path = None
        self.byte_count = 0
        self.paused = False

    def _callback(self, data, frames, time_info, status):
        if status:
            self.error = "capture_overflow"
            return
        self.byte_count += len(data)
        if self.byte_count > MAX_BYTES:
            self.error = "capture_limit"
            return
        try:
            self.queue.put_nowait(bytes(data))
        except Full:
            self.error = "capture_storage_slow"

    def _write(self, handle, capture_queue):
        try:
            with handle:
                while True:
                    data = capture_queue.get()
                    if data is None:
                        break
                    handle.write(data)
                handle.flush()
        except OSError:
            self.error = "capture_storage_failed"

    def _open_stream(self):
        if self.factory is None:
            import sounddevice

            self.factory = sounddevice.RawInputStream
        try:
            self.stream = self.factory(
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

    def start(self, sid):
        if self.writer is not None:
            raise RuntimeError("capture_already_active")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"capture_{sid}.raw"
        self.queue = Queue(maxsize=128)
        self.error, self.byte_count = None, 0
        handle = self.path.open("xb")
        self.writer = Thread(target=self._write, args=(handle, self.queue), daemon=True)
        self.writer.start()
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

    def abort(self):
        try:
            self._close_stream()
        except Exception:  # noqa: BLE001 - always close PortAudio and propagate failure
            self.error = "capture_close_failed"
        finally:
            self._close_writer()
