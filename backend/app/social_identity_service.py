from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

import httpx

from .profile_links import canonical_profile_url


MAX_INSTAGRAM_BYTES = 2_000_000
INSTAGRAM_RESERVED_PATHS = {"about", "accounts", "developer", "direct", "explore", "p", "reel", "reels", "stories"}


class SocialIdentityError(ValueError):
    pass


@dataclass(frozen=True)
class SocialProfileIdentity:
    platform: str
    display_name: str
    canonical_url: str
    handle: str
    source: str
    name_confidence: float = 1.0

    def source_text(self) -> str:
        return "\n".join([
            f"{self.source} 公开主页资料",
            f"平台：{self.platform}",
            f"显示名称：{self.display_name}",
            f"账号：@{self.handle}",
            f"标准主页：{self.canonical_url}",
        ])


def social_platform(value: str) -> str | None:
    try:
        host = (urlparse(value.strip()).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return None
    if host == "tiktok.com":
        return "TikTok"
    if host == "instagram.com":
        return "Instagram"
    return None


def _profile_handle(url: str, platform: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if not parts:
        raise SocialIdentityError(f"请输入 {platform} 用户主页链接")
    handle = parts[0].removeprefix("@").strip().casefold()
    if not handle or (platform == "Instagram" and handle in INSTAGRAM_RESERVED_PATHS):
        raise SocialIdentityError(f"请输入 {platform} 用户主页，而不是帖子、Reel 或功能页面")
    return handle


def _response_error(response: httpx.Response, platform: str) -> SocialIdentityError:
    if response.status_code == 404:
        return SocialIdentityError(f"没有找到对应的公开 {platform} 主页")
    if response.status_code == 429:
        return SocialIdentityError(f"{platform} 暂时限制了公开主页读取，请稍后再试")
    return SocialIdentityError(f"{platform} 公开主页读取失败（HTTP {response.status_code}）")


def _instagram_title(body: str) -> str | None:
    candidates = [
        re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', body, re.I),
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', body, re.I),
        re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S),
    ]
    for match in candidates:
        if match:
            return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return None


def _instagram_display_name(title: str | None, handle: str) -> tuple[str, float]:
    if title:
        match = re.match(rf"\s*(.*?)\s*\(@{re.escape(handle)}\)", title, re.I)
        if match and match.group(1).strip():
            return match.group(1).strip(), 1.0
    return handle, 0.85


def fetch_social_identity(url: str, client: httpx.Client | None = None) -> SocialProfileIdentity:
    platform = social_platform(url)
    if not platform:
        raise SocialIdentityError("当前轻量身份补全仅支持 TikTok 和 Instagram 主页")
    canonical = canonical_profile_url(url)
    if not canonical:
        raise SocialIdentityError("无法识别该社媒主页")
    handle = _profile_handle(canonical, platform)
    owns_client = client is None
    api_client = client or httpx.Client(
        timeout=20,
        follow_redirects=False,
        headers={"User-Agent": "Mozilla/5.0 (compatible; PangdunCRM/1.0; public-profile-review)"},
    )
    try:
        if platform == "TikTok":
            public_profile_url = f"https://www.tiktok.com/@{handle}"
            response = api_client.get("https://www.tiktok.com/oembed", params={"url": public_profile_url})
            if response.is_error:
                raise _response_error(response, platform)
            try:
                data = response.json()
            except ValueError as exc:
                raise SocialIdentityError("TikTok oEmbed 返回了无法解析的数据") from exc
            display_name = str(data.get("author_name") or "").strip()
            author_url = canonical_profile_url(str(data.get("author_url") or canonical)) or canonical
            if not display_name:
                raise SocialIdentityError("TikTok 没有返回该公开主页的显示名称")
            return SocialProfileIdentity(platform, display_name, author_url, handle, "TikTok 官方 oEmbed")

        public_profile_url = f"https://www.instagram.com/{handle}/"
        response = api_client.get(public_profile_url)
        if response.is_error:
            raise _response_error(response, platform)
        raw_body = response.content
        if len(raw_body) > MAX_INSTAGRAM_BYTES:
            raw_body = raw_body[:MAX_INSTAGRAM_BYTES]
        encoding = response.encoding or "utf-8"
        title = _instagram_title(raw_body.decode(encoding, errors="replace"))
        display_name, confidence = _instagram_display_name(title, handle)
        return SocialProfileIdentity(platform, display_name, canonical, handle, "Instagram 公开主页标题", confidence)
    finally:
        if owns_client:
            api_client.close()


def merge_social_identity_proposal(proposal: dict[str, Any], identity: SocialProfileIdentity) -> dict[str, Any]:
    today = date.today().isoformat()
    media = proposal.setdefault("media", {})
    evidence = proposal.setdefault("evidence", {})
    confidence = proposal.setdefault("confidence", {})
    media.update({
        "name": identity.display_name,
        "platform_type": identity.platform,
        "profile_links": [{
            "platform": identity.platform,
            "url": identity.canonical_url,
            "source": identity.source,
            "verified_at": today,
            "confidence": identity.name_confidence,
        }],
    })
    evidence.update({
        "media.name": f"{identity.source}：{identity.display_name}（@{identity.handle}）",
        "media.platform_type": f"{identity.source}：{identity.platform}",
        "media.profile_links": f"{identity.source}：{identity.canonical_url}",
    })
    confidence.update({
        "media.name": identity.name_confidence,
        "media.platform_type": 1.0,
        "media.profile_links": 1.0,
    })
    warnings = [warning for warning in proposal.setdefault("warnings", []) if "个字段缺少原文证据" not in str(warning)]
    proposed_fields = {f"media.{key}": value for key, value in media.items()}
    for index, contact in enumerate(proposal.get("contacts") or []):
        if isinstance(contact, dict):
            proposed_fields.update({f"contacts.{index}.{key}": value for key, value in contact.items()})
    missing = [key for key, value in proposed_fields.items() if value not in (None, "", []) and key not in evidence]
    if missing:
        warnings.append(f"{len(missing)} 个字段缺少原文证据，写入前必须人工核对")
    proposal["warnings"] = warnings
    proposal["summary"] = f"已核验 {identity.platform} 公开主页身份：{identity.display_name}"
    proposal["provider"] = f"{identity.platform.casefold()}_public_identity"
    return proposal
