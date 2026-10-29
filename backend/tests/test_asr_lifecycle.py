"""Lifecycle tests use a fake model; never import/download Whisper."""

import sys
import tempfile
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.adapters import asr_adapter as asr


class ASRLifecycleTests(unittest.TestCase):
    def setUp(self):
        if hasattr(asr, "clear_asr_cache"):
            asr.clear_asr_cache()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "audio.wav"
        self.path.write_bytes(b"test model input")
        self.models = []
        owner = self

        class Model:
            def __init__(self, *args, **kwargs):
                self.busy = False
                self.unloaded = False
                self.model = self
                owner.models.append(self)

            def transcribe(self, path, **kwargs):
                owner.assertEqual(kwargs["language"], "pt")

                def segments():
                    owner.assertFalse(self.busy, "generator use must be serialized")
                    self.busy = True
                    time.sleep(0.01)
                    yield types.SimpleNamespace(text=" explicação em português ")
                    self.busy = False

                return segments(), None

            def unload_model(self):
                owner.assertFalse(self.busy)
                self.unloaded = True

        self.factory = Model
        self.addCleanup(lambda: getattr(asr, "clear_asr_cache", lambda: None)())
        self.module = types.SimpleNamespace(WhisperModel=Model)
        self.patcher = patch.dict(sys.modules, faster_whisper=self.module)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_lazy_shared_across_adapters(self):
        first, second = asr.FasterWhisperAdapter(), asr.FasterWhisperAdapter()
        self.assertEqual(self.models, [])
        self.assertEqual(first.transcribe(self.path), "explicação em português")
        second.transcribe(self.path)
        self.assertEqual(len(self.models), 1)

    def test_concurrent_initialization_and_generator(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: asr.FasterWhisperAdapter().transcribe(self.path), range(6)))
        self.assertEqual(len(self.models), 1)

    def test_cache_configuration(self):
        for model, device, compute in [
            ("small", "cpu", "int8"),
            ("tiny", "cpu", "int8"),
            ("small", "auto", "int8"),
            ("small", "cpu", "float32"),
        ]:
            asr.FasterWhisperAdapter(model, device, compute).transcribe(self.path)
        self.assertEqual(len(self.models), 4)

    def test_failed_initialization_can_retry(self):
        self.module.WhisperModel = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("unavailable")
        )
        with self.assertRaises(RuntimeError):
            asr.FasterWhisperAdapter().transcribe(self.path)
        self.module.WhisperModel = self.factory
        asr.FasterWhisperAdapter().transcribe(self.path)
        self.assertEqual(len(self.models), 1)

    def test_clear_unloads_and_next_call_reloads(self):
        asr.FasterWhisperAdapter().transcribe(self.path)
        self.assertTrue(hasattr(asr, "clear_asr_cache"), "explicit lifecycle cleanup required")
        asr.clear_asr_cache()
        self.assertTrue(self.models[0].unloaded)
        asr.FasterWhisperAdapter().transcribe(self.path)
        self.assertEqual(len(self.models), 2)

    def test_mock_never_initializes_model(self):
        self.assertIn("[DEMO]", asr.get_asr_adapter("mock").transcribe(Path("absent")))
        self.assertEqual(self.models, [])

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            asr.get_asr_adapter("typo")

    def test_absent_file_rejected_before_model_load(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            asr.FasterWhisperAdapter().transcribe(Path(self.temp.name) / "absent")
        self.assertEqual(self.models, [])

    def test_empty_file_rejected_before_model_load(self):
        self.path.write_bytes(b"")
        with self.assertRaises(ValueError):
            asr.FasterWhisperAdapter().transcribe(self.path)
        self.assertEqual(self.models, [])

    def test_fastapi_lifespan_unloads_model(self):
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine, inspect

        from app.config import Settings
        from app.main import app

        settings = Settings(
            database_url=f"sqlite:///{self.temp.name}/lifecycle.db",
            storage_dir=Path(self.temp.name) / "storage" / "audio",
            mode="demo",
            asr_provider="mock",
            llm_provider="mock",
        )
        engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
        self.addCleanup(engine.dispose)
        with (
            patch("app.database.connection.engine", engine),
            patch("app.main.get_settings", return_value=settings),
            patch("app.security.get_settings", return_value=settings),
            TestClient(app),
        ):
            self.assertIn("study_sessions", inspect(engine).get_table_names())
            asr.FasterWhisperAdapter().transcribe(self.path)
            self.assertFalse(self.models[0].unloaded)
        self.assertTrue(self.models[0].unloaded)
