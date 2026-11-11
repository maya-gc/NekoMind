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
    except Exception:  # noqa: BLE001 - Ollama off is a normal state
        ok = False
    _available_cache[model] = (now, ok)
    return ok


LEVELS = {
    "crianca": "Fale como para uma criança de 10 anos: frases curtas, exemplos do dia a dia.",
    "enem": "Fale como para um estudante do ensino médio se preparando para o ENEM.",
    "faculdade": "Fale como para um universitário: rigor técnico e termos corretos da área.",
}
ASSESSMENTS = {"correto", "parcial", "equivoco", "nao_mencionou"}


def _ask(model: str, prompt: str, timeout: float) -> dict:
    payload = {
        "model": model,
        "system": SYSTEM,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.3, "num_predict": 320},
    }
    with httpx.Client(trust_env=False, timeout=timeout) as client:
        response = client.post(f"{OLLAMA}/api/generate", json=payload)
        response.raise_for_status()
    data = json.loads(response.json()["response"])
    if not isinstance(data, dict):
        raise ValueError("resposta nao e objeto JSON")
    return data


def _text(data: dict, key: str, limit: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"campo ausente: {key}")
    return _short(value, limit)


def _assessment(data: dict) -> str:
    value = str(data.get("assessment", "")).strip().lower()
    return value if value in ASSESSMENTS else "parcial"


def warm_up(model: str) -> bool:
    """Load the model into memory so the first question does not time out."""
    if not available(model):
        return False
    try:
        with httpx.Client(trust_env=False, timeout=180) as client:
            client.post(f"{OLLAMA}/api/generate",
                        json={"model": model, "prompt": "", "keep_alive": "30m"})
        return True
    except Exception:  # noqa: BLE001
        return False


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
        f"grafia): {transcript[:1500] or '(nada)'}\n"
        f"{('Histórico: ' + history) if history else ''}\n\n"
        "1) Avalie pelo SIGNIFICADO (paráfrases valem) se a fala explica ESTE "
        "ponto da missão (não outro ponto do material): assessment = correto, "
        "parcial, equivoco (disse algo errado) ou nao_mencionou.\n"
        "2) Se houver equívoco, descreva-o em misconception (senão, string vazia).\n"
        "3) Escreva UMA pergunta curta: se houve equívoco, leve o estudante a "
        "perceber o erro; senão, pergunte sobre o que faltou; se estava correto, "
        "aprofunde (por quê? exemplo? consequência?).\n"
        "4) Escreva três dicas graduais, sem entregar a resposta, CADA UMA com no "
        "máximo 100 caracteres: hint1 = pista leve; hint2 = analogia curta; "
        "hint3 = começo de um exemplo.\n"
        'JSON: {"assessment": "...", "misconception": "...", "question": "<até 120 '
        'caracteres>", "hint1": "Dica: ...", "hint2": "Dica: ...", "hint3": "Dica: ..."}'
    )
    data = _ask(model, prompt, timeout)
    hints = [_text(data, "hint1", LIMITS["hint"])]
    for key in ("hint2", "hint3"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            hints.append(_short(value, LIMITS["hint"]))
    return {
        "assessment": _assessment(data),
        "misconception": _short(data.get("misconception") or "", 160),
        "question": _text(data, "question", LIMITS["question"]),
        "hint": hints[0],
        "hints": hints,
    }


def second_turn(point: str, question: str, first: str, second: str, model: str, *,
                level: str = "enem", timeout: float = 40.0) -> dict:
    """Return {"comparison", "assessment"} for the second explanation."""
    prompt = (
        f"{LEVELS.get(level, LEVELS['enem'])}\n"
        f"Ponto da missão: {point}\nPergunta feita: {question}\n"
        f"1ª explicação: {first[:1200] or '(nada)'}\n"
        f"2ª explicação: {second[:1200] or '(nada)'}\n\n"
        "Avalie a 2ª explicação pelo SIGNIFICADO: assessment = correto, parcial, "
        "equivoco ou nao_mencionou. Em UMA frase curta diga o que melhorou e, se "
        "houver, o que ainda falta ou está errado, em NO MÁXIMO 85 caracteres. "
        "Seja específica ao conteúdo (evite 'explicação clara'); não dê nota.\n"
        'JSON: {"assessment": "...", "comparison": "<até 90 caracteres>"}'
    )
    data = _ask(model, prompt, timeout)
    return {"comparison": _text(data, "comparison", LIMITS["comparison"]),
            "assessment": _assessment(data)}
