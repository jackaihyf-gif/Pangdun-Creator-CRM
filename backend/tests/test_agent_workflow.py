import pytest

from backend.app.agent_service import AgentSourceError, normalize_agent_proposal, validate_public_url


def sample_proposal(profile_url: str) -> dict:
    return {
        "summary": "识别到媒体及商务联系人",
        "media": {
            "name": "Test Creator Updated",
            "country": "美国",
            "platform_type": "YouTube",
            "category": "硬件评测",
            "profile_links": [{"platform": "YouTube", "url": profile_url}],
            "followers_or_traffic": 125,
            "audience_metric_type": "followers",
            "cooperation_status": None,
            "notes": None,
        },
        "contacts": [{"name": "Alex", "role": "Business", "email": "alex@example.test", "phone": None, "whatsapp": None, "telegram": None}],
        "evidence": {
            "media.name": "Test Creator Updated",
            "media.category": "Hardware reviews",
            "media.profile_links": profile_url,
            "contacts.0.name": "Alex — Business",
            "contacts.0.email": "alex@example.test",
        },
        "confidence": {
            "media.name": 0.95,
            "media.category": 0.9,
            "media.profile_links": 1,
            "contacts.0.name": 0.9,
            "contacts.0.email": 1,
        },
        "warnings": [],
    }


def test_agent_proposal_caps_fields_without_evidence():
    result = normalize_agent_proposal({
        "media": {"name": "Creator", "country": "US"},
        "contacts": [],
        "evidence": {"media.name": "Creator"},
        "confidence": {"media.name": 1, "media.country": 1},
    }, "pasted text")
    assert result["confidence"]["media.name"] == 0.95
    assert result["confidence"]["media.country"] == 0.49
    assert any("缺少原文证据" in item for item in result["warnings"])


def test_agent_blocks_private_urls():
    with pytest.raises(AgentSourceError):
        validate_public_url("http://127.0.0.1:8000/api/users")
    with pytest.raises(AgentSourceError):
        validate_public_url("http://localhost/admin")


def test_agent_extract_preview_apply_and_reject(client, seeded_collaboration, monkeypatch):
    headers = seeded_collaboration["headers"]
    media_id = seeded_collaboration["media_id"]
    profile_url = "https://youtube.com/@testcreator"
    current = client.get(f"/api/media/{media_id}", headers=headers).json()["media"]
    current["profile_links"] = [{"platform": "YouTube", "url": profile_url}]
    current["website_url"] = profile_url
    assert client.put(f"/api/media/{media_id}", headers=headers, json=current).status_code == 200

    monkeypatch.setattr(
        "backend.app.main.deepseek_json_extract",
        lambda content, source: (normalize_agent_proposal(sample_proposal(profile_url), source), {"total_tokens": 321}),
    )
    extracted = client.post("/api/agent/extract", headers=headers, json={
        "input_type": "text",
        "content": "Test Creator Updated has 125K followers. Alex: alex@example.test",
        "source_label": "Media Kit 2026",
    })
    assert extracted.status_code == 200
    run = extracted.json()
    assert run["status"] == "proposed"
    assert run["proposal"]["suggested_target_media_id"] == media_id
    assert run["usage"]["total_tokens"] == 321

    applied = client.post(f"/api/agent/runs/{run['id']}/apply", headers=headers, json={
        "target_media_id": media_id,
        "selected_fields": ["media.category", "contacts.0.name", "contacts.0.email"],
    })
    assert applied.status_code == 200
    assert applied.json()["media"]["category"] == "硬件评测"
    assert applied.json()["media"]["data_capture_method"] == "agent"
    assert applied.json()["contacts_created"] == 1
    assert applied.json()["run"]["status"] == "applied"

    second = client.post("/api/agent/extract", headers=headers, json={
        "input_type": "text",
        "content": "Another sufficiently long source document for rejection.",
        "source_label": "Email",
    }).json()
    rejected = client.post(f"/api/agent/runs/{second['id']}/reject", headers=headers, json={"reason": "来源不是官方资料"})
    assert rejected.status_code == 200
    assert rejected.json()["run"]["status"] == "rejected"
