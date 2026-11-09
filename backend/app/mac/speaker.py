"""Local pt-BR speech (macOS and Windows); synthesis never blocks touch or capture.

``KokoroSpeaker(play=False)`` keeps the rendered WAV files instead of playing
them, and ``SilentSpeaker`` only records the phrases: both serve automated
tests on machines without a loudspeaker.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from time import time

from app.platform_support import IS_MACOS, IS_WINDOWS, audio_player_available, audio_player_command

logger = logging.getLogger(__name__)


class KokoroSpeaker:
    """Keep Kokoro warm and play only the latest utterance (afplay or SoundPlayer)."""

    def __init__(self, directory: Path, *, play: bool = True):
        self.directory = directory
        self.play = play
        self.rendered = 0
        self.lock = RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nekomind-voice")
        self.pipeline = None
        self.playback = None
        self.future = None
        self.generation = 0
        self.closed = False

    def preload(self):
        """Fail at startup if the local model or the system player is unavailable."""
        if self.play and not audio_player_available():
            raise RuntimeError(
                "afplay indisponivel neste Mac" if IS_MACOS else "Player de audio indisponivel"
            )
        if IS_WINDOWS:
            # O instalador do eSpeak NG nem sempre poe a pasta no PATH; o
            # fonemizador do Kokoro aceita a DLL por variavel de ambiente.
            default = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "eSpeak NG"
            if (default / "libespeak-ng.dll").is_file():
                os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", str(default / "libespeak-ng.dll"))
                os.environ.setdefault("PHONEMIZER_ESPEAK_PATH", str(default / "espeak-ng.exe"))
                os.environ["PATH"] = f"{default}{os.pathsep}{os.environ.get('PATH', '')}"
        if shutil.which("espeak-ng") is None:
            raise RuntimeError("espeak-ng indisponivel neste computador")
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        import torch
        from huggingface_hub import hf_hub_download
        from kokoro import KModel, KPipeline

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        repo_id = "hexgrad/Kokoro-82M"

        def cached(filename):
            return hf_hub_download(repo_id=repo_id, filename=filename, local_files_only=True)

        model = KModel(
            repo_id=repo_id,
            config=cached("config.json"),
            model=cached(KModel.MODEL_NAMES[repo_id]),
        ).to(device).eval()
        pipeline = KPipeline(lang_code="p", device=device, model=model, repo_id=repo_id)
        pipeline.voices["pf_dora"] = pipeline.load_voice(cached("voices/pf_dora.pt"))
        self.pipeline = pipeline

    def speak(self, text: str):
        if self.pipeline is None:
            raise RuntimeError("Voz Kokoro nao foi carregada")
        phrase = " ".join(text.split())
        if not phrase or len(phrase) > 240:
            raise ValueError("Fala vazia ou longa demais")
        with self.lock:
            if self.closed:
                return
            self.generation += 1
            generation = self.generation
            self._stop_playback_locked()
            self.future = self.pool.submit(self._render_and_play, generation, phrase)

    def stop(self):
        with self.lock:
            self.generation += 1
            playback = self._stop_playback_locked()
        if playback is not None:
            try:
                playback.wait(timeout=1)
            except subprocess.TimeoutExpired:
                playback.kill()
                playback.wait(timeout=1)

    def _stop_playback_locked(self):
        playback = self.playback
        if playback is not None and playback.poll() is None:
            try:
                playback.terminate()
            except ProcessLookupError:
                pass
            return playback
        return None

    def _render_and_play(self, generation: int, phrase: str):
        path = None
        try:
            with self.lock:
                if self.closed or generation != self.generation:
                    return
            import numpy as np
            import soundfile as sf

            chunks = []
            for _, _, audio in self.pipeline(phrase, voice="pf_dora", speed=1.0):
                with self.lock:
                    if self.closed or generation != self.generation:
                        return
                if hasattr(audio, "detach"):
                    audio = audio.detach().cpu().numpy()
                chunks.append(np.asarray(audio))
            if not chunks:
                raise RuntimeError("Kokoro nao gerou audio")
            with self.lock:
                if self.closed or generation != self.generation:
                    return
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix="nekomind-", suffix=".wav", dir=self.directory, delete=False
            ) as handle:
                path = Path(handle.name)
            sf.write(path, np.concatenate(chunks), 24000, subtype="PCM_16")
            if not self.play:
                self.rendered += 1
                path.replace(self.directory / f"fala-{self.rendered:03d}.wav")
                path = None
                return
            with self.lock:
                if self.closed or generation != self.generation:
                    return
                self.playback = subprocess.Popen(
                    audio_player_command(path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                playback = self.playback
            returncode = playback.wait()
            with self.lock:
                if self.playback is playback:
                    self.playback = None
                interrupted = self.closed or generation != self.generation
            if returncode != 0 and not interrupted:
                raise RuntimeError(f"afplay encerrou com codigo {returncode}")
        except Exception:  # optional voice must never stop capture
            logger.warning("Falha na sintese ou reproducao local da voz.", exc_info=True)
        finally:
            if path is not None:
                path.unlink(missing_ok=True)

    def close(self):
        with self.lock:
            self.closed = True
            self.generation += 1
            playback = self._stop_playback_locked()
        if playback is not None:
            try:
                playback.wait(timeout=1)
            except subprocess.TimeoutExpired:
                playback.kill()
                playback.wait(timeout=1)
        self.pool.shutdown(wait=True, cancel_futures=True)


class SilentSpeaker:
    """Speaker for automated tests: records each phrase, never plays audio."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log_path = self.directory / "falas.jsonl"
        self.lock = RLock()
        self.spoken: list[str] = []
        self.stops = 0

    def preload(self):
        return None

    def speak(self, text: str):
        phrase = " ".join(text.split())
        if not phrase or len(phrase) > 240:
            raise ValueError("Fala vazia ou longa demais")
        with self.lock:
            self.spoken.append(phrase)
            with self.log_path.open("a", encoding="utf-8") as out:
                out.write(json.dumps({"t": round(time(), 3), "fala": phrase}, ensure_ascii=False))
                out.write("\n")

    def stop(self):
        with self.lock:
            self.stops += 1

    def close(self):
        return None
