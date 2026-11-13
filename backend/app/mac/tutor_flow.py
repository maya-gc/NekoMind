"""Guided dialogue on top of a capture: question, graded hints, comparison.

Uses the local AI tutor when available and the rule-based dialogue otherwise.
"""

import logging

from app.config import get_settings
from app.errors import log_swallowed
from app.mac.dialogue import choose_focus, comparison_for, hint_for, question_for
from app.services.content_matching import match_point

logger = logging.getLogger("app.mac.bridge")


def tutor_reconcile(assessment, lexical_status):
    from app.services.tutor_ai import reconcile

    return reconcile(assessment, lexical_status)


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
        if stage not in {"question", "hint", "answering", "done"}:
            return None
        return {
            "stage": stage,
            "point_index": item["focus_index"],
            "question": item["question"],
            "hint": item.get("hint", "") if item.get("hint_shown") else "",
            "comparison": item.get("comparison", "") if stage == "done" else "",
        }

    def _followup_public(self):
        followup = self._followup_wire()
        if followup is not None:
            item = self.interaction
            key = "second_assessment" if followup["stage"] == "done" else "first_assessment"
            assessment = item.get(key, "")
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
            if provider == "regras":
                return
            from app.services import tutor_ai

            if provider == "auto" and not tutor_ai.available(model):
                return
            with self.lock:
                item = dict(self.interaction)
            transcript = row.get("transcription", "") or ""
            if sid == item.get("first_sid") and item.get("stage") == "explaining":
                focus = choose_focus(row.get("content_report"), item.get("mission_index", 0))
                if focus is None:
                    return
                level = getattr(settings, "tutor_level", "enem")
                result = tutor_ai.first_turn(
                    focus[1], transcript, model, level=level,
                    history=self._memory_note(focus[1]),
                )
                self.tutor_cache[("first", sid)] = {**result, "point": focus[1]}
            elif sid == item.get("second_sid") and item.get("stage") == "answering":
                result = tutor_ai.second_turn(
                    item.get("focus_point", ""), item.get("question", ""),
                    item.get("first_transcript", ""), transcript, model,
                    level=getattr(settings, "tutor_level", "enem"),
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
            focus = choose_focus(row.get("content_report"), item.get("mission_index", 0))
            if focus is None:
                return None
            index, point = focus
            first_match = match_point(point, row.get("transcription", ""))
            tutor = self.tutor_cache.pop(("first", self.sid), None)
            if tutor and tutor.get("point") != point:
                tutor = None
            item.update(
                stage="question",
                focus_index=index,
                focus_point=point,
                question=tutor["question"] if tutor else question_for(point),
                hint=tutor["hint"] if tutor else hint_for(point),
                hints=tutor.get("hints", []) if tutor else [],
                hint_level=0,
                tutor="ia_local" if tutor else "regras",
                first_assessment=tutor_reconcile(tutor.get("assessment", ""), first_match.status)
                if tutor else "",
                misconception=tutor.get("misconception", "") if tutor else "",
                first_transcript=(row.get("transcription", "") or "")[:2000],
                hint_shown=False,
                first_status=first_match.status,
                first_evidence=first_match.evidence or "",
            )
            self._save_interaction()
            return item["question"]
        if self.sid == item.get("second_sid") and item.get("stage") == "answering":
            second_match = match_point(item["focus_point"], row.get("transcription", ""))
            tutor = self.tutor_cache.pop(("second", self.sid), None)
            item.update(
                stage="done",
                second_status=second_match.status,
                second_evidence=second_match.evidence or "",
                comparison=tutor["comparison"] if tutor else comparison_for(
                    item["focus_point"], item["first_status"], second_match.status,
                    item.get("first_evidence", ""), second_match.evidence or "",
                ),
            )
            item["second_assessment"] = tutor_reconcile(
                (tutor or {}).get("assessment", ""), second_match.status) if tutor else ""
            self._remember_point(item["focus_point"],
                                 item["second_assessment"] or second_match.status)
            self._save_interaction()
            return item["comparison"]
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
