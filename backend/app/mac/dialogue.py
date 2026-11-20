"""Source-grounded, local prompts for one follow-up after a guided explanation."""

import re

from app.services.content_matching import STOP, normalize

MAX_MISSION_BYTES = 44
MAX_MISSIONS = 30

STATUS_RANK = {
    "not_mentioned": 0,
    "partial": 1,
    "possible_divergence": 2,
    "covered": 3,
}
MAX_COMPARISON_BYTES = 94
WORD_RE = re.compile(r"[\wÀ-ÿ]+")

LCD_PROMPT_CHARS = 48
LCD_TEXT = re.compile(r"[A-Za-zÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç0-9 .,:!?/\-]+")
BULLET = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
METADATA = re.compile(
    r"^(?:tema|p[úu]blico(?:-alvo)?|objetivos?|n[íi]vel|faixa et[áa]ria|"
    r"diagn[óo]stico|miss[õo]es|(?:primeira |segunda )?dicas?)\b",
    re.IGNORECASE,
)
MISSION_HEADER = re.compile(r"^(?:#{1,6}\s+)?miss[õo]es\s*:?$", re.IGNORECASE)
SECTION_HEADER = re.compile(r"^#{1,6}\s+\S")
AUTHORED_QUESTION = re.compile(r"\bpergunte:\s*[“\"]?([^?”\"]+\?)", re.IGNORECASE)


def short_text(value: str, max_bytes: int) -> str:
    compact = " ".join(value.split())
    if len(compact.encode("utf-8")) <= max_bytes:
        return compact
    clipped = compact.encode("utf-8")[: max_bytes - 3].decode("utf-8", errors="ignore")
    if " " in clipped and len(clipped.rsplit(" ", 1)[0]) >= len(clipped) // 2:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(" ,;:.!?") + "..."


def mission_points(source: str, points: list[str]) -> list[str]:
    """Prefer named exercises and keep administrative lines out of the picker."""
    authored = []
    in_missions = False
    for raw in source.splitlines():
        line = raw.strip()
        if MISSION_HEADER.fullmatch(line):
            in_missions = True
        elif in_missions and SECTION_HEADER.match(line):
            break
        elif in_missions and BULLET.match(line):
            point = BULLET.sub("", line)
            if not METADATA.match(point):
                authored.append(point)
    candidates = authored or [point for point in points if not METADATA.match(point)]
    return list(dict.fromkeys(candidates))[:MAX_MISSIONS]


def mission_previews(points: list[str]) -> list[str]:
    previews = []
    for point in points[:MAX_MISSIONS]:
        previews.append(short_text(mission_title(point), MAX_MISSION_BYTES))
    return previews


def mission_title(point: str) -> str:
    title, _, instructions = point.partition(". ")
    if AUTHORED_QUESTION.search(instructions) or re.match(
        r"^(?:mostre|pergunte)\b", instructions, re.IGNORECASE,
    ):
        return title
    return point


def lcd_line(value: object) -> str | None:
    # The landscape result card has three rows with 24 glyphs each. Leave room
    # for wrapping at spaces and reject glyphs unsupported by the firmware.
    if not isinstance(value, str):
        return None
    line = " ".join(value.split())
    if (
        len(line) <= LCD_PROMPT_CHARS
        and LCD_TEXT.fullmatch(line)
        and any(char.isalnum() for char in line)
        and all(len(word) <= 24 for word in line.split())
    ):
        return line
    return None


def authored_hint_for(point: str, source: str) -> str | None:
    label = mission_title(point)
    if label == point:
        return None
    pattern = (
        r"^Dicas? para a miss[ãa]o " + re.escape(label.rstrip(" .!?"))
        + r":?[^\S\n]*\n[^\S\n]*(?:[-*•]\s*)?(?:Primeira dica:\s*)?([^\n]+)"
    )
    match = re.search(pattern, source, re.IGNORECASE | re.MULTILINE)
    return lcd_line(match[1].strip(' “”:."') + ".") if match else None


def fallback_dialogue(point: str) -> tuple[str, str]:
    authored = AUTHORED_QUESTION.search(point)
    label = mission_title(point).rstrip(" .!?")
    # Prepared missions may already be complete LCD-safe questions. Reuse them
    # instead of wrapping them in another "O que sabe sobre ...?" prompt.
    question = lcd_line(point) if point.rstrip().endswith("?") else None
    # Ask about the method when an authored exercise relies on a visual aid.
    question = question or (
        lcd_line(authored[1]) if authored and "mostre " not in point.lower() else None
    )
    question = question or lcd_line(question_for(point)) or lcd_line(f"Como resolveu: {label}?")
    question = question or lcd_line(f"O que sabe sobre {short_text(label, 28)}?")
    hint = lcd_line(hint_for(point))
    return question or "Como você resolveu essa missão?", hint or "Dica: pense em um exemplo."


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
