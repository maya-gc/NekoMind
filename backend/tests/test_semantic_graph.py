"""The local model may link concepts, but evidence and labels stay bounded."""

import pytest

from app.services import semantic_graph


class FakeResponse:
    def __init__(self, result):
        self.result = result

    def raise_for_status(self):
        pass

    def json(self):
        return {"response": self.result}


class FakeClient:
    def __init__(self, result, calls):
        self.result, self.calls = result, calls

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def post(self, url, *, json):
        self.calls.append((url, json))
        return FakeResponse(self.result)


def test_local_graph_links_verbatim_source_and_speech_without_claiming_truth(monkeypatch):
    calls = []
    monkeypatch.setattr(semantic_graph.httpx, "Client", lambda **kw: FakeClient(
        '{"edges":[{"point":0,"speech":0,"relation":"related"}]}', calls
    ))
    points = ["A maçã é uma fruta. A abobrinha é um legume."]
    speech = "Maçã e abobrinha são alimentos."
    graph = semantic_graph.build_semantic_graph(points, speech, "qwen2.5:3b")
    assert graph["status"] == "completed"
    assert graph["edges"] == [{
        "point_index": 0,
        "speech_excerpt": speech,
        "relation": "related",
    }]
    assert "não comprovam" in graph["disclaimer"]
    assert calls[0][0] == semantic_graph.OLLAMA_URL
    assert points[0] in calls[0][1]["prompt"] and speech in calls[0][1]["prompt"]


@pytest.mark.parametrize("result", [
    '{"edges":[{"point":99,"speech":0,"relation":"related"}]}',
    '{"edges":[{"point":true,"speech":0,"relation":"related"}]}',
    '{"edges":[{"point":0,"speech":0,"relation":"agrees"}]}',
    '{"edges":[{"point":0,"speech":0,"relation":"related"},{"point":0,"speech":0,"relation":"related"}]}',
])
def test_graph_rejects_ungrounded_or_invalid_edges(monkeypatch, result):
    monkeypatch.setattr(semantic_graph.httpx, "Client", lambda **kw: FakeClient(result, []))
    with pytest.raises(semantic_graph.SemanticGraphError):
        semantic_graph.build_semantic_graph(["A maçã é uma fruta."], "Eu falei de maçã.", "qwen2.5:3b")
