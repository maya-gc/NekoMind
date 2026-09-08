"""Cliente HTTP do backend NekoMind.

Regra: o frontend NUNCA acessa o banco diretamente - todo dado vem
da API do backend por este modulo.
"""
from __future__ import annotations

from typing import Any

import httpx

from streamlit import session_state as st_state

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def get_backend_url() -> str:
    if "backend_url" in st_state and st_state["backend_url"]:
        return st_state["backend_url"].rstrip("/")
    return DEFAULT_BACKEND_URL


def is_demo_mode() -> bool:
    return bool(st_state.get("demo_mode", False))


def _client() -> httpx.Client:
    return httpx.Client(base_url=get_backend_url(), timeout=20.0)


def _request(method: str, path: str, **kwargs: Any) -> dict | list | None:
    with _client() as client:
        resp = client.request(method, path, **kwargs)
        if resp.status_code in (200, 201):
            return resp.json()
        resp.raise_for_status()
    return None


def health() -> dict:
    return _request("GET", "/health") or {}


def list_sessions(limit: int = 100) -> list[dict]:
    return _request("GET", "/api/v1/sessions", params={"limit": limit}) or []


def get_session(session_id: int) -> dict | None:
    return _request("GET", f"/api/v1/sessions/{session_id}")


def create_session(title: str | None = None) -> dict:
    payload = {"title": title} if title else {}
    return _request("POST", "/api/v1/sessions", json=payload) or {}


def finish_session(session_id: int) -> dict | None:
    return _request("POST", f"/api/v1/sessions/{session_id}/finish")


def dashboard_summary() -> dict:
    return _request("GET", "/api/v1/dashboard/summary") or {}


def demo_session() -> dict:
    """Cria e finaliza uma sessao de demonstracao no backend.

    Usado pelo modo demo do frontend para popular o dashboard com dados
    ficticios [DEMO] produzidos pelos adapters mock do backend.
    """
    created = create_session("Sessão de demonstração")
    session_id = int(created["id"])
    fake_pcm = b"\x00\x00" * 16000 * 2  # 2s de silencio
    with _client() as client:
        resp = client.post(
            f"/api/v1/sessions/{session_id}/audio",
            files={"file": ("chunk.raw", fake_pcm, "application/octet-stream")},
            data={"sequence": "0", "audio_format": "pcm_s16le", "sample_rate": "16000"},
        )
        resp.raise_for_status()
    return finish_session(session_id) or {}