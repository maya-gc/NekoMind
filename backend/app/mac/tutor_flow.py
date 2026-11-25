"""Guided dialogue on top of a capture: question, graded hints, comparison.

Uses the local AI tutor when available and the rule-based dialogue otherwise.
"""

import logging

from app.config import get_settings
from app.errors import log_swallowed
from app.mac.dialogue import (
    authored_hint_for,
    choose_focus,
    comparison_for,
    fallback_dialogue,
    lcd_line,
)
from app.mac.mission_exercises import (
    addition_comparison,
    addition_feedback,
    addition_reference,
    mission_feedback,
    mission_first_assessment,
    mission_verdict,
)
from app.services.content_matching import match_point

logger = logging.getLogger("app.mac.bridge")


def tutor_reconcile(assessment, lexical_status, evidence=""):
    from app.services.tutor_ai import reconcile

    return reconcile(assessment, lexical_status, evidence)


def _selected_focus(row, item):
    index = item.get("mission_index", 0)
    if point := item.get("mission_point"):
        return index, point
    return choose_focus(row.get("content_report"), index)


def _tutor_text(value, level):
    if (
        not isinstance(value, str) or not value.strip()
        or "<" in value or ">" in value or "caracteres" in value.casefold()
    ):
        return None
    return lcd_line(value) if level == "crianca" else value


def _grounded_assessment(tutor):
    assessment = tutor.get("assessment", "")
    if assessment in {"correto", "equivoco"} and not tutor.get("evidence"):
        return ""
    return assessment


def _compatible_assessment(assessment, feedback):
    if not feedback:
        return assessment
    if assessment == "equivoco" and feedback.assessment != "equivoco":
        return ""
    if assessment == "correto" and feedback.assessment != "correto":
        return "parcial"
    return assessment


def _confirmed_message(tutor):
    analogy = tutor.get("analogy", "")
    return lcd_line(f"Você explicou usando {analogy}.") if analogy else None


