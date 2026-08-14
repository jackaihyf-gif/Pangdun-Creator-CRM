from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy.orm import Session, joinedload

from .database import SessionLocal
from .models import Campaign, Deliverable, DeliverablePerformanceSnapshot, Media
from .youtube_service import (
    YOUTUBE_API_BASE_URL,
    YouTubeConfigurationError,
    YouTubeSourceError,
    fetch_youtube_channel,
)


ACTIVE_MONITOR_STATUSES = {"待确认", "待发货", "运输中", "已签收待产出", "内容审核中", "已发布"}
YOUTUBE_SOURCE = "YouTube Data API v3"


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    channel_id: str
    title: str
    description: str
    published_at: datetime
    views: int | None
    likes: int | None
    comments: int | None

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def content_monitor_config() -> dict[str, Any]:
    tag = os.getenv("YOUTUBE_COLLABORATION_TAG", "#MAXSUN").strip()
    interval = max(900, int(os.getenv("CONTENT_MONITOR_INTERVAL_SECONDS", "21600")))
    days_before = max(0, int(os.getenv("CONTENT_MONITOR_DAYS_BEFORE", "1")))
    days_after = max(0, int(os.getenv("CONTENT_MONITOR_DAYS_AFTER", "7")))
    enabled = os.getenv("CONTENT_MONITOR_ENABLED", "1").strip().casefold() not in {"0", "false", "off", "no"}
    return {
        "configured": bool(os.getenv("YOUTUBE_API_KEY", "").strip() and tag),
        "enabled": enabled,
        "tag": tag,
        "interval_seconds": interval,
        "days_before": days_before,
        "days_after": days_after,
        "provider": YOUTUBE_SOURCE,
    }


