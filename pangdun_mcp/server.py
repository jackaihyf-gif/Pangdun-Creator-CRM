from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from pangdun_api import DEFAULT_URL, PangdunClient, PangdunError


MEDIA_FIELDS = [
    "name", "country", "region", "category", "platform_type", "website_url",
    "profile_links", "followers_or_traffic", "audience_metric_type",
    "audience_metric_unit", "media_tier", "cooperation_status", "notes",
]
MEDIA_UPDATE_FIELDS = set(MEDIA_FIELDS) - {"profile_links"}
COLLABORATION_UPDATE_FIELDS = {
    "execution_status", "next_action", "follow_up_date", "follow_up_priority",
    "owner_id", "follow_up_done",
}
CANONICAL_COOPERATION_STATUSES = {"未联系", "待回复", "洽谈中", "已合作", "暂缓", "不合作", "待核验"}
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


@dataclass
class ChangeSet:
    kind: str
    payload: dict[str, Any]
    created_at: datetime


CHANGE_SETS: dict[str, ChangeSet] = {}
CHANGE_SET_TTL = timedelta(minutes=15)


def _cli_config_path() -> Path:
    override = os.environ.get("PANGDUN_CONFIG")
    if override:
        return Path(override).expanduser()
    local = os.environ.get("LOCALAPPDATA")
    return (Path(local) / "PangdunCRM" / "cli.json") if local else (Path.home() / ".pangdun" / "cli.json")


def _connection_config() -> tuple[str, str]:
    config: dict[str, Any] = {}
    path = _cli_config_path()
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            config = {}
    url = os.environ.get("PANGDUN_URL") or config.get("url") or DEFAULT_URL
    token = os.environ.get("PANGDUN_TOKEN") or config.get("token")
    if not token:
        raise PangdunError("MCP 尚未获得 CRM 身份。请先运行 pangdun.cmd auth login，或设置 PANGDUN_TOKEN。")
    return url, token


def client() -> PangdunClient:
    url, token = _connection_config()
    return PangdunClient(url, token)


