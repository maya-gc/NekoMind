"""Local AI tutor (Ollama): question, hint and comparison adapted to any subject.

Works for simple and advanced topics (e.g. Hamiltonian, quantum computing):
the model reads the mission point and what the student actually said, and
returns a Socratic question about what is missing or inaccurate, a hint that
does not give the answer away, and after the second answer a short comparison.

Everything is optional and local: if Ollama or the model is missing, slow or
returns something invalid, callers fall back to the lexical rules in
``app.mac.dialogue``. Texts are bounded for the 240x320 LCD.
"""

from __future__ import annotations

import json
import logging
import time

import httpx

from app.errors import log_swallowed

logger = logging.getLogger(__name__)

OLLAMA = "http://127.0.0.1:11434"
LIMITS = {"question": 140, "hint": 120, "comparison": 94}
_available_cache: dict[str, tuple[float, bool]] = {}

SYSTEM = (
    "Você é a gatinha NekoMind, tutora socrática em português do Brasil. "
    "Adapte o nível ao assunto: do básico ao avançado (física, matemática, "
    "computação quântica...). Use termos corretos do tema. Nunca dê a resposta "
    "completa. Responda apenas com JSON válido."
)


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    cut = data[: limit - 3].decode("utf-8", errors="ignore").rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "..."


def available(model: str, *, ttl: float = 60.0) -> bool:
    now = time.monotonic()
    cached = _available_cache.get(model)
    if cached and now - cached[0] < ttl:
        return cached[1]
    ok = False
    try:
        with httpx.Client(trust_env=False, timeout=1.5) as client:
            tags = client.get(f"{OLLAMA}/api/tags").json().get("models", [])
        names = {t.get("name", "") for t in tags}
        ok = model in names or f"{model}:latest" in names
    except Exception as exc:  # noqa: BLE001 - Ollama off is a normal state
        log_swallowed(logger, "tutor_ai.available", exc)
        ok = False
    _available_cache[model] = (now, ok)
    return ok


LEVELS = {
    "crianca": "Fale como para uma criança de 10 anos: frases curtas, exemplos do dia a dia.",
    "enem": "Fale como para um estudante do ensino médio se preparando para o ENEM.",
    "faculdade": "Fale como para um universitário: rigor técnico e termos corretos da área.",
}
ASSESSMENTS = {"correto", "parcial", "equivoco", "nao_mencionou"}


def _ask(model: str, prompt: str, timeout: float, fields: tuple[str, ...]) -> dict:
    properties = {field: {"type": "string"} for field in fields}
    if "assessment" in properties:
        properties["assessment"]["enum"] = sorted(ASSESSMENTS)
    schema = {
        "type": "object", "properties": properties, "required": list(fields),
        "additionalProperties": False,
    }
    payload = {
        "model": model,
        "system": SYSTEM,
        "prompt": prompt,
        "format": schema,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": 420},
    }
    if model.partition(":")[0] in {"qwen3", "qwen3.5"}:
        payload["think"] = False
    with httpx.Client(trust_env=False, timeout=timeout) as client:
        response = client.post(f"{OLLAMA}/api/generate", json=payload)
        response.raise_for_status()
    data = json.loads(response.json()["response"])
    if not isinstance(data, dict):
        raise TypeError("resposta nao e objeto JSON")
    return data


def _text(data: dict, key: str, limit: int) -> str:
    value = data.get(key)
    return _short(value, limit) if isinstance(value, str) and value.strip() else ""


def _assessment(data: dict) -> str:
    value = str(data.get("assessment", "")).strip().lower()
    return value if value in ASSESSMENTS else "parcial"


def reconcile(assessment: str, lexical_status: str, evidence: str = "") -> str:
    """Use a cited excerpt to support correct reasoning with different words."""
    if assessment == "correto" and lexical_status == "not_mentioned" and not evidence:
        return "parcial"
    return assessment


def _evidence(data: dict, transcript: str) -> str:
    value = data.get("evidence")
    if not isinstance(value, str):
        return ""
    compact = " ".join(value.casefold().split())
    speech = " ".join(transcript.casefold().split())
    return " ".join(value.split()) if 8 <= len(compact) <= 180 and compact in speech else ""


