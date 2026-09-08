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

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as c:
        yield c
