"""Cliente HTTP do backend NekoMind.

Regra: o frontend NUNCA acessa o banco diretamente - todo dado vem
da API do backend por este modulo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from streamlit import session_state as st_state

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def get_backend_url() -> str:
    if st_state.get("backend_url"):
        return st_state["backend_url"].rstrip("/")
    return DEFAULT_BACKEND_URL


def is_demo_mode() -> bool:
    status = effective_backend_status()
    return bool(status.get("is_demo"))


def effective_backend_status() -> dict:
    """Return backend-declared mode/provenance; never infer real/demo locally."""
    if "backend_health" in st_state and isinstance(st_state["backend_health"], dict):
        return classify_backend_health(st_state["backend_health"])
    return {"mode": "unknown", "is_demo": None, "label": "Modo desconhecido"}


def classify_backend_health(payload: dict | None) -> dict:
    payload = payload or {}
    mode = str(
        payload.get("mode") or payload.get("settings", {}).get("mode") or "unknown"
    )
    asr = payload.get("asr_provider") or payload.get("settings", {}).get("asr_provider")
    topic = (
        payload.get("llm_provider")
        or payload.get("topic_provider")
        or payload.get("settings", {}).get("llm_provider")
    )
    providers = {"asr_provider": asr, "topic_provider": topic}
    known = [provider for provider in providers.values() if provider]
    has_mock = any(provider == "mock" for provider in known)
    is_demo = (
        True
        if mode == "demo" or has_mock
        else False
        if mode == "real" and len(known) == 2
        else None
    )
    label = (
        "Demonstração"
        if is_demo is True
        else "Real"
        if is_demo is False
        else "Desconhecido"
    )
    return {"mode": mode, "is_demo": is_demo, "label": label, **providers}


def session_origin(session: dict) -> dict:
    asr = session.get("asr_provider_used")
    topic = session.get("topic_provider_used")
    known = [provider for provider in (asr, topic) if provider]
    is_demo = bool(
        session.get("is_demo") or any(provider == "mock" for provider in known)
    )
    unknown = len(known) != 2
    if is_demo:
        label = "Resultado de demonstração"
    elif unknown:
        label = "Origem desconhecida"
    else:
        label = "Resultado real"
    return {
        "label": label,
        "is_demo": is_demo,
        "unknown": unknown,
        "asr": asr,
        "topic": topic,
    }


def _client() -> httpx.Client:
    url = get_backend_url()
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
        or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('O historico aceita somente o backend local do Mac.')
    storage = Path(os.environ.get('NEKOMIND_STORAGE_DIR',
                   Path(__file__).resolve().parents[3] / 'backend' / 'storage' / 'audio'))
    token_path = storage.parent / 'operator-token'
    token = token_path.read_text().strip() if token_path.is_file() else ''
    return httpx.Client(base_url=url, timeout=20.0, trust_env=False,
                        follow_redirects=False, headers={'Authorization': f'Bearer {token}'})


def _request(method: str, path: str, **kwargs: Any) -> dict | list | None:
    with _client() as client:
        resp = client.request(method, path, **kwargs)
        if resp.status_code in (200, 201):
            return resp.json()
        resp.raise_for_status()
    return None


def health() -> dict:
    payload = _request("GET", "/health") or {}
    st_state["backend_health"] = payload
    return payload


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
    health()
    status = effective_backend_status()
    if status.get("is_demo") is not True:
        raise RuntimeError("Backend não confirmou modo demo; demonstração bloqueada.")
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
    result = finish_session(session_id) or {}
    if result.get("status") != "completed" or result.get("is_demo") is not True:
        raise RuntimeError("Backend não confirmou uma demonstração concluída.")
    return result
