def test_favicon_assets_are_served_with_image_types(client):
    icon = client.get("/favicon.ico")
    png = client.get("/favicon.png")

    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/x-icon")
    assert icon.content[:4] == b"\x00\x00\x01\x00"
    assert png.status_code == 200
    assert png.headers["content-type"].startswith("image/png")
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"
