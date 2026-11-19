from app.mac.mission_exercises import (
    addition_comparison,
    addition_feedback,
    mission_feedback,
    mission_verdict,
    prepare_questions,
)


def test_math_mission_asks_before_capture_and_guides_the_answer(monkeypatch):
    monkeypatch.setattr(
        "app.mac.mission_exercises.ask_questions",
        lambda *args: ["Quantas maçãs tem aqui?", "Quanto é 2 mais 3? Como sabe?"],
    )
    missions = prepare_questions("Matemática básica", "Conte até cinco.", [], "local")
    assert missions[0] == "Quanto é 1 mais 2 mais 2? Como sabe?"
    assert missions[1:] == ["Quanto é 2 mais 3? Como sabe?"]
    assert addition_feedback(missions[0], "Eu acho que dá quatro.").assessment == "equivoco"
    assert addition_feedback(missions[0], "Dá cinco, eu somei um e dois.").assessment == "parcial"
    assert addition_feedback(missions[0], "Eu somei um mais dois e depois dois.").assessment == ""
    assert addition_comparison(missions[0], "Dá quatro.", "Agora deu cinco.") == (
        "Agora a soma chegou a 5."
    )


def test_subject_title_is_enough_to_generate_a_relevant_question(monkeypatch):
    monkeypatch.setattr(
        "app.mac.mission_exercises.ask_questions",
        lambda *args: ["Público infantil?", "Como a água vira vapor?", "Como a água vira vapor?"],
    )
    assert prepare_questions("Ciclo da água", "", [], "local") == ["Como a água vira vapor?"]


def test_bridge_serves_question_then_compares_two_transcribed_answers(client, tmp_path, monkeypatch):
    from app.config import get_settings
    from app.mac.backend import LocalBackend
    from app.mac.bridge import MacBridge
    from app.services import audio_processing, transcription
    from app.services.transcription import TranscriptionResult
    from tests.test_mac_bridge import Recorder, command

    monkeypatch.setenv("NEKOMIND_MODE", "real")
    monkeypatch.setenv("NEKOMIND_ASR_PROVIDER", "faster_whisper")
    monkeypatch.setenv("NEKOMIND_LLM_PROVIDER", "local_keywords")
    monkeypatch.setenv("NEKOMIND_GUIDED_LIVE_ENABLED", "false")
    monkeypatch.setenv("NEKOMIND_TUTOR_PROVIDER", "regras")
    get_settings.cache_clear()
    calls = []

    def generate(*args):
        calls.append(args)
        return ["Quanto é 2 mais 2? Como sabe?"]

    monkeypatch.setattr("app.mac.mission_exercises.ask_questions", generate)
    monkeypatch.setattr(audio_processing, "validate_speech", lambda path: {"speech_seconds": 1})
    spoken = iter(["Acho que dá quatro.", "Agora deu cinco."])
    monkeypatch.setattr(
        transcription, "transcribe_audio_result",
        lambda path, **kwargs: TranscriptionResult(next(spoken), "faster_whisper", False),
    )
    content = client.post(
        "/api/v1/contents", json={"title": "Matemática básica", "text": "Matemática básica"},
    ).json()
    assert client.put("/api/v1/experience/selection", json={"content_id": content["id"]}).is_success

    class RealRecorder(Recorder):
        is_demo = False

    bridge = MacBridge(
        LocalBackend(client=client), RealRecorder(tmp_path / "capture.raw"), tmp_path / "journal.db",
    )
    try:
        bridge.state = "ready"
        bridge.diagnostics = [{"component": "test", "status": "ready", "message": "ok"}]
        bridge._set_missions(*bridge._fetch_missions(prepare=True))
        ready = bridge.handle(command("status", "ready"))
        assert ready["missions"][0] == "Quanto é 1 mais 2 mais 2? Como sabe?"
        first = bridge.handle({**command("start", "first"), "mission_index": 0})["session_id"]
        assert len(calls) == 1
        bridge.handle(command("finish", "finish-first", first))
        bridge.wait_for_analysis()
        question = bridge.handle(command("status", "read-feedback", first))["followup"]
        assert question["question"] == "Como você pode somar em duas partes?"
        hint = bridge.handle(command("hint", "ask-hint", first))["followup"]
        assert hint["hint"] == "Some 1 e 2. Depois some 2."
        second = bridge.handle(command("answer", "answer", first))["session_id"]
        bridge.handle(command("finish", "finish-second", second))
        bridge.wait_for_analysis()
        result = bridge.handle(command("status", "read-comparison", second))["followup"]
        assert result["comparison"] == "Agora a soma chegou a 5."
        bridge.state = "error"
        assert bridge._ops_snapshot()["followup"] is None
    finally:
        bridge.close()


