import re
from urllib.parse import urlparse, urlunparse


URL_PATTERN = re.compile(r"https?://[^\s()]+", re.IGNORECASE)


def canonical_profile_url(value: str | None) -> str | None:
    raw = (value or "").strip().rstrip("/.,;，；")
    if not raw:
        return None
    if not re.match(r"^https?://", raw, re.I):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = parsed.netloc.lower().removeprefix("www.")
    if host == "twitter.com":
        host = "x.com"
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    if host in {"instagram.com", "tiktok.com", "x.com"}:
        parts = [part for part in path.split("/") if part]
        path = f"/{parts[0].lower()}" if parts else ""
    elif host == "youtube.com":
        parts = [part for part in path.split("/") if part]
        if parts and (parts[0].startswith("@") or parts[0] in {"channel", "c", "user"}):
            keep = parts[:1] if parts[0].startswith("@") else parts[:2]
            path = "/" + "/".join(keep)
    return urlunparse(("https", host, path, "", "", ""))


def profile_identity(value: str | None) -> str | None:
    canonical = canonical_profile_url(value)
    return canonical.casefold() if canonical else None


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
        url = canonical_profile_url(match)
        if not url:
            continue
        key = profile_identity(url)
        if key in seen:
            continue
        seen.add(key)
        links.append({"platform": detect_platform(url), "url": url})
    return links


def clean_profile_links(value: list[dict] | None, fallback: str | None = None) -> list[dict]:
    source = value if value else split_profile_links(fallback)
    if not source and (fallback_url := canonical_profile_url(fallback)):
        source = [{"platform": detect_platform(fallback_url), "url": fallback_url}]
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in source:
        url = canonical_profile_url(str(item.get("url") or ""))
        if not url:
            continue
        key = profile_identity(url)
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
