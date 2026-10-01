"""Local model chooses only grounded source sentences and never saves a preview."""

import httpx

from app.services import briefing_ai


class FakeResponse:
    def __init__(self, result):
        self.result = result

    def raise_for_status(self):
        return None

    def json(self):
        return {"response": self.result}


class FakeClient:
    def __init__(self, result, calls):
        self.result, self.calls = result, calls

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def post(self, url, *, json):
        self.calls.append((url, json))
        return FakeResponse(self.result)


def test_local_ai_returns_only_selected_source_sentences(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        briefing_ai.httpx, "Client", lambda **kw: FakeClient('{"indices":[1]}', calls)
    )
    text = "A chuva forma rios. O sol evapora a água. As nuvens trazem chuva."
    response = client.post("/api/v1/contents/analyze-briefing", json={"text": text})
    assert response.status_code == 200, response.text
    assert response.json()["points"] == ["O sol evapora a água."]
    assert response.json()["provider"] == "ollama_local"
    assert calls[0][0] == briefing_ai.OLLAMA_URL
    assert calls[0][1]["model"] == "qwen2.5:3b"
    assert client.get("/api/v1/contents").json() == []


def test_ai_rejects_overlong_or_unusable_text_before_model_call(client, monkeypatch):
    def unexpected_client(**kwargs):
        raise AssertionError("model must not be called")

    monkeypatch.setattr(briefing_ai.httpx, "Client", unexpected_client)
    url = "/api/v1/contents/analyze-briefing"
    assert client.post(url, json={"text": "A" * 12001}).status_code == 422
    assert client.post(url, json={"text": "..."}).status_code == 422


def test_ai_failure_and_invalid_output_do_not_fall_back(client, monkeypatch):
    url = "/api/v1/contents/analyze-briefing"
    assert (
        client.post(
            url, headers={"Authorization": ""}, json={"text": "A chuva forma rios."}
        ).status_code
        == 401
    )
    for result in (
        '{"indices":[99]}',
        '{"indices":[0,0]}',
        '{"indices":[true]}',
        '{"invented":"x"}',
    ):
        monkeypatch.setattr(
            briefing_ai.httpx, "Client", lambda result=result, **kw: FakeClient(result, [])
        )
        assert client.post(url, json={"text": "A chuva forma rios."}).status_code == 422

    class Unavailable(FakeClient):
        def post(self, url, *, json):
            raise httpx.ConnectError("not running")

    monkeypatch.setattr(briefing_ai.httpx, "Client", lambda **kw: Unavailable("", []))
    assert client.post(url, json={"text": "A chuva forma rios."}).status_code == 422
    assert client.get("/api/v1/contents").json() == []
