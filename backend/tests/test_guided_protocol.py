import pytest

from app.mac.protocol import encode_line, validate_result


def test_live_pulse_is_not_a_result_and_stale_pulse_cannot_replace_newer(client):
    content = client.post(
        "/api/v1/contents", json={"title": "Água", "text": "A chuva devolve agua aos rios."}
    ).json()
    sid = client.post(
        "/api/v1/sessions",
        json={"request_id": "pulse-start", "reference_content_id": content["id"]},
    ).json()["id"]
    pulse = {
        "status": "partial",
        "expression": "content",
        "coverage_percent": 20,
        "origin": "demo",
        "seq": 2,
    }
    base = {
        "session_id": sid,
        "state": "recording",
        "is_demo": True,
        "diagnostics": [],
        "content": pulse,
    }
    assert client.post("/api/v1/experience/bridge", json=base).status_code == 200
    public = client.get("/api/v1/experience/public").json()
    assert public["content"]["coverage_percent"] == 20
    assert public["result"] is None
    stale = {**base, "content": {**pulse, "seq": 1, "coverage_percent": 90}}
    assert client.post("/api/v1/experience/bridge", json=stale).status_code == 200
    assert client.get("/api/v1/experience/public").json()["content"]["coverage_percent"] == 20
    assert (
        client.post("/api/v1/experience/bridge", json={**base, "state": "completed"}).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/experience/bridge",
            json={**base, "content": {**pulse, "transcription": "private"}},
        ).status_code
        == 422
    )
    free_sid = client.post("/api/v1/sessions", json={"request_id": "free-pulse"}).json()["id"]
    assert (
        client.post("/api/v1/experience/bridge", json={**base, "session_id": free_sid}).status_code
        == 409
    )


def test_free_session_rejects_guided_live_frame(client):
    sid = client.post("/api/v1/sessions", json={"request_id": "free-live"}).json()["id"]
    payload = {
        "session_id": sid,
        "state": "recording",
        "is_demo": True,
        "content": {
            "status": "partial",
            "expression": "content",
            "coverage_percent": 20,
            "origin": "demo",
            "seq": 1,
        },
    }
    assert client.post("/api/v1/experience/bridge", json=payload).status_code == 422


def test_serial_live_frame_has_no_audio_or_transcript_and_is_bounded():
    frame = encode_line(
        {
            "v": 1,
            "type": "content",
            "request_id": "c2-example-4",
            "session_id": 12,
            "state": "recording",
            "is_demo": False,
            "origin": "real",
            "seq": 2,
            "coverage_percent": 30,
            "expression": "thinking",
            "status": "partial",
        }
    )
    assert len(frame) < 4096
    assert b"transcription" not in frame and b"audio" not in frame
    with pytest.raises(ValueError):
        validate_result({"type": "content", "session_id": 12, "status": "covered"}, 12)
    with pytest.raises(ValueError, match="invalid_content_report"):
        validate_result(
            {
                "id": 12,
                "status": "completed",
                "is_demo": False,
                "asr_provider": "faster_whisper",
                "topic_provider": "local_keywords",
                "transcription": "Fala validada",
                "topics": [],
                "reference_content_id": 5,
                "reference_version": 1,
                "content_report": {
                    "content_id": 6,
                    "content_version": 1,
                    "origin": "real",
                    "points": [],
                },
            },
            12,
        )
