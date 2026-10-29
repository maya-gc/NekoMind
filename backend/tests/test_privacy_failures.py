"""Privacy failure/retry/path isolation using only synthetic temporary data."""

import json
import sqlite3
from pathlib import Path

from app.config import get_settings


def stopped(client, rid):
    sid = client.post("/api/v1/sessions", json={"request_id": rid}).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/capture-state", json={"state": "error"})
    return sid


def test_partial_file_deletion_can_retry_without_reanalysis(client, monkeypatch):
    sid = stopped(client, "partial-delete")
    folder = get_settings().storage_dir / f"session_{sid}"
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / "partial.raw"
    raw.write_bytes(b"\x00\x00")
    original = Path.unlink

    def fail_target(path, *args, **kwargs):
        if path == raw:
            raise PermissionError("controlled")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_target)
        first = client.request("DELETE", f"/api/v1/sessions/{sid}", json={"confirmed": True})
    assert first.status_code == 409
    assert client.get(f"/api/v1/sessions/{sid}").json()["deletion_pending"] is True
    second = client.request("DELETE", f"/api/v1/sessions/{sid}", json={"confirmed": True})
    assert second.status_code == 200
    assert not raw.exists()
    assert client.get(f"/api/v1/sessions/{sid}").status_code == 404


def test_session_directory_symlink_never_deletes_external_file(client, tmp_path):
    sid = stopped(client, "symlink-delete")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("synthetic sentinel")
    link = get_settings().storage_dir / f"session_{sid}"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    response = client.request("DELETE", f"/api/v1/sessions/{sid}", json={"confirmed": True})
    assert response.status_code == 409
    assert sentinel.read_text() == "synthetic sentinel"


def test_complete_delete_scrubs_mac_journal_content_but_preserves_dedup(
    client, tmp_path, monkeypatch
):
    monkeypatch.setenv("NEKOMIND_MAC_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    sid = stopped(client, "journal-delete")
    journal = tmp_path / "journal.db"
    with sqlite3.connect(journal) as db:
        db.execute("CREATE TABLE requests (id TEXT PRIMARY KEY,payload TEXT,response TEXT)")
        db.execute(
            "CREATE TABLE active (id INTEGER PRIMARY KEY,session_id INTEGER,state TEXT,demo INTEGER,code TEXT)"
        )
        for rid, target in [("target", sid), ("other", sid + 1)]:
            db.execute(
                "INSERT INTO requests VALUES(?,?,?)",
                (
                    rid,
                    json.dumps({"session_id": target}),
                    json.dumps({"session_id": target, "topics": ["SYNTHETIC PRIVATE TOPIC"]}),
                ),
            )
        db.execute("INSERT INTO active VALUES(1,?,?,1,NULL)", (sid, "completed"))
    assert (
        client.request("DELETE", f"/api/v1/sessions/{sid}", json={"confirmed": True}).status_code
        == 200
    )
    with sqlite3.connect(journal) as db:
        target = db.execute("SELECT response FROM requests WHERE id=?", ("target",)).fetchone()
        other = db.execute("SELECT response FROM requests WHERE id=?", ("other",)).fetchone()
        assert (
            target is not None
        )  # retain only receipt tombstone, preventing accidental new capture
        assert "SYNTHETIC PRIVATE" not in target[0]
        assert "SYNTHETIC PRIVATE" in other[0]
        assert db.execute("SELECT session_id FROM active").fetchone()[0] is None


def test_discard_does_not_remove_pending_ack_receipt(client):
    from app.database.connection import SessionLocal
    from app.database.operations import OperatorCommand

    sid = stopped(client, "pending-delete")
    with SessionLocal() as db:
        db.add(
            OperatorCommand(
                request_id="discard-pending",
                payload=json.dumps(
                    {
                        "request_id": "discard-pending",
                        "command": "discard",
                        "session_id": sid,
                        "confirmed": True,
                    }
                ),
                status="pending",
            )
        )
        db.commit()
    assert (
        client.request("DELETE", f"/api/v1/sessions/{sid}", json={"confirmed": True}).status_code
        == 200
    )
    assert client.get("/api/v1/experience/commands/discard-pending").status_code == 200


def test_cleanup_failure_preserves_result_and_retry_only_removes_audio(client, monkeypatch):
    from app.services import session_lifecycle, topic_extraction

    sid = client.post("/api/v1/sessions", json={"request_id": "cleanup-completed"}).json()["id"]
    upload = client.post(
        f"/api/v1/sessions/{sid}/audio",
        files={"file": ("s.raw", b"\x00\x00" * 16000)},
        data={"sequence": "0", "audio_format": "pcm_s16le", "sample_rate": "16000"},
    )
    assert upload.status_code == 201

    def fail_cleanup(*_args):
        raise session_lifecycle.LifecycleRejectedError("controlled cleanup failure")

    with monkeypatch.context() as patch:
        patch.setattr(session_lifecycle, "remove_raw_audio_after_success", fail_cleanup)
        finished = client.post(
            f"/api/v1/sessions/{sid}/finish", json={"request_id": "finish-cleanup"}
        )
    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"
    assert finished.json()["error_code"] == "audio_cleanup_failed"
    assert len(finished.json()["metrics"]) == 6

    def forbidden(*_args, **_kwargs):
        raise AssertionError("cleanup retry must not analyze again")

    monkeypatch.setattr(topic_extraction, "extract_topics_result", forbidden)
    retry = client.post(
        f"/api/v1/sessions/{sid}/recover", json={"action": "analyze", "request_id": "cleanup-only"}
    )
    assert retry.status_code == 200
    assert retry.json()["error_code"] is None
    assert len(retry.json()["metrics"]) == 6
    assert not list((get_settings().storage_dir / f"session_{sid}").glob("*.raw"))


def test_deleted_start_request_is_rejected_by_http_without_new_capture(client):
    sid = stopped(client, "deleted-start-http")
    assert (
        client.request("DELETE", f"/api/v1/sessions/{sid}", json={"confirmed": True}).status_code
        == 200
    )
    replay = client.post("/api/v1/sessions", json={"request_id": "deleted-start-http"})
    assert replay.status_code == 410
    assert client.get("/api/v1/sessions").json() == []


def test_distinct_concurrent_starts_get_distinct_ids(client):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(
                lambda i: client.post("/api/v1/sessions", json={"request_id": f"parallel-{i}"}),
                range(16),
            )
        )
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 16
