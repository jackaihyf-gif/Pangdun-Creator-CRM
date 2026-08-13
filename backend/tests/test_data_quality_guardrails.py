from backend.app.media_taxonomy import normalize_media_payload
from backend.app.profile_links import canonical_profile_url, clean_profile_links


def test_taxonomy_normalizes_country_status_and_profile():
    normalized = normalize_media_payload({"name": "Creator", "country": "USA", "cooperation_status": "待核验"})
    assert normalized["country"] == "美国"
    assert normalized["country_code"] == "US"
    assert normalized["cooperation_status"] == "未联系"
    assert normalized["verification_status"] == "待核验"
    assert canonical_profile_url("twitter.com/Example/?utm_source=test") == "https://x.com/example"
    assert clean_profile_links(None, "instagram.com/Example")[0]["url"] == "https://instagram.com/example"


def test_media_contact_and_product_identities_are_unique(client, seeded_collaboration):
    headers = seeded_collaboration["headers"]
    first = client.post("/api/media", headers=headers, json={"name": "Alpha", "country": "US", "website_url": "https://instagram.com/Alpha/?ref=one"})
    assert first.status_code == 200
    duplicate = client.post("/api/media", headers=headers, json={"name": "Alpha copy", "country": "美国", "website_url": "https://www.instagram.com/alpha/"})
    assert duplicate.status_code == 409

    contact = client.post("/api/contacts", headers=headers, json={"media_id": first.json()["id"], "name": "Alex", "email": "Alex@Example.com"})
    assert contact.status_code == 200
    contact_duplicate = client.post("/api/contacts", headers=headers, json={"media_id": seeded_collaboration["media_id"], "name": "Other", "email": " alex@example.com "})
    assert contact_duplicate.status_code == 409

    product = client.post("/api/products", headers=headers, json={"model": "Z890-A", "aliases": "Z890 Alpha"})
    assert product.status_code == 200
    product_duplicate = client.post("/api/products", headers=headers, json={"model": "Other", "aliases": "z890-alpha"})
    assert product_duplicate.status_code == 409


def test_review_queue_only_contains_actionable_issues(client, seeded_collaboration):
    headers = seeded_collaboration["headers"]
    complete = client.post("/api/media", headers=headers, json={"name": "Complete Creator", "country": "US", "website_url": "https://youtube.com/@complete"})
    assert complete.status_code == 200
    assert client.post("/api/contacts", headers=headers, json={"media_id": complete.json()["id"], "name": "Alex", "email": "alex@complete.test"}).status_code == 200

    flagged = client.post("/api/media", headers=headers, json={"name": "Broken Profile", "country": "US", "website_url": "https://youtube.com/@broken", "notes": "[数据核验] 主页链接返回 404。"})
    assert flagged.status_code == 200
    assert client.post("/api/contacts", headers=headers, json={"media_id": flagged.json()["id"], "name": "Sam", "email": "sam@broken.test"}).status_code == 200

    queue = client.get("/api/media-review-queue", headers=headers).json()
    queued_ids = {item["id"] for item in queue["items"]}
    assert complete.json()["id"] not in queued_ids
    assert seeded_collaboration["media_id"] in queued_ids
    assert flagged.json()["id"] in queued_ids
    assert queue["category_counts"] == {"contact": 1, "profile": 1, "conflict": 0}

    resolved = client.post(f"/api/media-review-queue/{flagged.json()['id']}/resolve", headers=headers, json={})
    assert resolved.status_code == 200
    assert flagged.json()["id"] not in {item["id"] for item in client.get("/api/media-review-queue", headers=headers).json()["items"]}
