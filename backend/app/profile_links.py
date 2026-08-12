import re
from urllib.parse import urlparse


URL_PATTERN = re.compile(r"https?://[^\s()]+", re.IGNORECASE)


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if "youtube.com" in host or "youtu.be" in host:
        return "YouTube"
    if "instagram.com" in host:
        return "Instagram"
    if "tiktok.com" in host:
        return "TikTok"
    if host in {"x.com", "twitter.com"} or host.endswith(".x.com"):
        return "X"
    if "bilibili.com" in host:
        return "Bilibili"
    if "facebook.com" in host:
        return "Facebook"
    return "网站"


def split_profile_links(raw: str | None) -> list[dict[str, str]]:
    """Extract and deduplicate URLs from legacy cells such as url(url)."""
    seen: set[str] = set()
    links: list[dict[str, str]] = []
    for match in URL_PATTERN.findall(raw or ""):
        url = match.rstrip(".,;，；")
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        links.append({"platform": detect_platform(url), "url": url})
    return links


def clean_profile_links(value: list[dict] | None, fallback: str | None = None) -> list[dict]:
    source = value if value else split_profile_links(fallback)
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in source:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned = {"platform": str(item.get("platform") or detect_platform(url)).strip(), "url": url}
        followers_k = item.get("followers_k")
        if followers_k not in (None, ""):
            try:
                cleaned["followers_k"] = round(float(followers_k), 3)
            except (TypeError, ValueError):
                pass
        result.append(cleaned)
    return result
