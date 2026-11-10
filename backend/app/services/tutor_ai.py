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


def _ask(model: str, prompt: str, keys: tuple[str, ...], timeout: float) -> dict:
    payload = {
        "model": model,
        "system": SYSTEM,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.3, "num_predict": 220},
    }
    with httpx.Client(trust_env=False, timeout=timeout) as client:
        response = client.post(f"{OLLAMA}/api/generate", json=payload)
        response.raise_for_status()
    data = json.loads(response.json()["response"])
    out = {}
    for key in keys:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"campo ausente: {key}")
        out[key] = _short(value, LIMITS[key])
    return out


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
               timeout: float = 40.0) -> dict:
    """Return {"question", "hint"} about the gap in the first explanation."""
    prompt = (
        f"Material de estudo (contexto): {material[:1500]}\n\n"
        f"Ponto da missão: {point}\n"
        f"O que o estudante explicou (transcrição automática, pode ter erros): "
        f"{transcript[:1500] or '(nada)'}\n\n"
        "Compare a explicação com o ponto. Escreva UMA pergunta curta que leve o "
        "estudante a explicar a parte que faltou ou corrigir um equívoco, e UMA "
        "dica que oriente sem entregar a resposta.\n"
        'JSON: {"question": "<até 120 caracteres>", "hint": "Dica: <até 100 caracteres>"}'
    )
    return _ask(model, prompt, ("question", "hint"), timeout)


def second_turn(point: str, question: str, first: str, second: str, model: str, *,
                timeout: float = 40.0) -> dict:
    """Return {"comparison"}: what improved and what is still missing."""
    prompt = (
        f"Ponto da missão: {point}\nPergunta feita: {question}\n"
        f"1ª explicação: {first[:1200] or '(nada)'}\n"
        f"2ª explicação: {second[:1200] or '(nada)'}\n\n"
        "Diga em UMA frase curta o que melhorou na 2ª explicação e, se houver, o "
        "que ainda falta. Seja específica ao conteúdo; não dê nota.\n"
        'JSON: {"comparison": "<até 90 caracteres>"}'
    )
    return _ask(model, prompt, ("comparison",), timeout)
