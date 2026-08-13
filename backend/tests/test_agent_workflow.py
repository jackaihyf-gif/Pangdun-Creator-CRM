from datetime import date

import pytest

from backend.app.agent_service import AgentSourceError, normalize_agent_proposal, validate_public_url
from backend.app.social_identity_service import SocialProfileIdentity
from backend.app.youtube_service import YouTubeChannel


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


def test_agent_youtube_url_uses_official_fields(client, seeded_collaboration, monkeypatch):
    headers = seeded_collaboration["headers"]
    channel = YouTubeChannel(
        channel_id="UC-OFFICIAL", title="Official Channel", description="Hardware reviews",
        canonical_url="https://youtube.com/@official", country="US", subscribers=250000,
        subscribers_hidden=False, view_count=123, video_count=12,
    )
    monkeypatch.setattr("backend.app.main.fetch_youtube_channel", lambda url: channel)
    monkeypatch.setattr(
        "backend.app.main.deepseek_json_extract",
        lambda content, source: (normalize_agent_proposal({
            "media": {"name": "Wrong model name", "category": "硬件评测"},
            "contacts": [],
            "evidence": {"media.name": "Wrong model name", "media.category": "Hardware reviews"},
            "confidence": {"media.name": .9, "media.category": .9},
        }, source), {"total_tokens": 20}),
    )
    response = client.post("/api/agent/extract", headers=headers, json={
        "input_type": "url", "content": "https://youtube.com/@official",
    })
    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["media"]["name"] == "Official Channel"
    assert proposal["media"]["followers_or_traffic"] == 250
    assert proposal["media"]["metric_source"] == "YouTube Data API v3"
    assert proposal["provider"] == "youtube_data_api"

    applied = client.post(f"/api/agent/runs/{response.json()['id']}/apply", headers=headers, json={
        "target_media_id": seeded_collaboration["media_id"],
        "selected_fields": ["media.followers_or_traffic", "media.metric_source", "media.metric_verified_at"],
    })
    assert applied.status_code == 200
    assert applied.json()["media"]["followers_or_traffic"] == 250
    assert applied.json()["media"]["metric_source"] == "YouTube Data API v3"
    assert applied.json()["media"]["metric_verified_at"] == date.today().isoformat()


def test_agent_tiktok_url_uses_lightweight_identity(client, seeded_collaboration, monkeypatch):
    headers = seeded_collaboration["headers"]
    identity = SocialProfileIdentity(
        platform="TikTok", display_name="Official TikTok Name",
        canonical_url="https://tiktok.com/@official", handle="official", source="TikTok 官方 oEmbed",
    )
    monkeypatch.setattr("backend.app.main.fetch_social_identity", lambda url: identity)
    monkeypatch.setattr(
        "backend.app.main.deepseek_json_extract",
        lambda content, source: (normalize_agent_proposal({
            "media": {"name": "Model Guess"}, "contacts": [],
            "evidence": {"media.name": "Model Guess"}, "confidence": {"media.name": .9},
        }, source), {"total_tokens": 12}),
    )
    response = client.post("/api/agent/extract", headers=headers, json={
        "input_type": "url", "content": "https://tiktok.com/@official",
    })
    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["media"]["name"] == "Official TikTok Name"
    assert proposal["media"]["profile_links"][0]["url"] == "https://tiktok.com/@official"
    assert proposal["provider"] == "tiktok_public_identity"
