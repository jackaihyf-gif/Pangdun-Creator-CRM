from __future__ import annotations

import asyncio

import pangdun_mcp.server as server


class FakeClient:
    def __init__(self, media: list[dict]):
        self.media = {item["id"]: item.copy() for item in media}
        self.writes: list[dict] = []

    def request(self, path, method="GET", data=None, query=None, reason=None):
        if path == "/api/media":
            return {"items": list(self.media.values()), "total": len(self.media)}
        if path.startswith("/api/media/"):
            media_id = int(path.rsplit("/", 1)[1])
            if method == "GET":
                return {"media": self.media[media_id].copy()}
            self.media[media_id] = {**self.media[media_id], **data}
            self.writes.append({"id": media_id, "data": data, "reason": reason})
            return self.media[media_id].copy()
        raise AssertionError(path)


def media_row(media_id: int, status: str, website: str, notes: str = "") -> dict:
    return {
        "id": media_id,
        "name": f"Media {media_id}",
        "country": "美国",
        "region": None,
        "category": "KOL",
        "platform_type": "YouTube",
        "website_url": website,
        "profile_links": [],
        "followers_or_traffic": 10,
        "audience_metric_type": "粉丝量",
        "audience_metric_unit": "K",
        "media_tier": None,
        "cooperation_status": status,
        "notes": notes,
    }


def test_mcp_tools_expose_read_and_preview_apply_pairs():
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    assert "search_media" in tools
    assert "preview_bulk_status_cleanup" in tools
    assert "apply_bulk_status_cleanup" in tools
    assert tools["search_media"].annotations.readOnlyHint is True
    assert tools["apply_bulk_status_cleanup"].annotations.readOnlyHint is False


def test_bulk_status_cleanup_requires_preview_and_preserves_original(monkeypatch):
    fake = FakeClient([media_row(1, "已发送三次未回复", "https://youtube.com/@one")])
    monkeypatch.setattr(server, "client", lambda: fake)
    server.CHANGE_SETS.clear()

    preview = server.preview_bulk_status_cleanup()
    assert preview["total"] == 1
    assert preview["items"][0]["after"] == "待回复"
    assert fake.writes == []

    result = server.apply_bulk_status_cleanup(preview["change_set_id"], "人工确认历史状态清洗")
    assert result["applied"] == 1
    assert fake.media[1]["cooperation_status"] == "待回复"
    assert "[原合作状态] 已发送三次未回复" in fake.media[1]["notes"]
    assert fake.writes[0]["reason"] == "人工确认历史状态清洗"


def test_bulk_profile_split_skips_records_changed_after_preview(monkeypatch):
    fake = FakeClient([media_row(2, "未联系", "https://youtube.com/@two https://instagram.com/two")])
    monkeypatch.setattr(server, "client", lambda: fake)
    server.CHANGE_SETS.clear()

    preview = server.preview_bulk_profile_link_split()
    assert preview["total"] == 1
    assert [item["platform"] for item in preview["items"][0]["links_after"]] == ["YouTube", "Instagram"]
    fake.media[2]["website_url"] = "https://youtube.com/@changed"

    result = server.apply_bulk_profile_link_split(preview["change_set_id"], "确认拆分历史主页")
    assert result["applied"] == 0
    assert result["skipped"] == [{"id": 2, "reason": "预览后数据已变化"}]
    assert fake.writes == []
