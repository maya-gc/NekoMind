"""One rule for broad ``except Exception`` blocks: never swallow silently.

Optional parts (voice, tutor, memory, probes) may degrade, but the log must say
where it happened and which error type it was. Only the type is logged, never
the message, because messages can carry transcripts, paths or payloads.
"""

from __future__ import annotations

import logging


def log_swallowed(logger: logging.Logger, where: str, exc: BaseException,
                  level: int = logging.WARNING) -> None:
    logger.log(level, "%s: falha tratada (%s)", where, type(exc).__name__)
