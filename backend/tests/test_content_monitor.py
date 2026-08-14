from datetime import datetime, timedelta

import httpx

from backend.app.content_monitor_service import description_has_tag, run_content_monitor
from backend.app.database import SessionLocal
from backend.app.models import Campaign, Deliverable, DeliverablePerformanceSnapshot, Media


def youtube_transport(state: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        part = request.url.params.get("part")
        state.setdefault("calls", []).append((path, part))
        if path.endswith("/channels") and part == "snippet,statistics":
            return httpx.Response(200, json={"items": [{
                "id": "UC-MONITOR-1",
                "snippet": {"title": "Test Creator", "customUrl": "@testcreator"},
                "statistics": {"subscriberCount": "1000", "viewCount": "9000", "videoCount": "20"},
            }]})
        if path.endswith("/channels") and part == "contentDetails":
            return httpx.Response(200, json={"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU-MONITOR-1"}}}]})
        if path.endswith("/playlistItems"):
            return httpx.Response(200, json={"items": [{"contentDetails": {"videoId": "video-monitor-1"}}]})
        if path.endswith("/videos"):
            return httpx.Response(200, json={"items": [{
                "id": "video-monitor-1",
                "snippet": {
                    "channelId": "UC-MONITOR-1",
                    "title": "Pangdun collaboration",
                    "description": "Thanks to our partner #Pangdun for supporting this video.",
                    "publishedAt": state["published_at"],
                },
                "statistics": {"viewCount": state["views"], "likeCount": "120", "commentCount": "15"},
            }]})
        return httpx.Response(404, json={})
    return httpx.MockTransport(handler)


def configure_media_profile(media_id: int, campaign_id: int):
    with SessionLocal() as db:
        media = db.get(Media, media_id)
        campaign = db.get(Campaign, campaign_id)
        media.profile_links = [{"platform": "YouTube", "url": "https://youtube.com/@testcreator"}]
        media.platform_type = "YouTube"
        campaign.expected_publish_date = datetime(2026, 8, 14).date()
        campaign.project.collaboration_tag = "#Pangdun"
        db.commit()


def test_exact_standard_tag_does_not_match_longer_hashtag():
    assert description_has_tag("Sponsored by #Pangdun", "#Pangdun")
    assert description_has_tag("sponsored by #pangdun!", "#Pangdun")
    assert not description_has_tag("Sponsored by #PangdunPlus", "#Pangdun")


def test_monitor_matches_once_and_stops_after_day_three(seeded_collaboration, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_COLLABORATION_TAG", "#Pangdun")
    configure_media_profile(seeded_collaboration["media_id"], seeded_collaboration["campaign_id"])
    published = datetime(2026, 8, 14, 0, 0, 0)
    state = {"published_at": "2026-08-14T00:00:00Z", "views": "1000"}
    with httpx.Client(transport=youtube_transport(state)) as client, SessionLocal() as db:
        first = run_content_monitor(db, client, published + timedelta(hours=10))
        assert first["matched"] == 1
        item = db.query(Deliverable).one()
        assert item.matched_tag == "#Pangdun"
        assert item.monitoring_status == "waiting_day_1"
        assert [row.sample_kind for row in item.performance_snapshots] == ["discovery"]

        state["views"] = "2500"
        second = run_content_monitor(db, client, published + timedelta(hours=26))
        db.refresh(item)
        assert second["updated"] == 1
        assert item.monitoring_status == "waiting_day_3"

        state["views"] = "7200"
        third = run_content_monitor(db, client, published + timedelta(hours=75))
        db.refresh(item)
        assert third["updated"] == 1
        assert item.monitoring_status == "completed"
        assert item.views == 7200
        samples = {row.sample_kind: row for row in db.query(DeliverablePerformanceSnapshot).all()}
        assert samples["day_1"].views == 2500
        assert samples["day_3"].views == 7200

        state["views"] = "12000"
        fourth = run_content_monitor(db, client, published + timedelta(hours=100))
        db.refresh(item)
        assert fourth["updated"] == 0
        assert item.views == 7200
        assert state["calls"].count(("/youtube/v3/channels", "snippet,statistics")) == 1
        assert state["calls"].count(("/youtube/v3/channels", "contentDetails")) == 1


def test_monitor_does_not_guess_when_media_has_multiple_active_campaigns(seeded_collaboration, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_COLLABORATION_TAG", "#Pangdun")
    configure_media_profile(seeded_collaboration["media_id"], seeded_collaboration["campaign_id"])
    with SessionLocal() as db:
        db.add(Campaign(media_id=seeded_collaboration["media_id"], project_id=seeded_collaboration["project_id"], execution_status="内容审核中", expected_publish_date=datetime(2026, 8, 14).date()))
        db.commit()
    state = {"published_at": "2026-08-14T00:00:00Z", "views": "1000"}
    with httpx.Client(transport=youtube_transport(state)) as client, SessionLocal() as db:
        result = run_content_monitor(db, client, datetime(2026, 8, 14, 10, 0, 0))
        assert result["matched"] == 0
        assert result["conflicts"] == 1
        assert db.query(Deliverable).count() == 0


def test_monitor_skips_channels_outside_expected_publish_window(seeded_collaboration, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_COLLABORATION_TAG", "#MAXSUN")
    configure_media_profile(seeded_collaboration["media_id"], seeded_collaboration["campaign_id"])
    state = {"published_at": "2026-08-14T00:00:00Z", "views": "1000"}
    with httpx.Client(transport=youtube_transport(state)) as client, SessionLocal() as db:
        result = run_content_monitor(db, client, datetime(2026, 9, 1, 10, 0, 0))
        assert result["channels_scanned"] == 0
        assert state.get("calls", []) == []
