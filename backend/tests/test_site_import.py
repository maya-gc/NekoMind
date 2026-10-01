"""Public URL preview is bounded, locally parsed and never auto-saved."""

import socket

from app.services import site_import


def _public_dns(monkeypatch):
    monkeypatch.setattr(
        site_import.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", port))
        ],
    )


def test_site_preview_suggests_source_grounded_points_without_saving(client, monkeypatch):
    _public_dns(monkeypatch)
    monkeypatch.setattr(
        site_import,
        "_load",
        lambda target: (
            200,
            {"content-type": "text/html; charset=utf-8"},
            b"".join(
                [
                    b"<html><head><title>Ciclo da agua</title><script>segredo()</script></head>",
                    b"<body><nav>Menu falso.</nav><main><h1>Agua</h1>",
                    b"<p>A chuva forma rios. O sol evapora agua.</p></main></body></html>",
                ]
            ),
        ),
    )
    response = client.post(
        "/api/v1/contents/import-url", json={"url": "https://example.org/artigo"}
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["title"] == "Ciclo da agua"
    assert preview["source"] == "url"
    assert "A chuva forma rios." in preview["points"]
    assert "segredo" not in preview["text"] and "Menu falso" not in preview["text"]
    assert client.get("/api/v1/contents").json() == []


def test_site_preview_rejects_internal_targets_and_redirects(client, monkeypatch):
    url = "/api/v1/contents/import-url"
    assert (
        client.post(
            url, headers={"Authorization": ""}, json={"url": "https://example.org"}
        ).status_code
        == 401
    )
    for target in (
        "http://127.0.0.1/",
        "http://192.168.1.2/",
        "file:///etc/passwd",
        "https://example.org:8443/",
        "https://user:pass@example.org/",
    ):
        assert client.post(url, json={"url": target}).status_code == 422

    _public_dns(monkeypatch)
    monkeypatch.setattr(
        site_import, "_load", lambda target: (302, {"location": "http://127.0.0.1/private"}, b"")
    )
    assert client.post(url, json={"url": "https://example.org"}).status_code == 422

    monkeypatch.setattr(
        site_import.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port)),
        ],
    )
    assert client.post(url, json={"url": "https://example.org"}).status_code == 422


def test_pasted_text_preview_keeps_review_separate_from_save(client):
    response = client.post(
        "/api/v1/contents/prepare-text",
        json={"text": "A água cai como chuva. O sol evapora a água."},
    )
    assert response.status_code == 200
    assert response.json()["points"] == ["A água cai como chuva.", "O sol evapora a água."]
    assert client.get("/api/v1/contents").json() == []
