"""Testes do health check."""


def test_health_ok(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "nekomind-backend"
    assert body["asr_provider"] == "mock"
    assert body["llm_provider"] == "mock"
