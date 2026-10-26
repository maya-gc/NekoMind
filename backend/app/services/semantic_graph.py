"""Build an evidence-linked concept graph with a local model.

Edges are tentative relations between source points and verbatim speech spans;
they are not a factual correctness or mastery score.
"""

from __future__ import annotations

import json
import re

import httpx

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
RELATIONS = {"related", "support_hint", "conflict_hint"}
MAX_SPEECH_NODES = 40
MAX_EDGES = 12
METHOD = "local-relation-graph-v1"


class SemanticGraphError(ValueError):
    pass


def _speech_nodes(transcript: str) -> tuple[list[str], bool]:
    nodes: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", transcript):
        words = sentence.strip().split()
        while words:
            chunk = []
            length = 0
            while words and length + len(words[0]) + 1 <= 350:
                word = words.pop(0)
                chunk.append(word)
                length += len(word) + 1
            if not chunk:
                chunk.append(words.pop(0)[:350])
            nodes.append(" ".join(chunk))
    sampled = len(nodes) > MAX_SPEECH_NODES
    if sampled:
        nodes = [nodes[round(i * (len(nodes) - 1) / (MAX_SPEECH_NODES - 1))] for i in range(MAX_SPEECH_NODES)]
    return nodes, sampled


def build_semantic_graph(points: list[str], transcript: str, model: str) -> dict:
    speech, speech_sampled = _speech_nodes(transcript)
    if not points or not speech:
        return {"status": "unavailable", "method_version": METHOD, "edges": []}
    source_list = "\n".join(f"{index}: {point}" for index, point in enumerate(points[:30]))
    speech_list = "\n".join(f"{index}: {sentence}" for index, sentence in enumerate(speech))
    prompt = (
        "Construa um grafo bipartido entre pontos de um material de estudo e trechos "
        "da fala transcrita. Para cada ponto com relação clara, inclua uma aresta, "
        "até o máximo de 12 relações que tenham evidência nos dois lados. "
        "Use SOMENTE índices das listas. 'related' significa apenas tema "
        "conceitualmente próximo, como maçã/fruta e abobrinha/legume dentro de alimentos; "
        "não significa concordância. 'support_hint' é um possível alinhamento da afirmação; "
        "'conflict_hint' é uma possível oposição explícita. Em dúvida use related ou omita. "
        "Não use conhecimento externo para decidir se a fala é verdadeira. "
        'Responda SOMENTE JSON: {"edges":[{"point":0,"speech":0,"relation":"related"}]}.\n\n'
        f"Pontos da fonte:\n{source_list}\n\nFala:\n{speech_list}"
    )
    try:
        with httpx.Client(trust_env=False, timeout=30) as client:
            response = client.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0, "num_predict": 512},
                },
            )
        response.raise_for_status()
        raw = json.loads(response.json()["response"])["edges"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise SemanticGraphError("A análise conceitual local não respondeu.") from exc
    if not isinstance(raw, list) or len(raw) > MAX_EDGES:
        raise SemanticGraphError("A análise conceitual local retornou relações inválidas.")
    seen = set()
    edges = []
    for item in raw:
        if not isinstance(item, dict):
            raise SemanticGraphError("A análise conceitual local retornou relações inválidas.")
        p, s, relation = item.get("point"), item.get("speech"), item.get("relation")
        if (
            type(p) is not int or not 0 <= p < min(len(points), 30)
            or type(s) is not int or not 0 <= s < len(speech)
            or not isinstance(relation, str) or relation not in RELATIONS or (p, s) in seen
        ):
            raise SemanticGraphError("A análise conceitual local retornou relações inválidas.")
        seen.add((p, s))
        edges.append({
            "point_index": p,
            "speech_excerpt": speech[s],
            "relation": relation,
        })
    return {
        "status": "completed",
        "method_version": METHOD,
        "provider": "ollama_local",
        "model": model,
        "speech_sampled": speech_sampled,
        "edges": edges,
        "disclaimer": "Relações conceituais são indícios; não comprovam concordância factual nem domínio do conteúdo.",
    }
