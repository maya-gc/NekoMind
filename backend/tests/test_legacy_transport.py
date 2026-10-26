from sqlalchemy import func, select

from app.database.connection import session_scope
from app.database.models import StudySession


def test_legacy_websocket_rejects_without_creating_session(client):
    with client.websocket_connect("/ws/device") as ws:
        ws.send_json({"type": "session_start", "title": "legacy"})
        message = ws.receive_json()
        assert message["type"] == "error"
        assert message["code"] == "legacy_transport_disabled"
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(StudySession)) == 0


def test_health_reports_effective_mode(client):
    assert client.get("/health").json()["mode"] == "demo"
