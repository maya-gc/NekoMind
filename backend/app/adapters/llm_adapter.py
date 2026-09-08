"""Adaptador de LLM (extracao de topicos e analise qualitativa).

Interface unica `LLMAdapter` com implementacao mock por padrao (offline,
sem chave de API). O mock retorna topicos ficticios marcados como
demonstracao, suficientes para exercitar pipeline, banco e frontend.

Para usar uma API externa, defina NEKOMIND_LLM_PROVIDER e
NEKOMIND_LLM_API_KEY no .env (nunca versione a chave).
"""
from __future__ import annotations


class LLMAdapter:
    """Contrato: recebe transcricao e extrai topicos + observacoes."""

    def extract_topics(self, transcription: str) -> list[dict]:  # pragma: no cover
        raise NotImplementedError


class MockLLMAdapter(LLMAdapter):
    """Implementacao de demonstracao (sem IA real)."""

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


class ExternalLLMAdapter(LLMAdapter):
    """Ponto de extensao para uma API de LLM (nao usado no MVP)."""

    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model

    def extract_topics(self, transcription: str) -> list[dict]:  # pragma: no cover
        raise NotImplementedError(
            "configure sua API de LLM aqui (OpenAI, Anthropic, local etc.)"
        )


def get_llm_adapter(provider: str = "mock", api_key: str = "") -> LLMAdapter:
    if provider != "mock" and api_key:
        return ExternalLLMAdapter(api_key=api_key)
    return MockLLMAdapter()
