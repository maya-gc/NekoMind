"""Source-grounded, local prompts for one follow-up after a guided explanation."""

import re

from app.services.content_matching import STOP, normalize

MAX_MISSION_BYTES = 60
MAX_MISSIONS = 30

STATUS_RANK = {
    "not_mentioned": 0,
    "partial": 1,
    "possible_divergence": 2,
    "covered": 3,
}
MAX_COMPARISON_BYTES = 94
WORD_RE = re.compile(r"[\wÀ-ÿ]+")


def short_text(value: str, max_bytes: int) -> str:
    compact = " ".join(value.split())
    if len(compact.encode("utf-8")) <= max_bytes:
        return compact
    clipped = compact.encode("utf-8")[: max_bytes - 3].decode("utf-8", errors="ignore")
    if " " in clipped and len(clipped.rsplit(" ", 1)[0]) >= len(clipped) // 2:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(" ,;:.!?") + "..."


def mission_previews(points: list[str]) -> list[str]:
    return [short_text(point, MAX_MISSION_BYTES) for point in points[:MAX_MISSIONS]]


def choose_focus(report: dict, preferred_index: int = 0) -> tuple[int, str] | None:
    points = report.get("points") if isinstance(report, dict) else None
    if not isinstance(points, list) or not points:
        return None
    candidates = [
        (index, item["point"], STATUS_RANK.get(item.get("status"), 4))
        for index, item in enumerate(points[:MAX_MISSIONS])
        if isinstance(item, dict) and isinstance(item.get("point"), str) and item["point"].strip()
    ]
    if not candidates:
        return None
    for index, point, _ in candidates:
        if index == preferred_index:
            return index, point
    index, point, _ = min(
        candidates,
        key=lambda item: (item[2], item[0]),
    )
    return index, point


def question_for(point: str) -> str:
    compact = " ".join(point.split()).rstrip(" .!?")
    if len(compact.encode("utf-8")) > 65:
        return "Explique a ideia central desta missão com suas palavras."
    return f"Como você explicaria: {compact}?"


def hint_for(point: str) -> str:
    keywords = []
    seen = set()
    for word in re.findall(r"[\wÀ-ÿ]+", point):
        key = normalize(word)
        if len(word) < 3 or key in STOP or key in seen:
            continue
        seen.add(key)
        keywords.append(short_text(word, 18))
        if len(keywords) == 3:
            break
    if len(keywords) >= 2:
        return "Dica: pense na relação entre " + ", ".join(keywords) + "."
    if keywords:
        return f"Dica: procure no material a parte sobre {keywords[0]}."
    return "Dica: releia o ponto do material e tente explicá-lo com um exemplo."


def _source_phrase(point: str, speech: str, *, absent_from: str = "") -> str:
    """Find a short phrase present in both the source and the spoken evidence."""
    source = list(WORD_RE.finditer(point))
    spoken = [normalize(word) for word in WORD_RE.findall(speech)]
    earlier = {normalize(word) for word in WORD_RE.findall(absent_from)}
    best = ((), "")
    for start in range(len(source)):
        for end in range(start + 2, min(start + 6, len(source)) + 1):
            words = [normalize(match.group()) for match in source[start:end]]
            content = [word for word in words if word not in STOP and len(word) >= 3]
            if not 2 <= len(content) <= 3 or words[0] in STOP or words[-1] in STOP:
                continue
            phrase = point[source[start].start():source[end - 1].end()]
            if len(phrase.encode("utf-8")) > 34:
                continue
            if not any(spoken[i:i + len(words)] == words for i in range(len(spoken) - len(words) + 1)):
                continue
            if absent_from and not any(word not in earlier for word in content):
                continue
            concept = len(words) == 3 and words[1] in {"de", "do", "da", "dos", "das"}
            end_mark = point[source[end - 1].end():].lstrip().startswith((",", ".", ";"))
            score = (concept, len(content), end_mark, -start, -len(phrase))
            if score > best[0]:
                best = (score, phrase)
    return best[1]


def comparison_for(
    point: str, first_status: str, second_status: str,
    first_evidence: str = "", second_evidence: str = "",
) -> str:
    """Compare observable speech, without treating lexical overlap as correctness."""
    if second_status == "possible_divergence":
        message = "A segunda fala pode divergir do material. Revise este ponto."
    else:
        new_phrase = _source_phrase(point, second_evidence, absent_from=first_evidence)
        lost_phrase = _source_phrase(point, first_evidence, absent_from=second_evidence)
        if new_phrase:
            message = f"Agora: {new_phrase}. Antes, esse trecho não apareceu."
        elif (STATUS_RANK.get(second_status, 0) < STATUS_RANK.get(first_status, 0)
              and lost_phrase):
            message = f"Na segunda, faltou {lost_phrase}; antes apareceu."
        elif first_status == "not_mentioned" and second_status == "not_mentioned":
            message = "Esse ponto não apareceu nas duas falas. Releia a missão."
        else:
            shared = _source_phrase(point, second_evidence)
            if shared:
                message = f"Nas duas falas: {shared}. Explique a relação."
            elif STATUS_RANK.get(second_status, 0) > STATUS_RANK.get(first_status, 0):
                message = "A segunda fala trouxe mais termos do ponto. Confira a relação."
            else:
                message = "Compare as duas falas com o ponto do material."
    return short_text(message, MAX_COMPARISON_BYTES)