def _supported_evidence(
    data: dict, transcript: str, point: str, model: str, reference: str, timeout: float,
) -> str:
    evidence = _evidence(data, transcript)
    if (
        evidence or _assessment(data) not in {"correto", "equivoco"}
        or reference.startswith("Gabarito para avaliação:")
    ):
        return evidence
    prompt = (
        "Copie um trecho literal da transcrição que sustente o parecer sobre a pergunta. "
        "Não corrija palavras nem acrescente fatos. Se não houver trecho, deixe evidence vazio. "
        "Use até 140 caracteres. Retorne apenas o JSON com evidence.\n"
        f"Pergunta: {point[:350]}\nParecer: {_assessment(data)}\n"
        f"Transcrição: {_speech_window(transcript)}"
    )
    try:
        return _evidence(_ask(model, prompt, min(timeout, 8), ("evidence",)), transcript)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return ""


def _analogy(data: dict, transcript: str) -> str:
    value = data.get("analogy")
    if not isinstance(value, str):
        return ""
    label = " ".join(value.split()).casefold()
    words = label.split()
    if not 1 <= len(words) <= 3 or len(label) > 24 or not all(word.isalpha() for word in words):
        return ""
    phrase = " ".join("".join(c if c.isalpha() else " " for c in transcript.casefold()).split())
    return label if f" {label} " in f" {phrase} " else ""


def _speech_window(text: str) -> str:
    limit = 2200
    return text if len(text) <= limit else text[:1000] + " […] " + text[-1195:]


def warm_up(model: str) -> bool:
    """Load the model into memory so the first question does not time out."""
    if not available(model):
        return False
    try:
        with httpx.Client(trust_env=False, timeout=180) as client:
            client.post(f"{OLLAMA}/api/generate",
                        json={"model": model, "prompt": "", "keep_alive": "30m"})
        return True
    except Exception as exc:  # noqa: BLE001
        log_swallowed(logger, "tutor_ai.warm_up", exc)
        return False


RUBRIC = (
    "Critérios (avalie pelo SIGNIFICADO; palavras diferentes valem):\n"
    "- correto: explica a relação central, também por contagem, analogia ou sinônimo.\n"
    "  Exemplo: a poça some porque a água vira algo invisível que vai para o ar. "
    "Isso descreve evaporação mesmo sem usar a palavra vapor.\n"
    "- parcial: está no assunto do ponto, mas incompleto ou vago. Incompleto NÃO é erro.\n"
    "- equivoco: afirma um fato errado sobre a pergunta. Um assunto diferente ou falta "
    "de detalhe nunca são equívocos. Cite qual afirmação da fala está errada.\n"
    "- nao_mencionou: fala de outra coisa (até de outro ponto do mesmo material).\n"
    "Exemplo (ponto: 'A gravidade atrai os objetos para o centro da Terra'):\n"
    "  'tudo cai porque a Terra puxa as coisas para o meio dela' -> correto\n"
    "  'a gravidade é uma força' -> parcial\n"
    "  'a gravidade empurra os objetos para cima' -> equivoco\n"
    "  'a Lua gira em volta da Terra' -> nao_mencionou\n"
)


