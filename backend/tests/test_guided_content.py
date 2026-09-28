import json

from app.database.connection import SessionLocal
from app.database.models import StudySession
from app.mac.__main__ import DemoRecorder
from app.mac.backend import LocalBackend
from app.mac.bridge import MacBridge
from app.services.content_matching import match_point, reference_synonyms, report


def test_content_crud_and_immutable_session_snapshot(client):
    payload = {
        "title": "Plantas",
        "text": "A luz permite fotossintese nas plantas.\n\nA agua participa da producao de glicose.",
    }
    created = client.post("/api/v1/contents", json=payload)
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert len(created.json()["points"]) == 2
    assert client.get("/api/v1/contents").json()[0]["id"] == cid
    sid = client.post(
        "/api/v1/sessions", json={"request_id": "guided-1", "reference_content_id": cid}
    ).json()["id"]
    updated = client.put(
        f"/api/v1/contents/{cid}", json={**payload, "text": "O oceano contem agua salgada."}
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert client.delete(f"/api/v1/contents/{cid}").status_code == 200
    with SessionLocal() as db:
        session = db.get(StudySession, sid)
        snapshot = json.loads(session.reference_snapshot_json)
        assert snapshot["version"] == 1
        assert "fotossintese" in snapshot["text"]
    assert (
        client.post(
            "/api/v1/sessions", json={"request_id": "guided-1", "reference_content_id": cid}
        ).status_code
        == 201
    )


def test_free_session_unchanged(client):
    row = client.post("/api/v1/sessions", json={"request_id": "free-1"}).json()
    assert row["reference_content_id"] is None
    assert row["content_report"] is None


def test_deleting_selected_library_item_returns_to_free_mode(client):
    item = client.post(
        "/api/v1/contents", json={"title": "Água", "text": "A chuva forma rios."}
    ).json()
    assert (
        client.put("/api/v1/experience/selection", json={"content_id": item["id"]}).status_code
        == 200
    )
    assert client.delete(f"/api/v1/contents/{item['id']}").status_code == 200
    assert client.get("/api/v1/experience/selection").json()["selected_content_id"] is None


def test_lexical_match_is_conservative_and_reproducible():
    point = "Plantas fazem fotossintese com luz solar e agua"
    assert match_point(point, "Eu prefiro a cor azul.").status == "not_mentioned"
    assert match_point(point, "").status == "not_mentioned"
    assert match_point(point, "eh... hm... barulho sem frase.").status == "not_mentioned"
    assert match_point(point, "Plantas usam luz solar.").status == "partial"
    a = report(
        {"id": 3, "version": 1, "points": [point]},
        "Plantas fazem fotossintese com luz solar e agua.",
        duration=9.0,
        is_demo=False,
    )
    assert a == report(
        {"id": 3, "version": 1, "points": [point]},
        "Plantas fazem fotossintese com luz solar e agua.",
        duration=9.0,
        is_demo=False,
    )
    assert a["coverage_percent"] == 100
    assert a["points"][0]["evidence"]
    assert (
        match_point("Plantas usam luz solar e agua", "Plantas não usam luz solar e agua.").status
        == "possible_divergence"
    )


def test_explicit_synonyms_stay_inside_reference():
    aliases = reference_synonyms("Evaporacao (vaporizacao) aquece a agua.")
    result = match_point("Evaporacao aquece a agua", "Vaporizacao aquece a agua.", synonyms=aliases)
    assert result.status == "covered"


def test_guided_demo_report_uses_final_transcription_once(client):
    content = client.post(
        "/api/v1/contents",
        json={"title": "Fotossintese", "text": "Plantas convertem luz e agua em glicose."},
    ).json()
    sid = client.post(
        "/api/v1/sessions",
        json={"request_id": "guided-finish", "reference_content_id": content["id"]},
    ).json()["id"]
    fake_pcm = b"\x00\x00" * 16000 * 2
    assert (
        client.post(
            f"/api/v1/sessions/{sid}/audio",
            files={"file": ("chunk.raw", fake_pcm, "application/octet-stream")},
            data={"sequence": "0", "audio_format": "pcm_s16le", "sample_rate": "16000"},
        ).status_code
        == 201
    )
    first = client.post(
        f"/api/v1/sessions/{sid}/finish", json={"request_id": "finish-guided"}
    ).json()
    second = client.post(
        f"/api/v1/sessions/{sid}/finish", json={"request_id": "finish-guided"}
    ).json()
    assert first["status"] == second["status"] == "completed"
    assert first["content_report"] == second["content_report"]
    assert first["content_report"]["origin"] == "demo"
    assert all(stage["origin"] == "demo" for stage in first["content_report"]["stages"].values())
    assert first["content_report"]["content_version"] == 1
    assert len(first["topics"]) == len(second["topics"])


def test_operator_selection_reaches_bridge_and_next_session(client, tmp_path):
    content = client.post(
        "/api/v1/contents",
        json={"title": "Plantas", "text": "Plantas fazem fotossintese com luz solar."},
    ).json()
    assert (
        client.put("/api/v1/experience/selection", json={"content_id": content["id"]}).status_code
        == 200
    )
    bridge = MacBridge(
        LocalBackend(client=client), DemoRecorder(tmp_path / "capture"), tmp_path / "journal.db"
    )
    try:
        bridge.mark_serial_connected()
        assert (
            bridge.handle(
                {
                    "v": 1,
                    "type": "command",
                    "request_id": "guided-diag",
                    "session_id": None,
                    "command": "diagnose",
                }
            )["state"]
            == "checking"
        )
        bridge.wait_for_operations()
        assert bridge.state == "ready"
        started = bridge.handle(
            {
                "v": 1,
                "type": "command",
                "request_id": "guided-start",
                "session_id": None,
                "command": "start",
            }
        )
        assert started["state"] == "recording"
        sid = started["session_id"]
        row = client.get(f"/api/v1/sessions/{sid}").json()
        assert row["reference_content_id"] == content["id"]
        assert row["reference_version"] == 1
        assert (
            client.put(
                "/api/v1/experience/selection", json={"content_id": content["id"]}
            ).status_code
            == 200
        )
        assert (
            client.put("/api/v1/experience/selection", json={"content_id": None}).status_code == 409
        )
    finally:
        bridge.close()