def _api_json(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise YouTubeConfigurationError("尚未配置 YOUTUBE_API_KEY")
    response = client.get(f"{YOUTUBE_API_BASE_URL}/{path}", params={**params, "key": api_key})
    if response.is_error:
        raise YouTubeSourceError(f"YouTube 内容监测请求失败（HTTP {response.status_code}）")
    try:
        return response.json()
    except ValueError as exc:
        raise YouTubeSourceError("YouTube 内容监测返回了无法解析的数据") from exc


def _published_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _int_or_none(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def fetch_uploads_playlist_id(channel_id: str, client: httpx.Client) -> str | None:
    channel = _api_json(client, "channels", {"part": "contentDetails", "id": channel_id})
    items = channel.get("items") or []
    return (((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads") if items else None)


def fetch_channel_videos(channel_id: str, client: httpx.Client, max_results: int = 15, uploads_playlist_id: str | None = None) -> list[YouTubeVideo]:
    uploads_id = uploads_playlist_id or fetch_uploads_playlist_id(channel_id, client)
    if not uploads_id:
        return []
    playlist = _api_json(client, "playlistItems", {"part": "contentDetails", "playlistId": uploads_id, "maxResults": max_results})
    video_ids = [str((row.get("contentDetails") or {}).get("videoId") or "").strip() for row in playlist.get("items") or []]
    video_ids = [video_id for video_id in video_ids if video_id]
    if not video_ids:
        return []
    body = _api_json(client, "videos", {"part": "snippet,statistics", "id": ",".join(video_ids)})
    videos: list[YouTubeVideo] = []
    for row in body.get("items") or []:
        snippet = row.get("snippet") or {}
        statistics = row.get("statistics") or {}
        if not row.get("id") or not snippet.get("publishedAt"):
            continue
        videos.append(YouTubeVideo(
            video_id=str(row["id"]),
            channel_id=str(snippet.get("channelId") or channel_id),
            title=str(snippet.get("title") or "").strip(),
            description=str(snippet.get("description") or ""),
            published_at=_published_at(str(snippet["publishedAt"])),
            views=_int_or_none(statistics.get("viewCount")),
            likes=_int_or_none(statistics.get("likeCount")),
            comments=_int_or_none(statistics.get("commentCount")),
        ))
    return videos


def description_has_tag(description: str, tag: str) -> bool:
    if not tag:
        return False
    return bool(re.search(rf"(?<![\w]){re.escape(tag)}(?![\w])", description, flags=re.IGNORECASE))


def youtube_video_id(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").casefold().removeprefix("www.").removeprefix("m.")
    parts = [part for part in parsed.path.split("/") if part]
    if host == "youtu.be" and parts:
        return parts[0]
    if host == "youtube.com":
        if parsed.path == "/watch":
            return (parse_qs(parsed.query).get("v") or [None])[0]
        if len(parts) > 1 and parts[0] in {"shorts", "live", "embed"}:
            return parts[1]
    return None


def _youtube_profile_url(media: Media) -> str | None:
    for row in media.profile_links or []:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        platform = str(row.get("platform") or "").casefold()
        if url and (platform == "youtube" or "youtube.com" in url.casefold() or "youtu.be" in url.casefold()):
            return url
    website = (media.website_url or "").strip()
    return website if "youtube.com" in website.casefold() or "youtu.be" in website.casefold() else None


def _hours_since(video: YouTubeVideo, captured_at: datetime) -> float:
    return max(0.0, (captured_at - video.published_at).total_seconds() / 3600)


def campaign_monitor_window(campaign: Campaign, config: dict[str, Any]) -> tuple[date, date] | None:
    if not campaign.expected_publish_date:
        return None
    return (
        campaign.expected_publish_date - timedelta(days=config["days_before"]),
        campaign.expected_publish_date + timedelta(days=config["days_after"]),
    )


def campaign_is_in_monitor_window(campaign: Campaign, current_date: date, config: dict[str, Any]) -> bool:
    window = campaign_monitor_window(campaign, config)
    return bool(window and window[0] <= current_date <= window[1])


def _write_sample(db: Session, deliverable: Deliverable, video: YouTubeVideo, kind: str, captured_at: datetime) -> bool:
    exists = db.query(DeliverablePerformanceSnapshot).filter(
        DeliverablePerformanceSnapshot.deliverable_id == deliverable.id,
        DeliverablePerformanceSnapshot.sample_kind == kind,
    ).first()
    if exists:
        return False
    db.add(DeliverablePerformanceSnapshot(
        deliverable_id=deliverable.id,
        sample_kind=kind,
        views=video.views,
        likes=video.likes,
        comments=video.comments,
        captured_at=captured_at,
        hours_since_publish=round(_hours_since(video, captured_at), 2),
        source=YOUTUBE_SOURCE,
    ))
    return True


def _update_monitoring(db: Session, deliverable: Deliverable, video: YouTubeVideo, captured_at: datetime, is_new: bool) -> None:
    age_hours = _hours_since(video, captured_at)
    deliverable.title = video.title or deliverable.title
    deliverable.url = video.url
    deliverable.published_at = video.published_at.date()
    deliverable.platform_published_at = video.published_at
    deliverable.platform_channel_id = video.channel_id
    deliverable.views = video.views
    deliverable.likes = video.likes
    deliverable.comments = video.comments
    deliverable.data_updated_at = captured_at
    if is_new:
        deliverable.first_detected_at = captured_at
        if age_hours >= 72:
            _write_sample(db, deliverable, video, "late_discovery", captured_at)
            deliverable.monitoring_status = "late_discovered"
            deliverable.monitoring_completed_at = captured_at
            return
        _write_sample(db, deliverable, video, "discovery", captured_at)
    if age_hours >= 72:
        _write_sample(db, deliverable, video, "day_3", captured_at)
        deliverable.monitoring_status = "completed"
        deliverable.monitoring_completed_at = captured_at
    elif age_hours >= 24:
        _write_sample(db, deliverable, video, "day_1", captured_at)
        deliverable.monitoring_status = "waiting_day_3"
    else:
        deliverable.monitoring_status = "waiting_day_1"


def run_content_monitor(db: Session, client: httpx.Client | None = None, captured_at: datetime | None = None) -> dict[str, Any]:
    config = content_monitor_config()
    if not config["configured"]:
        raise YouTubeConfigurationError("内容监测需要 YOUTUBE_API_KEY 和合作 Tag")
    now = captured_at or datetime.utcnow()
    owns_client = client is None
    api_client = client or httpx.Client(timeout=20, headers={"User-Agent": "PangdunCRM-ContentMonitor/1.0"})
    result: dict[str, Any] = {"channels_scanned": 0, "videos_checked": 0, "matched": 0, "updated": 0, "conflicts": 0, "tag": config["tag"]}
    try:
        monitored = db.query(Deliverable).filter(
            Deliverable.platform_content_id.isnot(None),
            Deliverable.monitoring_status.in_(["waiting_day_1", "waiting_day_3"]),
        ).all()
        monitored_ids = {row.platform_content_id for row in monitored if row.platform_content_id}
        if monitored_ids:
            body = _api_json(api_client, "videos", {"part": "snippet,statistics", "id": ",".join(sorted(monitored_ids))})
            for raw in body.get("items") or []:
                snippet, statistics = raw.get("snippet") or {}, raw.get("statistics") or {}
                if not snippet.get("publishedAt"):
                    continue
                video = YouTubeVideo(str(raw["id"]), str(snippet.get("channelId") or ""), str(snippet.get("title") or ""), str(snippet.get("description") or ""), _published_at(str(snippet["publishedAt"])), _int_or_none(statistics.get("viewCount")), _int_or_none(statistics.get("likeCount")), _int_or_none(statistics.get("commentCount")))
                deliverable = next((row for row in monitored if row.platform_content_id == video.video_id), None)
                if deliverable:
                    _update_monitoring(db, deliverable, video, now, False)
                    result["updated"] += 1

        current_date = now.date()
        campaigns = db.query(Campaign).options(joinedload(Campaign.media)).filter(
            Campaign.is_historical.is_(False),
            Campaign.execution_status.in_(ACTIVE_MONITOR_STATUSES),
            Campaign.expected_publish_date.isnot(None),
            Campaign.expected_publish_date >= current_date - timedelta(days=config["days_after"]),
            Campaign.expected_publish_date <= current_date + timedelta(days=config["days_before"]),
        ).all()
        by_media: dict[int, list[Campaign]] = {}
        for campaign in campaigns:
            by_media.setdefault(campaign.media_id, []).append(campaign)
        for media_campaigns in by_media.values():
            media = media_campaigns[0].media
            profile_url = _youtube_profile_url(media)
            if not profile_url:
                continue
            if not media.youtube_channel_id:
                channel = fetch_youtube_channel(profile_url, api_client)
                media.youtube_channel_id = channel.channel_id
            if not media.youtube_uploads_playlist_id:
                media.youtube_uploads_playlist_id = fetch_uploads_playlist_id(media.youtube_channel_id, api_client)
            videos = fetch_channel_videos(media.youtube_channel_id, api_client, uploads_playlist_id=media.youtube_uploads_playlist_id)
            result["channels_scanned"] += 1
            result["videos_checked"] += len(videos)
            for video in videos:
                if not any((window := campaign_monitor_window(campaign, config)) and window[0] <= video.published_at.date() <= window[1] for campaign in media_campaigns):
                    continue
                if not description_has_tag(video.description, config["tag"]):
                    continue
                existing = db.query(Deliverable).filter(Deliverable.platform_content_id == video.video_id).first()
                if not existing:
                    existing = next((row for row in db.query(Deliverable).filter(Deliverable.url.isnot(None)).all() if youtube_video_id(row.url) == video.video_id), None)
                if existing:
                    if existing.campaign.media_id != media.id:
                        result["conflicts"] += 1
                        continue
                    if not existing.platform_content_id:
                        existing.platform_content_id = video.video_id
                        existing.platform_channel_id = video.channel_id
                        existing.matched_tag = config["tag"]
                        existing.match_method = "channel_tag_existing"
                        _update_monitoring(db, existing, video, now, True)
                        result["updated"] += 1
                    continue
                if len(media_campaigns) != 1:
                    result["conflicts"] += 1
                    continue
                campaign = media_campaigns[0]
                deliverable = Deliverable(
                    campaign_id=campaign.id,
                    deliverable_type="YouTube Video",
                    title=video.title,
                    url=video.url,
                    platform_content_id=video.video_id,
                    platform_channel_id=video.channel_id,
                    matched_tag=config["tag"],
                    match_method="channel_tag",
                )
                db.add(deliverable)
                db.flush()
                _update_monitoring(db, deliverable, video, now, True)
                result["matched"] += 1
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_client:
            api_client.close()


_monitor_thread: threading.Thread | None = None
_stop_event = threading.Event()
_last_result: dict[str, Any] = {}


def monitor_runtime_status() -> dict[str, Any]:
    return {**content_monitor_config(), "running": bool(_monitor_thread and _monitor_thread.is_alive()), "last_result": _last_result}


def _monitor_loop() -> None:
    global _last_result
    interval = content_monitor_config()["interval_seconds"]
    while not _stop_event.is_set():
        try:
            with SessionLocal() as db:
                _last_result = {**run_content_monitor(db), "ran_at": datetime.utcnow().isoformat()}
        except Exception as exc:  # keep the LAN service alive; status exposes the latest failure
            _last_result = {"error": str(exc), "ran_at": datetime.utcnow().isoformat()}
        _stop_event.wait(interval)


def start_content_monitor() -> None:
    global _monitor_thread
    config = content_monitor_config()
    if not config["enabled"] or not config["configured"] or (_monitor_thread and _monitor_thread.is_alive()):
        return
    _stop_event.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, name="pangdun-content-monitor", daemon=True)
    _monitor_thread.start()


def stop_content_monitor() -> None:
    _stop_event.set()