def _new_change_set(kind: str, payload: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    expired = [key for key, item in CHANGE_SETS.items() if now - item.created_at > CHANGE_SET_TTL]
    for key in expired:
        CHANGE_SETS.pop(key, None)
    change_set_id = secrets.token_urlsafe(18)
    CHANGE_SETS[change_set_id] = ChangeSet(kind=kind, payload=payload, created_at=now)
    return change_set_id


def _change_set(change_set_id: str, kind: str) -> ChangeSet:
    item = CHANGE_SETS.get(change_set_id)
    if not item or item.kind != kind:
        raise ValueError("变更预览不存在或类型不匹配，请重新生成预览")
    if datetime.now(timezone.utc) - item.created_at > CHANGE_SET_TTL:
        CHANGE_SETS.pop(change_set_id, None)
        raise ValueError("变更预览已超过 15 分钟，请重新生成")
    return item


def _require_reason(reason: str) -> str:
    value = reason.strip()
    if len(value) < 4:
        raise ValueError("写入原因至少需要 4 个字符")
    return value


def _legacy_status(value: str) -> str:
    compact = re.sub(r"\s+", "", value)
    if any(token in compact for token in ["不愿意合作", "不商业合作", "拒绝", "不合作"]):
        return "不合作"
    if any(token in compact for token in ["已合作", "已产出", "已发货", "送测中", "待收货", "和编辑合作"]):
        return "已合作"
    if any(token in compact for token in ["未回复", "回复不活跃", "鸽子", "已发送", "联系"]):
        return "待回复"
    if any(token in compact for token in ["待开发", "未开发", "未发送"]):
        return "未联系"
    if any(token in compact for token in ["已经回复", "对方同意", "愿意", "可发review", "倾向", "要钱", "测评视频", "只发news"]):
        return "洽谈中"
    return "待核验"


def _profile_links(raw: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for url in re.findall(r"https?://[^\s()]+", raw, re.I):
        url = url.rstrip(".,;，；")
        if any(url.rstrip("/").casefold() == item["url"].rstrip("/").casefold() for item in links):
            continue
        host = (urlparse(url).hostname or "").casefold()
        platform = next((label for needle, label in [
            ("youtube", "YouTube"), ("youtu.be", "YouTube"), ("instagram", "Instagram"),
            ("tiktok", "TikTok"), ("bilibili", "Bilibili"), ("facebook", "Facebook"),
            ("x.com", "X"), ("twitter", "X"),
        ] if needle in host), "网站")
        links.append({"platform": platform, "url": url})
    return links


mcp = FastMCP(
    "Pangdun CRM",
    instructions="Pangdun CRM 本地工具。查询工具可直接使用；所有写入必须先生成预览，再由用户确认并提供原因。",
)


@mcp.tool(annotations=READ_ONLY)
def connection_status() -> dict[str, Any]:
    """确认当前 MCP 使用的 CRM 地址、成员身份和角色；永不返回 Token。"""
    url, _ = _connection_config()
    user = client().request("/api/auth/me")
    return {"connected": True, "url": url, "user": {key: user.get(key) for key in ["id", "name", "email", "role"]}}


@mcp.tool(annotations=READ_ONLY)
def search_media(
    query: str = "",
    country: str = "",
    channel: str = "",
    cooperation_status: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """搜索媒体/KOL，可按名称、国家、渠道和合作状态筛选。"""
    return client().request("/api/media", query={"q": query, "country": country, "platform_type": channel, "cooperation_status": cooperation_status, "page_size": max(1, min(limit, 100))})


@mcp.tool(annotations=READ_ONLY)
def get_media(media_id: int) -> dict[str, Any]:
    """读取一个媒体/KOL 的档案、联系人和地址。"""
    return client().request(f"/api/media/{media_id}")


@mcp.tool(annotations=READ_ONLY)
def list_follow_up_tasks(queue: Literal["today", "overdue", "upcoming", "all"] = "today") -> dict[str, Any]:
    """读取今日、逾期、未来或全部合作跟进任务。"""
    return client().request("/api/workbench", query={"queue": queue})


@mcp.tool(annotations=READ_ONLY)
def list_collaborations(media_id: int | None = None, owner_id: int | None = None, limit: int = 50) -> dict[str, Any]:
    """列出合作执行单，可按媒体或负责人筛选。"""
    return client().request("/api/campaigns", query={"media_id": media_id, "owner_id": owner_id, "page_size": max(1, min(limit, 100))})


@mcp.tool(annotations=READ_ONLY)
def get_collaboration(collaboration_id: int) -> dict[str, Any]:
    """读取合作详情、阶段、下一步、寄样、产出和费用。"""
    return client().request(f"/api/collaborations/{collaboration_id}")


@mcp.tool(annotations=READ_ONLY)
def list_audit_logs(limit: int = 50) -> dict[str, Any]:
    """读取 CRM 最近的修改审计记录。"""
    return client().request("/api/audit-logs", query={"limit": max(1, min(limit, 100))})


@mcp.tool(annotations=READ_ONLY)
def prepare_media_update(media_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """预览媒体字段修改，不写入。返回的 change_set_id 需经用户确认后才能应用。"""
    invalid = sorted(set(updates) - MEDIA_UPDATE_FIELDS)
    if invalid:
        raise ValueError(f"不允许通过 MCP 修改这些字段：{', '.join(invalid)}")
    media = client().request(f"/api/media/{media_id}")["media"]
    diff = {key: {"before": media.get(key), "after": value} for key, value in updates.items() if media.get(key) != value}
    if not diff:
        return {"changed": False, "message": "数据没有变化"}
    change_set_id = _new_change_set("media_update", {"media_id": media_id, "before": {key: media.get(key) for key in diff}, "updates": updates})
    return {"changed": True, "change_set_id": change_set_id, "expires_in_minutes": 15, "diff": diff}


@mcp.tool(annotations=WRITE)
def apply_media_update(change_set_id: str, reason: str) -> dict[str, Any]:
    """应用已确认的媒体修改预览。只有用户明确确认后才能调用。"""
    plan = _change_set(change_set_id, "media_update")
    data = plan.payload
    api = client()
    current = api.request(f"/api/media/{data['media_id']}")["media"]
    if any(current.get(key) != value for key, value in data["before"].items()):
        raise ValueError("预览后媒体数据已被修改，请重新生成预览")
    payload = {key: current.get(key) for key in MEDIA_FIELDS}
    payload.update(data["updates"])
    result = api.request(f"/api/media/{data['media_id']}", method="PUT", data=payload, reason=_require_reason(reason))
    CHANGE_SETS.pop(change_set_id, None)
    return {"applied": True, "media": result}


@mcp.tool(annotations=READ_ONLY)
def prepare_collaboration_update(collaboration_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """预览合作执行单修改，不写入。"""
    invalid = sorted(set(updates) - COLLABORATION_UPDATE_FIELDS)
    if invalid:
        raise ValueError(f"不允许通过 MCP 修改这些字段：{', '.join(invalid)}")
    current = client().request(f"/api/collaborations/{collaboration_id}")
    diff = {key: {"before": current.get(key), "after": value} for key, value in updates.items() if current.get(key) != value}
    if not diff:
        return {"changed": False, "message": "数据没有变化"}
    change_set_id = _new_change_set("collaboration_update", {"collaboration_id": collaboration_id, "before": {key: current.get(key) for key in diff}, "updates": updates})
    return {"changed": True, "change_set_id": change_set_id, "expires_in_minutes": 15, "diff": diff}


@mcp.tool(annotations=WRITE)
def apply_collaboration_update(change_set_id: str, reason: str) -> dict[str, Any]:
    """应用已确认的合作执行单修改预览。只有用户明确确认后才能调用。"""
    plan = _change_set(change_set_id, "collaboration_update")
    data = plan.payload
    api = client()
    current = api.request(f"/api/collaborations/{data['collaboration_id']}")
    if any(current.get(key) != value for key, value in data["before"].items()):
        raise ValueError("预览后合作数据已被修改，请重新生成预览")
    result = api.request(f"/api/collaborations/{data['collaboration_id']}", method="PATCH", data=data["updates"], reason=_require_reason(reason))
    CHANGE_SETS.pop(change_set_id, None)
    return {"applied": True, "collaboration": result}


@mcp.tool(annotations=READ_ONLY)
def preview_bulk_status_cleanup() -> dict[str, Any]:
    """扫描非标准合作状态并生成批量清洗预览；不会写入。"""
    rows = client().request("/api/media", query={"page_size": 500})["items"]
    changes = []
    for item in rows:
        raw = (item.get("cooperation_status") or "").strip()
        if not raw or raw in CANONICAL_COOPERATION_STATUSES:
            continue
        target = _legacy_status(raw)
        marker = f"[原合作状态] {raw}"
        notes = (item.get("notes") or "").strip()
        changes.append({"id": item["id"], "name": item["name"], "before": raw, "after": target, "notes_before": notes, "notes_after": notes if marker in notes else "\n".join(part for part in [notes, marker] if part)})
    change_set_id = _new_change_set("status_cleanup", {"changes": changes}) if changes else None
    return {"total": len(changes), "change_set_id": change_set_id, "expires_in_minutes": 15 if changes else None, "items": changes[:100], "truncated": len(changes) > 100}


@mcp.tool(annotations=WRITE)
def apply_bulk_status_cleanup(change_set_id: str, reason: str) -> dict[str, Any]:
    """应用用户已确认的批量状态清洗预览，并把原状态保留到备注。"""
    plan = _change_set(change_set_id, "status_cleanup")
    api = client()
    applied, skipped = [], []
    for change in plan.payload["changes"]:
        current = api.request(f"/api/media/{change['id']}")["media"]
        if current.get("cooperation_status") != change["before"] or (current.get("notes") or "").strip() != change["notes_before"]:
            skipped.append({"id": change["id"], "reason": "预览后数据已变化"})
            continue
        payload = {key: current.get(key) for key in MEDIA_FIELDS}
        payload["cooperation_status"] = change["after"]
        payload["notes"] = change["notes_after"]
        api.request(f"/api/media/{change['id']}", method="PUT", data=payload, reason=_require_reason(reason))
        applied.append(change["id"])
    CHANGE_SETS.pop(change_set_id, None)
    return {"applied": len(applied), "applied_ids": applied, "skipped": skipped}


@mcp.tool(annotations=READ_ONLY)
def preview_bulk_profile_link_split() -> dict[str, Any]:
    """扫描粘连在 website_url 中的多个主页并生成拆分预览；不会写入。"""
    rows = client().request("/api/media", query={"page_size": 500})["items"]
    changes = []
    for item in rows:
        if item.get("profile_links"):
            continue
        raw = item.get("website_url") or ""
        links = _profile_links(raw)
        if links:
            changes.append({"id": item["id"], "name": item["name"], "website_before": raw, "links_after": links})
    change_set_id = _new_change_set("profile_split", {"changes": changes}) if changes else None
    return {"total": len(changes), "change_set_id": change_set_id, "expires_in_minutes": 15 if changes else None, "items": changes[:100], "truncated": len(changes) > 100}


@mcp.tool(annotations=WRITE)
def apply_bulk_profile_link_split(change_set_id: str, reason: str) -> dict[str, Any]:
    """应用用户已确认的批量主页拆分预览。"""
    plan = _change_set(change_set_id, "profile_split")
    api = client()
    applied, skipped = [], []
    for change in plan.payload["changes"]:
        current = api.request(f"/api/media/{change['id']}")["media"]
        if current.get("profile_links") or (current.get("website_url") or "") != change["website_before"]:
            skipped.append({"id": change["id"], "reason": "预览后数据已变化"})
            continue
        payload = {key: current.get(key) for key in MEDIA_FIELDS}
        payload["profile_links"] = change["links_after"]
        payload["website_url"] = change["links_after"][0]["url"]
        api.request(f"/api/media/{change['id']}", method="PUT", data=payload, reason=_require_reason(reason))
        applied.append(change["id"])
    CHANGE_SETS.pop(change_set_id, None)
    return {"applied": len(applied), "applied_ids": applied, "skipped": skipped}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
