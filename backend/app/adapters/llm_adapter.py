"""Topic extraction adapters.

The MVP keeps cloud/model selection open. It provides an explicit demo adapter
and a local deterministic extractor that never sends transcripts to the cloud.
"""

from __future__ import annotations

import re
import unicodedata

_WORD_RE = re.compile(r"\b[\wÀ-ÿ]{3,}\b", flags=re.UNICODE)
_STOPWORDS = {
    "aqui",
    "aquela",
    "aquele",
    "aquilo",
    "cada",
    "como",
    "com",
    "das",
    "dos",
    "de",
    "dela",
    "dele",
    "depois",
    "e",
    "ela",
    "ele",
    "eles",
    "em",
    "entre",
    "essa",
    "esse",
    "esta",
    "este",
    "explica",
    "explicam",
    "acho",
    "assim",
    "entao",
    "então",
    "formar",
    "gente",
    "gosta",
    "gostar",
    "gostava",
    "gosto",
    "isso",
    "mais",
    "mas",
    "nas",
    "nos",
    "para",
    "pela",
    "pelo",
    "por",
    "pouco",
    "quer",
    "quero",
    "que",
    "uma",
    "uso",
    "usa",
    "tipo",
    "eu",
}


class LLMAdapter:
    """Contrato: recebe transcricao e extrai topicos + observacoes."""

    provider = "unknown"
    is_demo = False

    def extract_topics(self, transcription: str) -> list[dict]:  # pragma: no cover
        raise NotImplementedError


class MockLLMAdapter(LLMAdapter):
    """Implementacao de demonstracao (sem IA real)."""

    provider = "mock"
    is_demo = True

    def extract_topics(self, transcription: str) -> list[dict]:
        return [
            {
                "name": "fotossintese",
                "relevance": 0.95,
                "notes": "[DEMO] Topico central da explicacao simulada.",
            },
            {
                "name": "respiracao celular",
                "relevance": 0.6,
                "notes": "[DEMO] Comparacao mencionada na demonstracao.",
            },
            {
                "name": "ciclo do carbono",
                "relevance": 0.4,
                "notes": "[DEMO] Topico relacionado, sugerido para revisao.",
            },
        ]


class LocalKeywordTopicAdapter(LLMAdapter):
    """Extract transcript-grounded keyword topics without fixed padding."""

    provider = "local_keywords"

    def extract_topics(self, transcription: str) -> list[dict]:
        """Rank literal phrases separated by stopwords/punctuation (RAKE-style).

        This is an opt-in deterministic candidate, not an approved AI model.
        Every output name is a contiguous span of this transcript. No padding.
        """
        if not isinstance(transcription, str) or not transcription.strip():
            raise ValueError("Transcricao vazia ou invalida")
        from collections import Counter

        stops = _STOPWORDS | {
            "a",
            "o",
            "as",
            "os",
            "um",
            "uns",
            "umas",
            "ao",
            "aos",
            "da",
            "do",
            "no",
            "na",
            "se",
            "ser",
            "sao",
            "foi",
            "e",
            "é",
            "sobre",
            "tem",
            "ter",
            "ate",
            "ou",
            "porque",
            "portanto",
            "exemplo",
            "explicar",
            "explica",
            "explicado",
            "vou",
            "hoje",
            "falar",
            "assunto",
        }
        candidates = []
        current = []
        for token in re.findall(r"[^\W\d_]+|[^\w\s]", transcription, re.UNICODE):
            if not token.isalpha() or _normalize(token) in stops:
                if current:
                    candidates.append(current)
                    current = []
            else:
                current.append(token)
                if len(current) == 4:
                    candidates.append(current)
                    current = []
        if current:
            candidates.append(current)
        frequency, degree = Counter(), Counter()
        for phrase in candidates:
            for word in map(_normalize, phrase):
                frequency[word] += 1
                degree[word] += len(phrase)
        ranked = {}
        for phrase in candidates:
            name = " ".join(phrase)
            key = _normalize(name)
            if len(name) > 200:
                continue
            score = sum(degree[_normalize(word)] / frequency[_normalize(word)] for word in phrase)
            if key not in ranked:
                ranked[key] = (name, score)
        choices = []
        for name, score in sorted(ranked.values(), key=lambda item: -item[1]):
            words = tuple(_normalize(word) for word in name.split())
            word_set = set(words)
            if len(words) == 1 and len(words[0]) < 6 and frequency[words[0]] == 1:
                continue
            if any(word_set < set(_normalize(chosen).split()) for chosen, _ in choices):
                continue
            choices.append((name, score))
            if len(choices) == 5:
                break
        peak = max((score for _, score in choices), default=1)
        return [
            {
                "name": name,
                "relevance": round(score / peak, 3),
                "notes": "Expressao presente na transcricao; relevancia lexical, sem verificacao factual.",
            }
            for name, score in choices
        ]


def get_llm_adapter(provider: str = "mock", api_key: str = "") -> LLMAdapter:
    if provider == "mock":
        return MockLLMAdapter()
    if provider == "local_keywords":
        return LocalKeywordTopicAdapter()
    if api_key:
        raise ValueError(f"Provedor de topicos desconhecido ou nao implementado: {provider}")
    raise ValueError(f"Provedor de topicos desconhecido: {provider}")


def _normalize(value: str) -> str:
    value = value.lower().strip()
    value = "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )
    return value
