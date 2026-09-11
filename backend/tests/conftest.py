"""Fixtures de teste: banco SQLite temporario e isolado por execucao.

As variaveis de ambiente precisam ser definidas ANTES de importar `app`,
pois `get_settings()` usa cache. O banco de producao nunca e tocado.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="nekomind_test_"))
os.environ["NEKOMIND_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["NEKOMIND_STORAGE_DIR"] = str(_TMP / "audio")

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database.connection import engine, migrate_sqlite_schema
from app.database.models import Base
from app.main import app
from app.security import operator_token


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch, tmp_path):
    # DB and files are both isolated. A fresh DB may reuse IDs between tests;
    # sharing the audio directory would attach an earlier test's files to them.
    monkeypatch.setenv("NEKOMIND_STORAGE_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("NEKOMIND_MAC_DATA_DIR", str(tmp_path / "mac"))
    monkeypatch.setenv("NEKOMIND_ASR_PROVIDER", "mock")
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "mock")
    monkeypatch.setenv("NEKOMIND_ASR_MODEL_SIZE", "small")
    monkeypatch.setenv("NEKOMIND_ASR_DEVICE", "cpu")
    monkeypatch.setenv("NEKOMIND_ASR_COMPUTE_TYPE", "int8")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    migrate_sqlite_schema(engine)
    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {operator_token()}"
        yield c
