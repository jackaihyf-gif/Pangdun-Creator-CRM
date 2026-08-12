from __future__ import annotations

import re


MEDIA_CHANNELS = ["YouTube", "Instagram", "TikTok", "X", "Bilibili", "多平台", "科技媒体 / 网站", "其他"]
MEDIA_TIERS = ["S", "A", "B", "C", "D", "待评估"]
AUDIENCE_METRIC_TYPES = ["粉丝量", "月访问量"]
COOPERATION_STATUSES = ["未联系", "待回复", "洽谈中", "已合作", "暂缓", "不合作", "待核验"]


def normalize_channel(value: str | None, website_url: str | None = None) -> str | None:
    raw = (value or "").strip()
    # An explicit multi-platform classification must not be overwritten by an
    # aggregator URL such as a Beacons media kit or Linktree profile.
    if raw == "多平台":
        return raw
    probe = f"{raw} {website_url or ''}".lower()
    if not probe.strip():
        return None
    detected = sum(bool(token in probe) for token in ["youtube", "instagram", "tiktok", "bilibili"])
    if detected > 1:
        return "多平台"
    if "youtube" in probe or "youtu.be" in probe:
        return "YouTube"
    if "instagram" in probe:
        return "Instagram"
    if "tiktok" in probe:
        return "TikTok"
    if "bilibili" in probe or "b站" in probe:
        return "Bilibili"
    if re.search(r"(^|[\s/])x([\s/.]|$)|twitter", probe):
        return "X"
    if any(token in probe for token in ["科技网站", "科技媒体", "网站", "新闻", "测评", "评测", "论坛", "media"]):
        return "科技媒体 / 网站"
    if re.search(r"https?://", website_url or "") and not any(token in probe for token in ["youtube", "youtu.be", "instagram", "tiktok", "bilibili", "twitter.com", "x.com"]):
        return "科技媒体 / 网站"
    if raw in MEDIA_CHANNELS:
        return raw
    return "其他"


def normalize_cooperation_status(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return "未联系"
    if raw in COOPERATION_STATUSES:
        return raw
    compact = re.sub(r"\s+", "", raw).lower()
    exact_groups = {
        "未联系": {"未接触", "未沟通", "new", "notcontacted"},
        "待回复": {"已联系", "等待回复", "待回应", "contacted", "waitingreply", "发送邮件"},
        "洽谈中": {"沟通中", "跟进中", "报价中", "有意向", "negotiating", "quoting"},
        "已合作": {"合作过", "已完成合作", "cooperated", "closedwon"},
        "暂缓": {"暂停", "延后", "paused", "onhold"},
        "不合作": {"拒绝", "不愿意合作", "无意向", "blacklisted", "closedlost"},
    }
    for canonical, aliases in exact_groups.items():
        if compact in aliases:
            return canonical
    return None


def infer_audience_metric_type(platform_type: str | None) -> str:
    return "月访问量" if platform_type == "科技媒体 / 网站" else "粉丝量"


def metric_value_in_k(value: float | int | None, unit: str | None) -> float | None:
    if value is None:
        return None
    converted = float(value) if unit == "K" else float(value) / 1000
    return round(converted, 2)


def infer_media_tier(followers_or_traffic: float | None) -> str:
    if followers_or_traffic is None:
        return "待评估"
    if followers_or_traffic >= 1_000:
        return "S"
    if followers_or_traffic >= 500:
        return "A"
    if followers_or_traffic >= 100:
        return "B"
    if followers_or_traffic >= 10:
        return "C"
    return "D"


def normalize_media_payload(data: dict) -> dict:
    normalized = dict(data)
    raw_channel = (normalized.get("platform_type") or "").strip()
    raw_cooperation = (normalized.get("cooperation_status") or "").strip()
    channel = normalize_channel(raw_channel, normalized.get("website_url"))
    cooperation = normalize_cooperation_status(raw_cooperation)
    notes = (normalized.get("notes") or "").strip()
    preserved: list[str] = []
    if raw_channel and not channel:
        preserved.append(f"[原渠道] {raw_channel}")
    if raw_cooperation and not cooperation:
        preserved.append(f"[原合作状态] {raw_cooperation}")
    normalized["platform_type"] = channel or ("其他" if raw_channel else None)
    normalized["audience_metric_type"] = infer_audience_metric_type(normalized["platform_type"])
    normalized["audience_metric_unit"] = "K"
    normalized["cooperation_status"] = cooperation or "待核验"
    if preserved:
        normalized["notes"] = "\n".join([part for part in [notes, *preserved] if part])
    # Volume is shown and filtered directly; letter tiers are intentionally retired.
    normalized["media_tier"] = None
    return normalized
