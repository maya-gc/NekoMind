"""Study memory: what each point looked like last time, and the review queue."""

import logging
from time import time

from app.errors import log_swallowed

logger = logging.getLogger("app.mac.bridge")


class StudyMemoryMixin:
    """Needs ``self.db`` (journal) and ``self.mission_content_id``."""

    def _memory_note(self, point):
        """What happened the last time this point was studied (local journal)."""
        try:
            row = self.db.execute(
                "SELECT status, ts FROM memory WHERE content_id IS ? AND point=? "
                "ORDER BY ts DESC LIMIT 1",
                (self.mission_content_id, point),
            ).fetchone()
        except Exception as exc:  # noqa: BLE001
            log_swallowed(logger, "bridge._memory_note", exc)
            return ""
        if not row:
            return ""
        days = max(0, int((time() - row[1]) // 86400))
        return f"há {days} dia(s) este ponto ficou como '{row[0]}'."

    def _remember_point(self, point, status):
        try:
            self.db.execute(
                "INSERT INTO memory VALUES(?,?,?,?)",
                (self.mission_content_id, point, str(status), time()),
            )
            self.db.commit()
        except Exception as exc:  # noqa: BLE001 - memoria e opcional
            logger.warning("Memoria de estudo indisponivel. (%s)", type(exc).__name__)

    def _review_safe(self):
        try:
            return [
                {**r, "point": r["point"][:500], "status": str(r["status"])[:32]}
                for r in self.review_queue()
            ]
        except Exception as exc:  # noqa: BLE001
            log_swallowed(logger, "bridge._review_safe", exc)
            return []

    def review_queue(self, limit=5):
        """Points whose last result was not 'correto', oldest first (spaced review)."""
        rows = self.db.execute(
            "SELECT content_id, point, status, MAX(ts) FROM memory GROUP BY content_id, point"
        ).fetchall()
        due = [r for r in rows if r[2] not in {"correto", "covered"}]
        return [
            {"content_id": r[0], "point": r[1], "status": r[2]}
            for r in sorted(due, key=lambda r: r[3])[:limit]
        ]