def test_explanation_by_grouping_objects_is_correct():
    from app.mac.mission_exercises import FIRST_ADDITION

    first = "Um lápis mais dois lápis é igual a três lápis, mais dois lápis é igual a cinco."
    second = "Eu juntei dois mais dois, deu quatro. Mais um dá cinco."
    assert addition_feedback(FIRST_ADDITION, first).assessment == "correto"
    assert addition_feedback(FIRST_ADDITION, second).assessment == "correto"
    assert "lápis" in addition_comparison(FIRST_ADDITION, first, first)


def test_unclear_audio_does_not_override_an_explained_total():
    from app.mac.mission_exercises import FIRST_ADDITION

    first = "1 mais 2 é 3, mais 2 é 5."
    assert addition_feedback(FIRST_ADDITION, first).assessment == "correto"
    assert addition_feedback(FIRST_ADDITION, "Eu falei lápis.").assessment == ""
    assert addition_feedback(FIRST_ADDITION, "Não dá cinco.").assessment == ""
    assert addition_feedback(FIRST_ADDITION, "1 mais 2 é 4, mais 2 é 5.").assessment == "equivoco"


def test_explanation_in_pairs_can_be_correct_without_echoing_the_question():
    from app.mac.mission_exercises import FIRST_ADDITION

    first = "Eu tinha um lápis. Cada um dos meus dois colegas me deu um par. No fim contei cinco."
    second = "Comecei com o meu lápis e juntei os dois pares que ganhei, por isso fiquei com cinco."
    assert addition_feedback(FIRST_ADDITION, first).assessment == "correto"
    assert addition_feedback(FIRST_ADDITION, second).assessment == "correto"
    assert addition_feedback(FIRST_ADDITION, "Cada colega me deu um par.").assessment == ""


def test_explanation_with_chairs_is_accepted_and_referenced():
    point = "Quanto é 4 mais 1? Como sabe?"
    first = "4 mais 1 é igual a 5."
    second = "Por exemplo, quatro cadeiras, mais uma cadeira, são cinco cadeiras."
    assert addition_feedback(point, second).assessment == "correto"
    assert "cadeiras" in addition_comparison(point, first, second)


def test_solver_does_not_require_pencils_or_original_operand_order():
    point = "Quanto é 4 mais 1? Como sabe?"
    speech = "Uma bolinha com quatro bolinhas, dá cinco bolinhas."
    assert addition_feedback(point, speech).assessment == "correto"
    assert "bolinhas" in addition_comparison(point, "", speech)


def test_narrated_purchase_is_an_explanation_of_the_sum():
    point = "Quanto é 4 mais 1? Como sabe?"
    speech = "Se eu tenho quatro lápis e compro mais um, eu vou ter cinco lápis."
    wrong = "Eu tinha quatro blocos e coloquei mais um. Agora tenho seis blocos."
    assert addition_feedback(point, speech).assessment == "correto"
    assert "lápis" in addition_comparison(point, "", speech)
    assert addition_feedback(point, wrong).assessment == "equivoco"


def test_narrated_addition_accepts_an_explanation_with_two_purchases():
    point = "Quanto é 1 mais 2 mais 2? Como sabe?"
    explanation = (
        "Tenho um lápis e compro mais dois, vou ter três lápis. "
        "Se eu compro mais dois, eu vou ter cinco lápis."
    )
    assert addition_feedback(point, explanation).assessment == "correto"
    assert addition_feedback(point, explanation.replace("três", "quatro")).assessment == "equivoco"


def test_inconclusive_followup_keeps_the_confirmed_first_explanation():
    point = "Quanto é 4 mais 1? Como sabe?"
    item = {
        "first_assessment": "correto",
        "second_assessment": "",
        "focus_point": point,
        "first_transcript": "Tenho quatro lápis e ganhei mais um. Agora tenho cinco lápis.",
        "comparison": "Repita este trecho.",
    }
    assert mission_verdict("correto", "") == "correto"
    assert mission_verdict("correto", "equivoco") == "equivoco"
    assert mission_verdict("equivoco", "") == ""
    assert mission_feedback(item) == "Você mostrou a soma com lápis."
