from __future__ import annotations

import re


MEDIA_CHANNELS = ["YouTube", "Instagram", "TikTok", "X", "Bilibili", "多平台", "科技媒体 / 网站", "其他"]
MEDIA_TIERS = ["S", "A", "B", "C", "D", "待评估"]
AUDIENCE_METRIC_TYPES = ["粉丝量", "月访问量"]
COOPERATION_STATUSES = ["未联系", "待回复", "洽谈中", "已合作", "暂缓", "不合作"]
VERIFICATION_STATUSES = ["待核验", "部分核验", "已核验", "有冲突"]

COUNTRIES = [
    {"code": "CN", "label": "中国", "aliases": ["中国大陆", "china", "prc", "cn"]},
    {"code": "US", "label": "美国", "aliases": ["usa", "united states", "united states of america", "us"]},
    {"code": "CA", "label": "加拿大", "aliases": ["canada", "ca"]},
    {"code": "GB", "label": "英国", "aliases": ["uk", "united kingdom", "great britain", "gb"]},
    {"code": "FR", "label": "法国", "aliases": ["france", "fr"]},
    {"code": "DE", "label": "德国", "aliases": ["germany", "deutschland", "de"]},
    {"code": "IT", "label": "意大利", "aliases": ["italy", "it"]},
    {"code": "ES", "label": "西班牙", "aliases": ["spain", "es"]},
    {"code": "NL", "label": "荷兰", "aliases": ["netherlands", "holland", "nl"]},
    {"code": "PL", "label": "波兰", "aliases": ["poland", "pl"]},
    {"code": "RU", "label": "俄罗斯", "aliases": ["russia", "russian federation", "ru"]},
    {"code": "UA", "label": "乌克兰", "aliases": ["ukraine", "ua"]},
    {"code": "JP", "label": "日本", "aliases": ["japan", "jp"]},
    {"code": "KR", "label": "韩国", "aliases": ["south korea", "korea", "kr"]},
    {"code": "IN", "label": "印度", "aliases": ["india", "in"]},
    {"code": "ID", "label": "印度尼西亚", "aliases": ["indonesia", "id"]},
    {"code": "SG", "label": "新加坡", "aliases": ["singapore", "sg"]},
    {"code": "MY", "label": "马来西亚", "aliases": ["malaysia", "my"]},
    {"code": "TH", "label": "泰国", "aliases": ["thailand", "th"]},
    {"code": "VN", "label": "越南", "aliases": ["vietnam", "viet nam", "vn"]},
    {"code": "PH", "label": "菲律宾", "aliases": ["philippines", "ph"]},
    {"code": "AU", "label": "澳大利亚", "aliases": ["australia", "au"]},
    {"code": "NZ", "label": "新西兰", "aliases": ["new zealand", "nz"]},
    {"code": "BR", "label": "巴西", "aliases": ["brazil", "br"]},
    {"code": "MX", "label": "墨西哥", "aliases": ["mexico", "mx"]},
    {"code": "TR", "label": "土耳其", "aliases": ["turkey", "türkiye", "tr"]},
    {"code": "AE", "label": "阿联酋", "aliases": ["uae", "united arab emirates", "ae"]},
    {"code": "SA", "label": "沙特阿拉伯", "aliases": ["saudi arabia", "sa"]},
    {"code": "ZA", "label": "南非", "aliases": ["south africa", "za"]},
]


def normalize_country(value: str | None) -> tuple[str | None, str | None, bool]:
    raw = (value or "").strip()
    if not raw:
        return None, None, True
    compact = re.sub(r"[\s._-]+", " ", raw).strip().casefold()
    for country in COUNTRIES:
        candidates = [country["code"], country["label"], *country["aliases"]]
        if compact in {str(item).strip().casefold() for item in candidates}:
            return str(country["label"]), str(country["code"]), True
    return raw, None, False


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
    if raw == "待核验":
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
    country, country_code, country_recognized = normalize_country(normalized.get("country"))
    notes = (normalized.get("notes") or "").strip()
    preserved: list[str] = []
    if raw_channel and not channel:
        preserved.append(f"[原渠道] {raw_channel}")
    if raw_cooperation and not cooperation:
        preserved.append(f"[原合作状态] {raw_cooperation}")
    if normalized.get("country") and not country_recognized:
        preserved.append(f"[原国家] {normalized.get('country')}")
    normalized["platform_type"] = channel or ("其他" if raw_channel else None)
    normalized["audience_metric_type"] = infer_audience_metric_type(normalized["platform_type"])
    normalized["audience_metric_unit"] = "K"
    normalized["cooperation_status"] = cooperation or "未联系"
    normalized["country"] = country
    normalized["country_code"] = country_code
    requested_verification = normalized.get("verification_status")
    if requested_verification not in VERIFICATION_STATUSES:
        requested_verification = None
    has_conflict = bool(raw_cooperation and not cooperation) or not country_recognized
    normalized["verification_status"] = "有冲突" if has_conflict else (requested_verification or ("待核验" if raw_cooperation == "待核验" else "已核验"))
    if preserved:
        normalized["notes"] = "\n".join([part for part in [notes, *preserved] if part])
    # Volume is shown and filtered directly; letter tiers are intentionally retired.
    normalized["media_tier"] = None
    return normalized
