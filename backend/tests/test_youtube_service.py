from datetime import date

import httpx
import pytest

from backend.app.youtube_service import (
    YouTubeChannel,
    fetch_youtube_channel,
    is_youtube_url,
    merge_youtube_proposal,
)


def channel_payload(*, hidden: bool = False) -> dict:
    statistics = {"viewCount": "1234567", "videoCount": "321", "hiddenSubscriberCount": hidden}
    if not hidden:
        statistics["subscriberCount"] = "15700000"
    return {
        "items": [{
            "id": "UC123",
            "snippet": {
                "title": "Example Tech",
                "description": "Business: hello@example.test",
                "customUrl": "@exampletech",
                "country": "CA",
            },
            "statistics": statistics,
        }]
    }


def test_youtube_channel_handle_uses_official_api(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/channels")
        assert request.url.params["forHandle"] == "@exampletech"
        assert request.url.params["part"] == "snippet,statistics"
        return httpx.Response(200, json=channel_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_youtube_channel("https://youtube.com/@exampletech/videos", client)
    assert result.title == "Example Tech"
    assert result.country == "CA"
    assert result.followers_k == 15700
    assert result.canonical_url == "https://youtube.com/@exampletech"


def test_youtube_video_url_resolves_its_channel(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/videos"):
            assert request.url.params["id"] == "abc123"
            return httpx.Response(200, json={"items": [{"snippet": {"channelId": "UC123"}}]})
        assert request.url.params["id"] == "UC123"
        return httpx.Response(200, json=channel_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_youtube_channel("https://youtu.be/abc123", client)
    assert calls == ["/youtube/v3/videos", "/youtube/v3/channels"]
    assert result.channel_id == "UC123"


def test_youtube_proposal_overrides_model_guesses_with_provenance():
    channel = YouTubeChannel(
        channel_id="UC123", title="Official Name", description="", canonical_url="https://youtube.com/@official",
        country="US", subscribers=1234000, subscribers_hidden=False, view_count=10, video_count=2,
    )
    proposal = merge_youtube_proposal({
        "media": {"name": "Model Guess", "followers_or_traffic": 99},
        "evidence": {}, "confidence": {}, "warnings": [],
    }, channel)
    assert proposal["media"]["name"] == "Official Name"
    assert proposal["media"]["followers_or_traffic"] == 1234
    assert proposal["media"]["metric_source"] == "YouTube Data API v3"
    assert proposal["media"]["metric_verified_at"] == date.today().isoformat()
    assert proposal["media"]["profile_links"][0]["source"] == "YouTube Data API v3"
    assert proposal["confidence"]["media.followers_or_traffic"] == 1


def test_youtube_merge_recounts_missing_evidence_after_official_fields():
    channel = YouTubeChannel(
        channel_id="UC123", title="Official Name", description="", canonical_url="https://youtube.com/@official",
        country=None, subscribers=1000, subscribers_hidden=False, view_count=None, video_count=None,
    )
    proposal = merge_youtube_proposal({
        "media": {"name": "Model Guess", "notes": "Uncited note"},
        "contacts": [], "evidence": {}, "confidence": {},
        "warnings": ["2 个字段缺少原文证据，写入前必须人工核对"],
    }, channel)
    assert "1 个字段缺少原文证据，写入前必须人工核对" in proposal["warnings"]
    assert not any(warning.startswith("2 个字段缺少") for warning in proposal["warnings"])


@pytest.mark.parametrize("url", [
    "https://youtube.com/@example", "https://www.youtube.com/channel/UC123", "https://youtu.be/abc123",
])
def test_youtube_url_detection(url):
    assert is_youtube_url(url)


def test_hidden_subscribers_do_not_create_a_metric(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=channel_payload(hidden=True)))) as client:
        channel = fetch_youtube_channel("https://youtube.com/@exampletech", client)
    proposal = merge_youtube_proposal({"media": {}, "evidence": {}, "confidence": {}, "warnings": []}, channel)
    assert channel.followers_k is None
    assert "followers_or_traffic" not in proposal["media"]
    assert any("隐藏" in warning for warning in proposal["warnings"])
