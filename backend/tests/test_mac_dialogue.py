"""Guided touch mission, requested hint, spoken follow-up and compared answer."""

from app.config import get_settings
from app.mac.backend import LocalBackend
from app.mac.bridge import MacBridge
from app.mac.dialogue import (
    choose_focus,
    comparison_for,
    hint_for,
    mission_previews,
    question_for,
)
from app.mac.protocol import encode_line
from app.services.transcription import TranscriptionResult
from tests.test_mac_bridge import Recorder, command


class Speaker:
    def __init__(self):
        self.lines = []
        self.stops = 0

    def speak(self, text):
        self.lines.append(text)

    def stop(self):
        self.stops += 1

    def close(self):
        pass


def test_guided_mission_hint_second_answer_and_restart(client, tmp_path, monkeypatch):
    from app.services import audio_processing, transcription

    monkeypatch.setenv("NEKOMIND_MODE", "real")
    monkeypatch.setenv("NEKOMIND_ASR_PROVIDER", "faster_whisper")
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")
    monkeypatch.setenv("NEKOMIND_GUIDED_LIVE_ENABLED", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(audio_processing, "validate_speech", lambda path: {"speech_seconds": 1})
    spoken = iter(
        [
            "A água evapora com o calor e forma vapor.",
            "Quando o vapor esfria, ele se condensa e forma gotinhas de água.",
        ]
    )
    monkeypatch.setattr(
        transcription,
        "transcribe_audio_result",
        lambda path, **kwargs: TranscriptionResult(next(spoken), "faster_whisper", False),
    )
    content = client.post(
        "/api/v1/contents",
        json={
            "title": "Ciclo da água",
            "text": "O vapor esfria e se condensa em gotas de água.\nA água evapora com o calor e forma vapor.",
            "points": [
                "O vapor esfria e se condensa em gotas de água.",
                "A água evapora com o calor e forma vapor.",
            ],
        },
    ).json()
    assert client.put(
        "/api/v1/experience/selection", json={"content_id": content["id"]}
    ).status_code == 200

    backend = LocalBackend(client=client)
    speaker = Speaker()
    journal = tmp_path / "journal.db"
    bridge = MacBridge(backend, Recorder(tmp_path / "capture.raw"), journal, speaker=speaker)
    bridge.state = "ready"
    bridge.diagnostics = [{"component": "test", "status": "ready", "message": "ok"}]
    bridge._set_missions(*bridge._fetch_missions())
    ready = bridge.handle(command("status", "ready"))
    assert len(ready["missions"]) == 2

    start = command("start", "mission-start")
    start["mission_index"] = 0
    first_sid = bridge.handle(start)["session_id"]
    assert bridge.interaction["mission_index"] == 0
    bridge.handle(command("finish", "first-finish", first_sid))
    bridge.wait_for_analysis()
    # The analysis row may finish before the Mac publishes its question.
    assert backend.publish(
        {"session_id": first_sid, "state": "processing", "is_demo": False}
    )["accepted"] is True
    waiting = client.get("/api/v1/experience/public").json()
    assert waiting["state"] == "processing"
    assert waiting["result"] is None
    first = bridge.handle(command("status", "first-result", first_sid))
    assert first["followup"]["stage"] == "question"
    assert first["followup"]["point_index"] == 0
    assert "vapor" in first["followup"]["question"]
    assert speaker.lines[-1] == first["followup"]["question"]
    assert backend.publish(bridge._ops_snapshot())["accepted"] is True
    published_question = client.get("/api/v1/experience/public").json()
    assert published_question["state"] == "completed"
    assert published_question["followup"]["stage"] == "question"
    invalid_after_question = bridge.handle(command("pause", "bad-question", first_sid))
    assert invalid_after_question["type"] == "error"
    assert "followup" not in invalid_after_question

    hinted = bridge.handle(command("hint", "ask-hint", first_sid))
    assert hinted["state"] == "completed"
    assert hinted["followup"]["stage"] == "hint"
    assert hinted["followup"]["hint"].startswith("Dica:")
    assert speaker.lines[-1] == hinted["followup"]["hint"]

    second_sid = bridge.handle(command("answer", "answer", first_sid))["session_id"]
    assert second_sid != first_sid and speaker.stops > 0
    bridge.handle(command("finish", "second-finish", second_sid))
    bridge.wait_for_analysis()
    second = bridge.handle(command("status", "second-result", second_sid))
    assert second["followup"]["stage"] == "done"
    assert "Agora:" in second["followup"]["comparison"]
    assert "Antes" in second["followup"]["comparison"]
    assert speaker.lines[-1] == second["followup"]["comparison"]
    assert "source_point" not in second["followup"]  # firmware keeps its strict wire schema
    assert backend.publish(bridge._ops_snapshot())["accepted"] is True
    public = client.get("/api/v1/experience/public").json()["followup"]
    assert public["source_point"] == bridge.interaction["focus_point"]
    assert "água evapora" in public["first_excerpt"].lower()
    assert "vapor esfria" in public["second_excerpt"].lower()
    bridge.close()

    reopened = MacBridge(backend, Recorder(tmp_path / "capture.raw"), journal)
    restored = reopened.handle(command("status", "restored", second_sid))
    assert restored["followup"] == second["followup"]
    reopened.state = "ready"
    reopened.diagnostics = [{"component": "test", "status": "ready", "message": "ok"}]
    reopened._set_missions(*reopened._fetch_missions())
    reopened._save_active()
    assert backend.publish(reopened._ops_snapshot())["accepted"] is True
    ready_again = client.get("/api/v1/experience/public").json()
    assert ready_again["state"] == "ready"
    assert ready_again["missions"] == mission_previews(content["points"])
    assert ready_again["followup"] is None
    assert ready_again["result"] is None
    assert ready_again["journey"] == []
    invalid_while_ready = reopened.handle(command("hint", "bad-ready", second_sid))
    assert invalid_while_ready["type"] == "error"
    assert "missions" not in invalid_while_ready

    queued = client.post(
        "/api/v1/experience/commands",
        json={
            "request_id": "new-visitor",
            "session_id": second_sid,
            "command": "start",
            "mission_index": 0,
        },
    )
    assert queued.status_code == 200
    wire = next(
        cmd for cmd in backend.commands()["commands"] if cmd["request_id"] == "new-visitor"
    )
    assert wire["mission_index"] == 0
    assert reopened.handle(wire)["state"] == "recording"
    reopened.close()


def test_all_prepared_mission_previews_fit_serial_frame():
    points = [('"Água" e vapor com calor ' * 20) for _ in range(30)]
    message = {
        "v": 1,
        "type": "state",
        "request_id": "ready",
        "session_id": None,
        "state": "ready",
        "is_demo": False,
        "missions": mission_previews(points),
    }
    assert len(encode_line(message)) <= 4096


def test_spoken_prompts_fit_the_lcd_card_without_cutting_words():
    point = "Água, condensação e temperatura " * 20
    assert len(question_for(point).encode("utf-8")) < 96
    assert len(hint_for(point).encode("utf-8")) < 96
    assert question_for(point) == "Explique a ideia central desta missão com suas palavras."
    assert question_for("O Sol aquece a água.").endswith("água?")
    for first in ("not_mentioned", "partial", "covered", "possible_divergence"):
        for second in ("not_mentioned", "partial", "covered", "possible_divergence"):
            assert len(comparison_for(point, first, second).encode("utf-8")) < 96


def test_comparison_uses_source_and_speech_without_claiming_correctness():
    water = "O Sol aquece a água, que evapora e vira vapor."
    result = comparison_for(
        water, "not_mentioned", "covered", "",
        "O sol aquece a água, ela evapora e vira vapor.",
    )
    assert "Sol aquece a água" in result
    assert "Antes" in result
    assert len(result.encode("utf-8")) < 96
    assert "acert" not in result.lower()

    quantum = (
        "Na mecânica quântica, a função de onda descreve amplitudes de probabilidade "
        "e a medição segue a regra de Born."
    )
    result = comparison_for(
        quantum, "partial", "covered", "A função de onda descreve o sistema.",
        "A função de onda descreve amplitudes de probabilidade e segue a regra de Born.",
    )
    assert "probabilidade" in result or "Born" in result
    assert len(result.encode("utf-8")) < 96

    shorter = comparison_for(
        water, "covered", "partial", "O Sol aquece a água, que evapora e vira vapor.",
        "O Sol aquece a água.",
    )
    assert "Na segunda, faltou" in shorter
    assert "vapor" in shorter


def test_question_stays_on_the_selected_mission_even_when_another_point_is_weaker():
    report = {"points": [
        {"point": "O Sol aquece a água.", "status": "not_mentioned"},
        {"point": "O vapor se condensa.", "status": "covered"},
    ]}
    assert choose_focus(report, preferred_index=1) == (1, "O vapor se condensa.")