class TutorFlowMixin:
    """Needs the bridge state: ``interaction``, ``sid``, ``state``, ``demo``,
    ``lock``, ``speaker``, ``tutor_cache`` and the memory mixin."""

    def _followup_wire(self):
        item = self.interaction
        if (
            self.state in {"idle", "checking", "ready"}
            or not item
            or self.sid not in {item.get("first_sid"), item.get("second_sid")}
        ):
            return None
        stage = item.get("stage")
        if stage in {"question", "hint", "done"}:
            if self.state != "completed":
                return None
        elif stage != "answering" or self.state not in {
            "recording", "paused", "processing", "error", "recovery",
        }:
            return None
        return {
            "stage": stage,
            "point_index": item["focus_index"],
            "question": item["question"],
            "hint": item.get("hint", "") if item.get("hint_shown") or stage == "done" else "",
            "comparison": mission_feedback(item) if stage == "done" else "",
        }

    def _followup_public(self):
        followup = self._followup_wire()
        if followup is not None:
            item = self.interaction
            first = mission_first_assessment(item)
            assessment = (
                mission_verdict(first, item.get("second_assessment", ""))
                if followup["stage"] == "done" else first
            )
            followup["source_point"] = item.get("focus_point", "")
            followup["assessment"] = assessment if assessment in {
                "correto", "parcial", "equivoco", "nao_mencionou"} else ""
            followup["tutor"] = item.get("tutor", "") if item.get("tutor") in {
                "ia_local", "regras"} else ""
        if followup is not None and followup["stage"] == "done":
            followup.update(
                source_point=self.interaction.get("focus_point", ""),
                first_excerpt=self.interaction.get("first_evidence", ""),
                second_excerpt=self.interaction.get("second_evidence", ""),
            )
        return followup

    def _say(self, text):
        if self.speaker is None:
            return
        try:
            self.speaker.speak(text)
        except Exception as exc:  # noqa: BLE001 - voz opcional nao altera a captura
            logger.warning("Voz local indisponivel; mantendo o fluxo de captura. (%s)",
                           type(exc).__name__)

    def _silence(self):
        if self.speaker is None:
            return
        try:
            self.speaker.stop()
        except Exception as exc:  # noqa: BLE001 - captura tem prioridade sobre voz
            logger.warning("Falha ao interromper a voz local. (%s)", type(exc).__name__)

    def _result_speech(self, row):
        if self.demo:
            return "A demonstração terminou. Em uma sessão real, vou ouvir sua explicação."
        report = row.get("content_report")
        if isinstance(report, dict):
            coverage = report.get("coverage_percent")
            if isinstance(coverage, (int, float)) and coverage < 50:
                return "Obrigada por explicar! Quer tentar de novo e falar de outro ponto do material?"
            return "Obrigada por explicar! Quer tentar de novo e ligar duas ideias com um exemplo?"
        return "Obrigada por explicar! Quer tentar de novo e incluir um exemplo?"

    def _prefetch_tutor(self, sid, row):
        """Ask the local AI tutor before publishing the result (never under the lock)."""
        try:
            if row.get("status") != "completed" or self.demo:
                return
            settings = get_settings()
            provider = getattr(settings, "tutor_provider", "regras")
            model = getattr(settings, "tutor_model", "")
            with self.lock:
                item = dict(self.interaction)
            transcript = row.get("transcription", "") or ""
            first_turn = sid == item.get("first_sid") and item.get("stage") == "explaining"
            second_turn = sid == item.get("second_sid") and item.get("stage") == "answering"
            if first_turn:
                focus = _selected_focus(row, item)
                if focus is None:
                    return
                reference = self.backend.reference(sid) or {}
                material = reference.get("text") or ""
                rubric = addition_reference(focus[1])
                self.tutor_cache[("first", sid)] = {
                    "point": focus[1], "authored_hint": authored_hint_for(focus[1], material),
                    "level": "crianca" if rubric or "educação infantil" in material.casefold() else settings.tutor_level,
                }
            if provider == "regras" or not (first_turn or second_turn):
                return
            from app.services import tutor_ai

            model = tutor_ai.resolve_model(model)
            if provider == "auto" and not tutor_ai.available(model):
                return
            if first_turn:
                result = tutor_ai.first_turn(
                    focus[1], transcript, model, material=f"{rubric}\n{material}".strip(),
                    level=self.tutor_cache[("first", sid)]["level"],
                    history=self._memory_note(focus[1]),
                )
                self.tutor_cache[("first", sid)].update(result)
            elif second_turn:
                reference = self.backend.reference(item["first_sid"]) or {}
                point = item.get("focus_point", "")
                material = reference.get("text") or ""
                result = tutor_ai.second_turn(
                    item.get("focus_point", ""), item.get("question", ""),
                    item.get("first_transcript", ""), transcript, model,
                    level=item.get("tutor_level") or settings.tutor_level,
                    reference=f"{addition_reference(point)}\n{material}".strip(),
                )
                self.tutor_cache[("second", sid)] = result
        except Exception as exc:  # noqa: BLE001 - tutor IA e opcional; regras locais assumem
            logger.warning("Tutor IA indisponivel (%s); usando regras locais.",
                           type(exc).__name__)

    def _prepare_interaction_result(self, row):
        item = self.interaction
        if self.demo or not item:
            return None
        if self.sid == item.get("first_sid") and item.get("stage") == "explaining":
            focus = _selected_focus(row, item)
            if focus is None:
                return None
            index, point = focus
            speech = row.get("transcription") or ""
            first_match = match_point(point, speech)
            feedback = addition_feedback(point, speech)
            tutor = self.tutor_cache.pop(("first", self.sid), None)
            if not tutor or tutor.get("point") != point:
                tutor = {}
            fallback_question, fallback_hint = fallback_dialogue(point)
            level = tutor.get("level")
            question = _tutor_text(tutor.get("question"), level) or fallback_question
            hints = [hint for line in tutor.get("hints", []) if (hint := _tutor_text(line, level))]
            authored_hint = tutor.get("authored_hint")
            if authored_hint:
                hints = [authored_hint, *(hint for hint in hints if hint != authored_hint)]
            assessment = _compatible_assessment(_grounded_assessment(tutor), feedback)
            if feedback and (
                feedback.assessment in {"correto", "equivoco"}
                or not assessment
            ):
                question = feedback.question
                hints = [feedback.hint]
                assessment = feedback.assessment
            item.update(
                stage="question",
                focus_index=index,
                focus_point=point,
                question=question,
                hint=hints[0] if hints else fallback_hint,
                hints=hints,
                hint_level=0,
                tutor="ia_local" if "question" in tutor else "regras",
                first_assessment=assessment,
                tutor_level=tutor.get("level"),
                misconception="" if feedback else tutor.get("misconception", ""),
                first_transcript=(row.get("transcription", "") or "")[:2000],
                hint_shown=False,
                first_status=first_match.status,
                first_evidence=(
                    tutor.get("evidence") or (speech[:240] if feedback and feedback.analogy else "")
                    or first_match.evidence or ""
                ),
            )
            self._save_interaction()
            return item["question"]
        if self.sid == item.get("second_sid") and item.get("stage") == "answering":
            speech = row.get("transcription") or ""
            second_match = match_point(item["focus_point"], speech)
            feedback = addition_feedback(item["focus_point"], speech)
            comparison = addition_comparison(
                item["focus_point"], item.get("first_transcript", ""), speech,
            )
            tutor = self.tutor_cache.pop(("second", self.sid), None) or {}
            tutor_comparison = _tutor_text(tutor.get("comparison"), item.get("tutor_level"))
            assessment = _compatible_assessment(_grounded_assessment(tutor), feedback)
            if assessment == "correto" and not tutor_comparison:
                tutor_comparison = _confirmed_message(tutor) or "Você explicou como chegou ao resultado."
            if feedback and not comparison and not tutor_comparison:
                comparison = (
                    "Não entendi esse trecho. Pode dizer de novo?"
                    if item.get("first_assessment") != "correto"
                    else "A primeira soma ficou certa. Repita este trecho."
                )
            item.update(
                stage="done",
                second_status=second_match.status,
                second_evidence=(
                    tutor.get("evidence") or (speech[:240] if feedback and feedback.analogy else "")
                    or second_match.evidence or ""
                ),
                comparison=comparison or tutor_comparison or comparison_for(
                    item["focus_point"], item["first_status"], second_match.status,
                    item.get("first_evidence", ""), second_match.evidence or "",
                ),
            )
            if feedback and (
                feedback.assessment in {"correto", "equivoco"}
                or not assessment
            ):
                assessment = feedback.assessment
            item["second_assessment"] = assessment
            verdict = mission_verdict(mission_first_assessment(item), assessment)
            self._remember_point(item["focus_point"], verdict or second_match.status)
            self._save_interaction()
            return mission_feedback(item)
        return None

    def _warm_tutor(self):
        """Load the tutor model while the student reads the missions (best effort)."""
        try:
            settings = get_settings()
            if self.demo or getattr(settings, "tutor_provider", "regras") == "regras":
                return
            from threading import Thread

            from app.services import tutor_ai

            Thread(target=tutor_ai.warm_up, args=(settings.tutor_model,), daemon=True).start()
        except Exception as exc:  # noqa: BLE001
            log_swallowed(logger, "bridge._warm_tutor", exc)
