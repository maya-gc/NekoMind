"""Loopback-only API client; audio never leaves this Mac."""

from pathlib import Path
from urllib.parse import urlsplit

import httpx


class LocalBackend:
    def __init__(self, url="http://127.0.0.1:8000", *, client=None):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("O bridge aceita somente backend HTTP em loopback")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("URL de backend invalida")
        self.client = client or httpx.Client(
            base_url=url, timeout=5, follow_redirects=False, trust_env=False
        )

    def _request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        if response.status_code not in {200, 201}:
            raise ValueError("Resposta HTTP inesperada")
        data = response.json()
        if not isinstance(data, dict):
            raise TypeError("Resposta de sessao invalida")
        # Wire protocol uses short names; API records the executed-stage names.
        data.setdefault("asr_provider", data.get("asr_provider_used"))
        data.setdefault("topic_provider", data.get("topic_provider_used"))
        return data

    def create(self, rid):
        return self._request(
            "POST",
            "/api/v1/sessions",
            json={"request_id": rid, "title": "Sessao touch", "capture_source": "mac_microphone"},
        )

    def get(self, sid):
        return self._request("GET", f"/api/v1/sessions/{sid}")

    def capture_state(self, sid, state, code=None):
        return self._request(
            "POST",
            f"/api/v1/sessions/{sid}/capture-state",
            json={"state": state, "error_code": code},
        )

    def upload(self, sid, path: Path):
        with path.open("rb") as stream:
            sequence = 0
            while pcm := stream.read(512 * 1024):
                self._request(
                    "POST",
                    f"/api/v1/sessions/{sid}/audio",
                    files={"file": ("chunk.raw", pcm, "application/octet-stream")},
                    data={
                        "sequence": str(sequence),
                        "sample_rate": "16000",
                        "audio_format": "pcm_s16le",
                    },
                )
                sequence += 1

    def finish(self, sid, rid):
        return self._request(
            "POST", f"/api/v1/sessions/{sid}/finish", json={"request_id": rid}, timeout=125
        )

    def close(self):
        self.client.close()
