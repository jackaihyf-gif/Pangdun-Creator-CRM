from backend.app.media_taxonomy import normalize_media_payload
from backend.app.profile_links import canonical_profile_url, clean_profile_links, profile_identity


def test_taxonomy_normalizes_country_status_and_profile():
    normalized = normalize_media_payload({"name": "Creator", "country": "USA", "cooperation_status": "待核验"})
    assert normalized["country"] == "美国"
    assert normalized["country_code"] == "US"
    assert normalized["cooperation_status"] == "未联系"
    assert normalized["verification_status"] == "待核验"
    assert canonical_profile_url("twitter.com/Example/?utm_source=test") == "https://x.com/example"
    assert clean_profile_links(None, "instagram.com/Example")[0]["url"] == "https://instagram.com/example"
    assert profile_identity("https://youtube.com/watch?v=example") is None


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
    assert queue["category_counts"] == {"duplicate": 0, "contact": 1, "profile": 1, "conflict": 0, "source": 0, "stale": 0, "confidence": 0}

    resolved = client.post(f"/api/media-review-queue/{flagged.json()['id']}/resolve", headers=headers, json={})
    assert resolved.status_code == 200
    assert flagged.json()["id"] not in {item["id"] for item in client.get("/api/media-review-queue", headers=headers).json()["items"]}


def test_media_merge_preserves_history_and_delete_is_guarded(client, seeded_collaboration):
    headers = seeded_collaboration["headers"]
    target = client.post("/api/media", headers=headers, json={"name": "Canonical Creator", "country": "US", "website_url": "https://youtube.com/@canonical"})
    assert target.status_code == 200
    assert client.post("/api/contacts", headers=headers, json={"media_id": target.json()["id"], "name": "Owner", "email": "owner@canonical.test"}).status_code == 200

    merged = client.post(f"/api/media/{seeded_collaboration['media_id']}/merge", headers=headers, json={"target_media_id": target.json()["id"]})
    assert merged.status_code == 200
    assert merged.json()["campaigns"] == 1
    assert client.get(f"/api/media/{seeded_collaboration['media_id']}", headers=headers).status_code == 404
    detail = client.get(f"/api/media/{target.json()['id']}", headers=headers).json()
    assert [campaign["id"] for campaign in detail["campaigns"]] == [seeded_collaboration["campaign_id"]]

    guarded = client.delete(f"/api/media/{target.json()['id']}", headers=headers)
    assert guarded.status_code == 409
    assert guarded.json()["detail"]["counts"] == {"campaigns": 1, "contacts": 1, "addresses": 0}

    empty = client.post("/api/media", headers=headers, json={"name": "Disposable Creator", "country": "US"})
    assert empty.status_code == 200
    assert client.delete(f"/api/media/{empty.json()['id']}", headers=headers).status_code == 200


def test_quality_center_groups_duplicates_sources_and_can_snooze(client, seeded_collaboration):
    headers = seeded_collaboration["headers"]
    first = client.post("/api/media", headers=headers, json={"name": "Piscumo", "country": "韩国", "platform_type": "科技媒体 / 网站", "followers_or_traffic": 120})
    second = client.post("/api/media", headers=headers, json={"name": "Piscomu", "country": "韩国", "platform_type": "科技媒体 / 网站"})
    assert first.status_code == 200 and second.status_code == 200

    queue = client.get("/api/media-review-queue", headers=headers).json()
    first_row = next(item for item in queue["items"] if item["id"] == first.json()["id"])
    assert {"possible_duplicate", "missing_source"}.issubset(first_row["issue_codes"])
    assert queue["category_counts"]["duplicate"] >= 2
    assert queue["category_counts"]["source"] >= 1

    blocked = client.post("/api/media-review-queue/batch", headers=headers, json={"media_ids": [first.json()["id"]], "action": "resolve"})
    assert blocked.status_code == 200
    assert blocked.json()["changed"] == 0
    assert len(blocked.json()["skipped"]) == 1

    snoozed = client.post("/api/media-review-queue/batch", headers=headers, json={"media_ids": [first.json()["id"]], "action": "snooze", "snooze_days": 30})
    assert snoozed.status_code == 200
    assert snoozed.json()["changed"] == 1
    assert first.json()["id"] not in {item["id"] for item in client.get("/api/media-review-queue", headers=headers).json()["items"]}


def test_media_update_audit_can_be_restored(client, seeded_collaboration):
    headers = seeded_collaboration["headers"]
    media_id = seeded_collaboration["media_id"]
    original = client.get(f"/api/media/{media_id}", headers=headers).json()["media"]
    changed = {**original, "name": "Changed Creator", "data_source": "Media Kit", "data_capture_method": "manual", "data_confidence": 1, "last_verified_at": "2026-08-13"}
    assert client.put(f"/api/media/{media_id}", headers=headers, json=changed).status_code == 200
    logs = client.get(f"/api/audit-logs?entity_type=media&entity_id={media_id}", headers=headers).json()["items"]
    update_log = next(item for item in logs if item["action"] == "update")
    restored = client.post(f"/api/audit-logs/{update_log['id']}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["name"] == original["name"]
