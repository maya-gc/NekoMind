"""Loopback-only API client; audio never leaves this Mac."""

from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

try:
    from app.security import operator_token
except ImportError:  # pragma: no cover - compatibility with old backend packages
    operator_token = None


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
        headers = dict(kwargs.pop("headers", {}) or {})
        if operator_token is not None:
            headers.setdefault("Authorization", f"Bearer {operator_token()}")
        kwargs["headers"] = headers
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

    def create(self, rid, *, is_demo=False):
        capture_source = "synthetic" if is_demo else "mac_microphone"
        return self._request(
            "POST",
            "/api/v1/sessions",
            json={"request_id": rid, "title": "Sessao touch", "capture_source": capture_source},
        )

    def get(self, sid):
        return self._with_trend(self._request("GET", f"/api/v1/sessions/{sid}"))

    def _with_trend(self, row):
        if (
            row.get("status") != "completed"
            or not row.get("subject_confirmed")
            or not row.get("subject")
        ):
            return row
        method_version = str(row.get("metric_method_version") or "heuristic-v1")
        subject = quote(str(row["subject"]), safe="")
        try:
            history = self._request(
                "GET",
                f"/api/v1/history/subjects/{subject}",
                params={"method_version": method_version},
            )
        except Exception:  # noqa: BLE001 - trend is operator context, not capture state
            return row
        trend = history.get("trend") if isinstance(history, dict) else None
        if not isinstance(trend, dict):
            return row
        pieces = []
        labels = (
            ("duration_seconds_delta", "duracao", "s"),
            ("clarity_score_delta", "clareza", ""),
            ("topic_count_delta", "topicos", ""),
        )
        for key, label, suffix in labels:
            value = trend.get(key)
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            formatted = f"{numeric:+g}{suffix}"
            pieces.append(f"{label} {formatted}")
        if pieces:
            row["trend_text"] = "; ".join(pieces)[:120]
        return row

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

    def upload_manifest(self, sid, manifest):
        for chunk in manifest:
            with Path(chunk["path"]).open("rb") as stream:
                stream.seek(chunk["offset"])
                pcm = stream.read(chunk["byte_size"])
            self._request(
                "POST",
                f"/api/v1/sessions/{sid}/audio",
                files={"file": ("chunk.raw", pcm, "application/octet-stream")},
                data={
                    "sequence": str(chunk["sequence"]),
                    "sample_rate": "16000",
                    "audio_format": "pcm_s16le",
                },
            )

    def finish(self, sid, rid):
        return self._with_trend(
            self._request(
                "POST", f"/api/v1/sessions/{sid}/finish", json={"request_id": rid}, timeout=125
            )
        )

    def publish(self, snapshot):
        return self._request("POST", "/api/v1/experience/bridge", json=snapshot)

    def commands(self):
        return self._request("GET", "/api/v1/experience/commands")

    def ack_command(self, rid, response):
        return self._request(
            "POST", f"/api/v1/experience/commands/{rid}/ack", json={"response": response}
        )

    def readiness(self):
        return self._request("GET", "/api/v1/experience/providers")

    def recover(self, sid, action, rid):
        return self._request(
            "POST",
            f"/api/v1/sessions/{sid}/recover",
            json={"action": action, "request_id": rid},
        )

    def cancel(self, sid, *, confirmed=True):
        return self._request(
            "POST", f"/api/v1/sessions/{sid}/cancel", json={"confirmed": confirmed}
        )

    def delete(self, sid, confirmed=True):
        return self._request("DELETE", f"/api/v1/sessions/{sid}", json={"confirmed": confirmed})

    def close(self):
        self.client.close()
