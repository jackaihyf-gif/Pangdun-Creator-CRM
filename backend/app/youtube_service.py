from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeConfigurationError(RuntimeError):
    pass


class YouTubeSourceError(ValueError):
    pass


@dataclass(frozen=True)
class YouTubeChannel:
    channel_id: str
    title: str
    description: str
    canonical_url: str
    country: str | None
    subscribers: int | None
    subscribers_hidden: bool
    view_count: int | None
    video_count: int | None

    @property
    def followers_k(self) -> float | None:
        return None if self.subscribers is None else round(self.subscribers / 1000, 3)

    def source_text(self) -> str:
        lines = [
            "YouTube Data API 官方频道资料",
            f"频道名称：{self.title}",
            f"频道主页：{self.canonical_url}",
            f"频道 ID：{self.channel_id}",
        ]
        if self.country:
            lines.append(f"频道国家/地区：{self.country}")
        if self.subscribers is not None:
            lines.append(f"订阅者：{self.subscribers}")
        elif self.subscribers_hidden:
            lines.append("订阅者：频道已隐藏")
        if self.view_count is not None:
            lines.append(f"频道总播放量：{self.view_count}")
        if self.video_count is not None:
            lines.append(f"公开视频数：{self.video_count}")
        if self.description:
            lines.extend(["频道简介：", self.description])
        return "\n".join(lines)


def is_youtube_url(value: str) -> bool:
    try:
        host = (urlparse(value.strip()).hostname or "").casefold()
    except ValueError:
        return False
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}


def youtube_config() -> dict[str, Any]:
    return {"configured": bool(os.getenv("YOUTUBE_API_KEY")), "provider": "YouTube Data API v3"}


def _api_error(response: httpx.Response) -> YouTubeSourceError:
    message = "YouTube 官方接口请求失败"
    try:
        error = response.json().get("error") or {}
        reason = (((error.get("errors") or [{}])[0]).get("reason") or "").casefold()
        detail = str(error.get("message") or "").strip()
    except (ValueError, AttributeError, TypeError):
        reason, detail = "", ""
    if reason in {"keyinvalid", "accessnotconfigured", "iprefererblocked"}:
        message = "YouTube API Key 无效或尚未启用 YouTube Data API v3"
    elif reason in {"quotaexceeded", "dailylimitexceeded"}:
        message = "YouTube API 今日配额已用完，请稍后再试"
    elif detail:
        message = f"YouTube 官方接口请求失败：{detail}"
    return YouTubeSourceError(message)


def _get_json(client: httpx.Client, path: str, params: dict[str, Any], api_key: str) -> dict[str, Any]:
    response = client.get(f"{YOUTUBE_API_BASE_URL}/{path}", params={**params, "key": api_key})
    if response.is_error:
        raise _api_error(response)
    try:
        return response.json()
    except ValueError as exc:
        raise YouTubeSourceError("YouTube 官方接口返回了无法解析的数据") from exc


def _channel_lookup(url: str, client: httpx.Client, api_key: str) -> dict[str, str]:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").casefold().removeprefix("www.").removeprefix("m.")
    parts = [part for part in parsed.path.split("/") if part]
    video_id: str | None = None
    if host == "youtu.be" and parts:
        video_id = parts[0]
    elif host == "youtube.com":
        if parsed.path == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [None])[0]
        elif parts and parts[0] in {"shorts", "live", "embed"} and len(parts) > 1:
            video_id = parts[1]
        elif parts and parts[0].startswith("@"):
            return {"forHandle": parts[0]}
        elif len(parts) > 1 and parts[0] == "channel":
            return {"id": parts[1]}
        elif len(parts) > 1 and parts[0] == "user":
            return {"forUsername": parts[1]}
        elif parts:
            candidate = parts[1] if parts[0] == "c" and len(parts) > 1 else parts[0]
            return {"forHandle": candidate}
    if video_id:
        video = _get_json(client, "videos", {"part": "snippet", "id": video_id}, api_key)
        items = video.get("items") or []
        channel_id = ((items[0].get("snippet") or {}).get("channelId") if items else None)
        if channel_id:
            return {"id": channel_id}
        raise YouTubeSourceError("该 YouTube 视频不存在、不可公开访问或没有所属频道")
    raise YouTubeSourceError("请输入 YouTube 频道主页、@handle 或公开视频链接")