def first_turn(point: str, transcript: str, model: str, *, material: str = "",
               level: str = "enem", history: str = "", timeout: float = 40.0) -> dict:
    """Judge the explanation by meaning and return question + three graded hints.

    Returns {"assessment", "misconception", "question", "hint", "hints"}.
    ``assessment``: correto | parcial | equivoco | nao_mencionou (paraphrases
    count; exact words are not required).
    """
    prompt = (
        f"{LEVELS.get(level, LEVELS['enem'])}\n"
        f"Material de estudo (contexto): {material[:1500]}\n\n"
        f"Ponto da missão: {point}\n"
        f"O que o estudante explicou (transcrição automática, pode ter erros de "
        f"grafia): {_speech_window(transcript) or '(nada)'}\n"
        f"{('Histórico: ' + history) if history else ''}\n\n"
        f"{RUBRIC}"
        "1) Transcreva uma evidência curta em evidence e diga em meaning o que ela mostra, "
        "sem completar ideias que a pessoa não disse. Depois classifique em assessment. "
        "Se o ponto for pergunta, avalie a resposta à pergunta, incluindo o raciocínio.\n"
        "2) Julgue o raciocínio pelo sentido. Qualquer objeto pode ilustrar a mesma relação. "
        "Use analogy para nomear o objeto citado, sem inventar. Cite em evidence um trecho literal "
        "da fala que sustente a avaliação. Se faltarem elementos, trate como parcial. "
        "Só descreva misconception quando houver uma afirmação errada sustentada pela fala.\n"
        "3) Escreva UMA pergunta curta: se houve equívoco, leve o estudante a "
        "perceber o erro; senão, pergunte sobre o que faltou; se estava correto, "
        "aprofunde (por quê? exemplo? consequência?).\n"
        "4) Dê três ações curtas para tentar, sem entregar a resposta. Use a linguagem do público do material. Cada dica tem no "
        "máximo 48 caracteres e a pergunta também: hint1 = pista leve; hint2 = analogia curta; "
        "hint3 = começo de um exemplo.\n"
        'Responda só com JSON. Chaves: evidence, meaning, analogy, assessment, misconception, '
        'question, hint1, hint2, hint3. Escreva perguntas e dicas reais.'
    )
    data = _ask(
        model, prompt, timeout,
        ("evidence", "meaning", "analogy", "assessment", "misconception", "question", "hint1", "hint2", "hint3"),
    )
    hints = []
    if hint := _text(data, "hint1", LIMITS["hint"]):
        hints.append(hint)
    for key in ("hint2", "hint3"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            hints.append(_short(value, LIMITS["hint"]))
    assessment = _assessment(data)
    misconception = _short(data.get("misconception") or "", 160)
    if assessment == "equivoco" and len(misconception) < 8:
        assessment = "parcial"  # sem dizer qual é o erro, não chame de equívoco
    return {
        "assessment": assessment,
        "evidence": _supported_evidence(data, transcript, point, model, material, timeout),
        "analogy": _analogy(data, transcript),
        "misconception": misconception if assessment == "equivoco" else "",
        "question": _text(data, "question", LIMITS["question"]),
        "hint": hints[0] if hints else "",
        "hints": hints,
    }


def second_turn(point: str, question: str, first: str, second: str, model: str, *,
                level: str = "enem", timeout: float = 40.0, reference: str = "") -> dict:
    """Return {"comparison", "assessment"} for the second explanation."""
    prompt = (
        f"{LEVELS.get(level, LEVELS['enem'])}\n"
        f"Ponto da missão: {point}\nPergunta feita: {question}\n"
        f"Referência para avaliação: {reference}\n"
        f"1ª explicação: {_speech_window(first) or '(nada)'}\n"
        f"2ª explicação: {_speech_window(second) or '(nada)'}\n\n"
        f"{RUBRIC}"
        "Cite a fala nova em evidence e resuma seu sentido em meaning antes de classificar. "
        "A primeira fala serve só para comparar. Classifique a segunda isoladamente. "
        "Em UMA frase curta diga o que a segunda mostra e, se "
        "houver, o que ainda falta ou está errado, em até 48 caracteres para criança e até 85 nos outros níveis. "
        "Aceite analogias e passos equivalentes. Se as duas falas estiverem corretas, "
        "diga qual raciocínio foi explicado. Não invente um erro ou uma melhora. "
        "Qualquer objeto pode ilustrar a mesma relação. Em analogy, indique o objeto realmente citado. "
        "Inclua em evidence um trecho literal curto da segunda fala, ou vazio se não houver. "
        "Responda em JSON com as chaves evidence, meaning, analogy, assessment e comparison."
    )
    data = _ask(model, prompt, timeout, ("evidence", "meaning", "analogy", "assessment", "comparison"))
    return {"comparison": _text(data, "comparison", LIMITS["comparison"]),
            "assessment": _assessment(data),
            "evidence": _supported_evidence(data, second, point, model, reference, timeout),
            "analogy": _analogy(data, second)}
