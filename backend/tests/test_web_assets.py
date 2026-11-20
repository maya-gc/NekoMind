def test_local_web_assets_are_current_and_never_cached(client):
    for route in ("/touch", "/public", "/presenter"):
        response = client.get(route)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "brand-lumi-1" in response.text

    render = client.get("/web/src/render.mjs?v=brand-lumi-1")
    assert render.status_code == 200
    assert render.headers["cache-control"] == "no-store, max-age=0"
    assert "Rosto de Lumi" in render.text
    assert "cat-spark" in render.text
    assert "cat-bow" not in render.text

    styles = client.get("/web/styles.css?v=brand-lumi-1")
    assert styles.status_code == 200
    assert styles.headers["cache-control"] == "no-store, max-age=0"
    assert ".cat-spark" in styles.text
    assert ".cat-bow" not in styles.text