def fetch_youtube_channel(url: str, client: httpx.Client | None = None) -> YouTubeChannel:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise YouTubeConfigurationError("尚未配置 YOUTUBE_API_KEY")
    owns_client = client is None
    api_client = client or httpx.Client(timeout=20, headers={"User-Agent": "PangdunCRM-Agent/1.0"})
    try:
        lookup = _channel_lookup(url, api_client, api_key)
        body = _get_json(api_client, "channels", {"part": "snippet,statistics", **lookup}, api_key)
    finally:
        if owns_client:
            api_client.close()
    items = body.get("items") or []
    if not items:
        raise YouTubeSourceError("没有找到对应的公开 YouTube 频道；旧式自定义地址可能需要改为 @handle")
    item = items[0]
    snippet = item.get("snippet") or {}
    statistics = item.get("statistics") or {}
    channel_id = str(item.get("id") or "").strip()
    custom_url = str(snippet.get("customUrl") or "").strip()
    canonical_url = f"https://youtube.com/{custom_url}" if custom_url.startswith("@") else f"https://youtube.com/channel/{channel_id}"
    hidden = bool(statistics.get("hiddenSubscriberCount"))
    subscribers = None if hidden or statistics.get("subscriberCount") in (None, "") else int(statistics["subscriberCount"])
    return YouTubeChannel(
        channel_id=channel_id,
        title=str(snippet.get("title") or "").strip(),
        description=str(snippet.get("description") or "").strip(),
        canonical_url=canonical_url,
        country=(str(snippet.get("country") or "").strip() or None),
        subscribers=subscribers,
        subscribers_hidden=hidden,
        view_count=int(statistics["viewCount"]) if statistics.get("viewCount") not in (None, "") else None,
        video_count=int(statistics["videoCount"]) if statistics.get("videoCount") not in (None, "") else None,
    )


def merge_youtube_proposal(proposal: dict[str, Any], channel: YouTubeChannel) -> dict[str, Any]:
    today = date.today().isoformat()
    media = proposal.setdefault("media", {})
    evidence = proposal.setdefault("evidence", {})
    confidence = proposal.setdefault("confidence", {})
    exact: dict[str, Any] = {
        "name": channel.title,
        "platform_type": "YouTube",
        "profile_links": [{
            "platform": "YouTube", "url": channel.canonical_url,
            "followers_k": channel.followers_k, "source": "YouTube Data API v3",
            "verified_at": today, "confidence": 1,
        }],
        "audience_metric_type": "粉丝量",
    }
    if channel.country:
        exact["country"] = channel.country
    if channel.followers_k is not None:
        exact.update({"followers_or_traffic": channel.followers_k, "metric_source": "YouTube Data API v3", "metric_verified_at": today})
    media.update(exact)
    field_evidence = {
        "media.name": f"YouTube Data API：频道名称 {channel.title}",
        "media.platform_type": "YouTube Data API：频道资源",
        "media.profile_links": f"YouTube Data API：频道 ID {channel.channel_id}；{channel.canonical_url}",
        "media.audience_metric_type": "YouTube Data API：subscriberCount",
    }
    if channel.country:
        field_evidence["media.country"] = f"YouTube Data API：频道国家/地区 {channel.country}"
    if channel.followers_k is not None:
        field_evidence.update({
            "media.followers_or_traffic": f"YouTube Data API：subscriberCount {channel.subscribers}（{channel.followers_k} K）",
            "media.metric_source": "YouTube Data API v3",
            "media.metric_verified_at": f"官方接口查询日期 {today}",
        })
    evidence.update(field_evidence)
    confidence.update({key: 1.0 for key in field_evidence})
    warnings = [
        warning for warning in proposal.setdefault("warnings", [])
        if "个字段缺少原文证据" not in str(warning)
    ]
    proposed_fields = {f"media.{key}": value for key, value in media.items()}
    for index, contact in enumerate(proposal.get("contacts") or []):
        if isinstance(contact, dict):
            proposed_fields.update({f"contacts.{index}.{key}": value for key, value in contact.items()})
    missing_evidence = [
        key for key, value in proposed_fields.items()
        if value not in (None, "", []) and key not in evidence
    ]
    if missing_evidence:
        warnings.append(f"{len(missing_evidence)} 个字段缺少原文证据，写入前必须人工核对")
    proposal["warnings"] = warnings
    if channel.subscribers_hidden:
        proposal["warnings"].append("该频道隐藏了订阅者数量，本次不会覆盖现有粉丝量")
    proposal["summary"] = f"已通过 YouTube 官方接口核验 {channel.title} 的频道档案"
    proposal["provider"] = "youtube_data_api"
    return proposal
