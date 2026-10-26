"""Conservative, local lexical coverage of an optional reference text.

Coverage describes overlap with the transcript, never factual correctness.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

STOP = frozenset(
    [
        "a",
        "ao",
        "aos",
        "as",
        "com",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "ou",
        "para",
        "por",
        "que",
        "um",
        "uma",
        "umas",
        "uns",
        "se",
        "seu",
        "sua",
        "seus",
        "suas",
        "sobre",
        "isso",
        "esta",
        "este",
        "muito",
        "mais",
        "como",
        "quando",
    ]
)
METHOD = "lexical-pt-v1"


def normalize(word: str) -> str:
    word = "".join(
        c for c in unicodedata.normalize("NFKD", word.lower()) if not unicodedata.combining(c)
    )
    for suffix in (
        "mente",
        "acoes",
        "acao",
        "idades",
        "idade",
        "ando",
        "endo",
        "indo",
        "ados",
        "adas",
        "idos",
        "idas",
        "es",
        "s",
    ):
        if len(word) > len(suffix) + 4 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def terms(text: str) -> set[str]:
    return {
        normalize(w)
        for w in re.findall(r"[\wÀ-ÿ]+", text.lower())
        if len(w) >= 3 and normalize(w) not in STOP
    }


def derive_points(text: str) -> list[str]:
    """Use explicit nonempty lines as points; no generated claims."""
    raw = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", p).strip() for p in text.splitlines()]
    return [p for p in raw if p and terms(p)][:30]


def suggest_review_points(text: str, limit: int = 8) -> list[str]:
    """Sample verbatim sentences across prose for human review, not AI analysis."""
    candidates: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        sentence = sentence.strip()
        if 1 <= len(sentence) <= 500 and terms(sentence) and sentence not in candidates:
            candidates.append(sentence)
    if len(candidates) <= limit:
        return candidates
    return [candidates[round(i * (len(candidates) - 1) / (limit - 1))] for i in range(limit)]


def validate_points(text: str, points: list[str]) -> list[str]:
    if (
        len(points) > 30
        or not points
        or any(not isinstance(p, str) or not p.strip() or len(p) > 500 for p in points)
    ):
        raise ValueError("Pontos invalidos")
    reference_terms = terms(text)
    if any(not terms(p) or not terms(p) <= reference_terms for p in points):
        raise ValueError("Ponto sem apoio no conteudo")
    return [p.strip() for p in points]


def reference_synonyms(text: str) -> dict[str, set[str]]:
    """Only explicit single-word parenthetical alternatives in the source."""
    groups: dict[str, set[str]] = {}
    for left, right in re.findall(r"\b([\wÀ-ÿ]+)\s*\(([\wÀ-ÿ]+)\)", text):
        a, b = normalize(left), normalize(right)
        if a != b and len(a) >= 4 and len(b) >= 4:
            groups.setdefault(a, set()).add(b)
            groups.setdefault(b, set()).add(a)
    return groups


@dataclass(frozen=True)
class Match:
    status: str
    overlap: float
    evidence: str | None
    seconds: float | None


def match_point(
    point: str,
    transcript: str,
    *,
    seconds: float | None = None,
    synonyms: dict[str, set[str]] | None = None,
) -> Match:
    key = terms(point)
    if not key or not transcript.strip():
        return Match("not_mentioned", 0.0, None, None)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", transcript) if s.strip()]
    synonyms = synonyms or {}

    def matched(sentence: str) -> set[str]:
        spoken = terms(sentence)
        return {term for term in key if term in spoken or bool(synonyms.get(term, set()) & spoken)}

    best = max(sentences, key=lambda s: len(matched(s)), default="")
    overlap = len(matched(best)) / len(key)
    # At least two distinct terms avoid a one-word false positive. Single-term
    # points require exact normalized match; no semantic inference is made.
    hits = len(matched(best))
    point_negated = bool(re.search(r"\b(não|nao|nunca)\b", point.lower()))
    transcript_negated = bool(re.search(r"\b(não|nao|nunca)\b", best.lower()))
    # Only flag explicit polarity reversal when most content words occur in
    # the same sentence. This is a possible divergence, not a fact check.
    if overlap >= 0.7 and hits >= 2 and point_negated != transcript_negated:
        status = "possible_divergence"
    else:
        status = (
            "covered"
            if overlap >= 0.7 and (hits >= 2 or len(key) == 1)
            else "partial"
            if hits >= 2
            else "not_mentioned"
        )
    return Match(
        status,
        round(overlap, 3),
        best[:240] if status != "not_mentioned" else None,
        seconds if status != "not_mentioned" else None,
    )


def report(
    snapshot: dict, transcript: str, *, duration: float, is_demo: bool, stages: dict | None = None
) -> dict:
    points = snapshot["points"]
    synonyms = reference_synonyms(snapshot.get("text", ""))
    items = []
    for index, point in enumerate(points):
        match = match_point(point, transcript, synonyms=synonyms)
        position = transcript.find(match.evidence) if match.evidence else -1
        approx_seconds = (
            round(duration * position / max(len(transcript), 1), 1) if position >= 0 else None
        )
        items.append(
            {
                "index": index,
                "point": point,
                "status": match.status,
                "overlap": match.overlap,
                "evidence": match.evidence,
                "approx_seconds": approx_seconds,
                "origin": "demo" if is_demo else "real",
            }
        )
    covered = sum(item["status"] == "covered" for item in items)
    return {
        "method_version": METHOD,
        "content_id": snapshot["id"],
        "content_version": snapshot["version"],
        "origin": "demo" if is_demo else "real",
        "stages": stages or {},
        "duration_seconds": duration,
        "coverage_percent": round(100 * covered / len(items)) if items else 0,
        "points": items,
        "mention_order": [
            item["index"]
            for item in sorted(
                (item for item in items if item["approx_seconds"] is not None),
                key=lambda item: (item["approx_seconds"], item["index"]),
            )
        ],
        "possible_divergences": [item for item in items if item["status"] == "possible_divergence"],
        "disclaimer": "Cobertura lexical nao comprova correcao factual nem dominio do assunto.",
    }
