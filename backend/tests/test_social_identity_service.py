import httpx
import pytest

from backend.app.social_identity_service import (
    SocialIdentityError,
    SocialProfileIdentity,
    fetch_social_identity,
    merge_social_identity_proposal,
    social_platform,
)


def test_tiktok_identity_uses_official_oembed():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oembed"
        assert request.url.params["url"] == "https://www.tiktok.com/@pinkxxiny"
        return httpx.Response(200, json={
            "author_name": "Pink Creator",
            "author_url": "https://www.tiktok.com/@pinkxxiny",
        })

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_social_identity("https://www.tiktok.com/@Pinkxxiny/videos", client)
    assert result.platform == "TikTok"
    assert result.display_name == "Pink Creator"
    assert result.canonical_url == "https://tiktok.com/@pinkxxiny"
    assert result.source == "TikTok 官方 oEmbed"


def test_instagram_identity_reads_public_title():
    page = '<html><head><meta property="og:title" content="Duda Tech (@dudatech.oficial) • Instagram photos and videos"></head></html>'
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=page))) as client:
        result = fetch_social_identity("https://instagram.com/DudaTech.Oficial/", client)
    assert result.platform == "Instagram"
    assert result.display_name == "Duda Tech"
    assert result.canonical_url == "https://instagram.com/dudatech.oficial"
    assert result.name_confidence == 1


def test_instagram_falls_back_to_handle_when_title_is_unavailable():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="Instagram"))) as client:
        result = fetch_social_identity("https://instagram.com/example.creator", client)
    assert result.display_name == "example.creator"
    assert result.name_confidence == .85


def test_instagram_rejects_post_urls():
    with pytest.raises(SocialIdentityError):
        fetch_social_identity("https://instagram.com/reel/ABC123")


def test_social_identity_merge_overrides_model_name_without_metrics():
    identity = SocialProfileIdentity("TikTok", "Official Creator", "https://tiktok.com/@creator", "creator", "TikTok 官方 oEmbed")
    proposal = merge_social_identity_proposal({
        "media": {"name": "Model Guess", "followers_or_traffic": None},
        "contacts": [], "evidence": {}, "confidence": {}, "warnings": [],
    }, identity)
    assert proposal["media"]["name"] == "Official Creator"
    assert proposal["media"]["profile_links"][0]["source"] == "TikTok 官方 oEmbed"
    assert "followers_or_traffic" not in {key for key, value in proposal["media"].items() if value is not None}
    assert proposal["provider"] == "tiktok_public_identity"


@pytest.mark.parametrize(("url", "platform"), [
    ("https://www.tiktok.com/@creator", "TikTok"),
    ("https://instagram.com/creator", "Instagram"),
    ("https://youtube.com/@creator", None),
])
def test_social_platform(url, platform):
    assert social_platform(url) == platform
