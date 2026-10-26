"""Local pt-BR speech on the Mac; synthesis never blocks touch or capture."""

import logging
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock

logger = logging.getLogger(__name__)


class KokoroSpeaker:
    """Keep Kokoro warm and play only the latest utterance through macOS."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.lock = RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nekomind-voice")
        self.pipeline = None
        self.playback = None
        self.future = None
        self.generation = 0
        self.closed = False

    def preload(self):
        """Fail at startup if the local model or the macOS player is unavailable."""
        if not Path("/usr/bin/afplay").is_file():
            raise RuntimeError("afplay indisponivel neste Mac")
        if shutil.which("espeak-ng") is None:
            raise RuntimeError("espeak-ng indisponivel neste Mac")
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
            with self.lock:
                if self.closed or generation != self.generation:
                    return
                self.playback = subprocess.Popen(
                    ["/usr/bin/afplay", str(path)],
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
