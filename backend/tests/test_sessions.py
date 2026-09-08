"""Testes de criacao/persistencia de sessao no SQLite."""


def test_create_session_persists(client) -> None:
    resp = client.post("/api/v1/sessions", json={"title": "Fotossintese"})
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] > 0
    assert created["title"] == "Fotossintese"
    assert created["status"] == "recording"

    # Persistencia: a sessao aparece na listagem e no detalhe.
    listing = client.get("/api/v1/sessions").json()
    assert any(s["id"] == created["id"] for s in listing)

    detail = client.get(f"/api/v1/sessions/{created['id']}").json()
    assert detail["title"] == "Fotossintese"
    assert detail["topics"] == []
    assert detail["metrics"] == []


def test_get_session_not_found(client) -> None:
    assert client.get("/api/v1/sessions/999999").status_code == 404


def test_upload_audio_and_finish_generates_demo_metrics(client) -> None:
    session_id = client.post("/api/v1/sessions", json={}).json()["id"]

    # Envia um chunk PCM ficticio (2 segundos de silencio a 16 kHz/16 bits).
    fake_pcm = b"\x00\x00" * 16000 * 2
    files = {"file": ("chunk.raw", fake_pcm, "application/octet-stream")}
    data = {"sequence": "0", "audio_format": "pcm_s16le", "sample_rate": "16000"}
    resp = client.post(f"/api/v1/sessions/{session_id}/audio", files=files, data=data)
    assert resp.status_code == 201
    assert resp.json()["byte_size"] == len(fake_pcm)

    # Finaliza: pipeline mock deve gerar transcricao [DEMO] e metricas.
    detail = client.post(f"/api/v1/sessions/{session_id}/finish").json()
    assert detail["status"] == "completed"
    assert "[DEMO]" in (detail["transcription"] or "")
    assert detail["is_demo"] is True
    assert detail["duration_seconds"] > 0

    metric_names = {m["name"] for m in detail["metrics"]}
    assert {
        "duration_seconds",
        "word_count",
        "topic_count",
        "lexical_diversity",
        "topic_coverage",
        "clarity_score",
    } <= metric_names
    assert len(detail["topics"]) > 0

    # Dashboard reflete a sessao concluida.
    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["total_sessions"] >= 1
    assert summary["total_study_seconds"] > 0
