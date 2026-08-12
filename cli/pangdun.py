#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_URL = "http://127.0.0.1:8000"
MEDIA_FIELDS = [
    "name", "country", "region", "category", "platform_type", "website_url",
    "profile_links", "followers_or_traffic", "audience_metric_type", "audience_metric_unit", "media_tier", "cooperation_status", "notes",
]
CANONICAL_COOPERATION_STATUSES = {"未联系", "待回复", "洽谈中", "已合作", "暂缓", "不合作", "待核验"}


class CliError(RuntimeError):
    pass


def config_path() -> Path:
    override = os.environ.get("PANGDUN_CONFIG")
    if override:
        return Path(override).expanduser()
    local = os.environ.get("LOCALAPPDATA")
    return (Path(local) / "PangdunCRM" / "cli.json") if local else (Path.home() / ".pangdun" / "cli.json")


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"无法读取 CLI 配置：{exc}") from exc


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


class Client:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(self, path: str, method: str = "GET", data: Any = None, query: dict[str, Any] | None = None, reason: str | None = None) -> Any:
        if query:
            clean = {key: value for key, value in query.items() if value is not None and value != ""}
            if clean:
                path = f"{path}?{urlencode(clean)}"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if reason:
            headers["X-Change-Reason"] = quote(reason, safe="")
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw).get("detail", raw)
            except json.JSONDecodeError:
                detail = raw or exc.reason
            raise CliError(f"API {exc.code}: {detail}") from exc
        except URLError as exc:
            raise CliError(f"无法连接 CRM：{exc.reason}") from exc


def dump_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def print_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> None:
    if not rows:
        print("没有记录")
        return
    widths = []
    for key, title in columns:
        widths.append(min(36, max(len(title), *(len(str(row.get(key) if row.get(key) is not None else "—")) for row in rows))))
    print("  ".join(title.ljust(widths[index]) for index, (_, title) in enumerate(columns)))
    print("  ".join("─" * width for width in widths))
    for row in rows:
        cells = []
        for index, (key, _) in enumerate(columns):
            value = str(row.get(key) if row.get(key) is not None else "—")
            cells.append((value[:widths[index] - 1] + "…" if len(value) > widths[index] else value).ljust(widths[index]))
        print("  ".join(cells))


def require_reason(args: argparse.Namespace) -> str:
    reason = (getattr(args, "reason", None) or "").strip()
    if not reason:
        raise CliError("写操作必须提供 --reason，说明本次修改原因")
    return reason


def show_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diff = {key: {"before": before.get(key), "after": value} for key, value in after.items() if before.get(key) != value}
    dump_json(diff)
    return diff


def classify_legacy_cooperation_status(value: str) -> str:
    compact = "".join(value.lower().split())
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


def auth_command(args: argparse.Namespace, config: dict[str, Any]) -> None:
    base_url = args.url or config.get("url") or DEFAULT_URL
    if args.auth_action == "login":
        email = args.email or input("邮箱：").strip()
        password = os.environ.get(args.password_env) if args.password_env else None
        password = password or getpass.getpass("密码：")
        result = Client(base_url).request("/api/auth/cli-token", method="POST", data={"email": email, "password": password})
        save_config({"url": base_url, "token": result["access_token"], "user": result["user"]})
        print(f"已登录：{result['user']['name']}（{result['user']['role']}），Token 有效期 {result['expires_in_days']} 天")
    elif args.auth_action == "status":
        user = Client(base_url, config.get("token")).request("/api/auth/me")
        dump_json(user) if args.json else print(f"{user['name']} <{user['email']}> · {user['role']}")
    elif args.auth_action == "logout":
        save_config({"url": base_url})
        print("本地 CLI Token 已清除")


def media_command(args: argparse.Namespace, client: Client) -> None:
    if args.media_action == "list":
        result = client.request("/api/media", query={"q": args.query, "country": args.country, "platform_type": args.channel, "min_volume": args.min_volume, "max_volume": args.max_volume, "cooperation_status": args.status, "page_size": args.limit})
        if args.json:
            dump_json(result)
        else:
            print_table(result["items"], [("id", "ID"), ("name", "名称"), ("country", "国家"), ("platform_type", "渠道"), ("audience_metric_type", "指标"), ("followers_or_traffic", "体量(K)"), ("cooperation_status", "合作状态")])
    elif args.media_action == "show":
        result = client.request(f"/api/media/{args.id}")
        dump_json(result)
    elif args.media_action == "update":
        result = client.request(f"/api/media/{args.id}")
        before = result["media"]
        updates = {key: value for key, value in {
            "name": args.name, "country": args.country, "category": args.category, "platform_type": args.channel,
            "media_tier": args.tier, "cooperation_status": args.status,
            "followers_or_traffic": args.followers, "website_url": args.website,
            "audience_metric_type": args.metric_type,
            "notes": args.notes,
        }.items() if value is not None}
        if args.profiles_json is not None:
            try:
                profiles = json.loads(args.profiles_json)
            except json.JSONDecodeError as exc:
                raise CliError(f"平台主页 JSON 无效: {exc}") from exc
            if not isinstance(profiles, list):
                raise CliError("--profiles-json 必须是 JSON 数组")
            updates["profile_links"] = profiles
        if not updates:
            raise CliError("没有提供需要修改的字段")
        diff = show_diff(before, updates)
        if not diff:
            print("数据没有变化")
            return
        if not args.apply:
            print("预览完成；加上 --apply --reason \"原因\" 才会写入")
            return
        payload = {key: before.get(key) for key in MEDIA_FIELDS}
        payload.update(updates)
        saved = client.request(f"/api/media/{args.id}", method="PUT", data=payload, reason=require_reason(args))
        dump_json(saved) if args.json else print(f"已更新媒体 #{saved['id']} {saved['name']}")
    elif args.media_action == "normalize":
        report = client.request("/api/media-data-quality")
        if args.json or args.apply:
            dump_json(report)
        else:
            print(f"媒体 {report['total']} · 可安全归一 {report['safe_changes']} · 待人工核验 {report['needs_review']}")
            for item in report["items"][:20]:
                print(f"- #{item['id']} {item['name']}: {'；'.join(item['changes'])}")
        if not args.apply:
            print("当前为 dry-run；加上 --apply --reason \"原因\" 才会写入")
            return
        result = client.request("/api/media-data-quality/normalize", method="POST", reason=require_reason(args))
        print(f"已归一 {result['updated']} 条媒体；{result['needs_review']} 个字段仍需人工核验")
    elif args.media_action == "split-links":
        result = client.request("/api/media", query={"page_size": 500})
        changes = []
        import re
        from urllib.parse import urlparse
        for item in result["items"]:
            if item.get("profile_links"):
                continue
            raw = item.get("website_url") or ""
            urls = []
            for url in re.findall(r"https?://[^\s()]+", raw, re.I):
                url = url.rstrip(".,;，；")
                if url.rstrip("/").lower() not in {x["url"].rstrip("/").lower() for x in urls}:
                    host = urlparse(url).netloc.lower()
                    platform = next((label for needle, label in [("youtube", "YouTube"), ("youtu.be", "YouTube"), ("instagram", "Instagram"), ("tiktok", "TikTok"), ("bilibili", "Bilibili"), ("facebook", "Facebook"), ("x.com", "X"), ("twitter", "X")] if needle in host), "网站")
                    urls.append({"platform": platform, "url": url})
            if urls and (urls != (item.get("profile_links") or []) or raw != urls[0]["url"]):
                changes.append((item, urls))
        print(f"发现 {len(changes)} 条主页链接需要拆分")
        for item, urls in changes:
            print(f"- #{item['id']} {item['name']}: " + "；".join(f"{x['platform']}={x['url']}" for x in urls))
        if not args.apply:
            print("当前为 dry-run；加上 --apply --reason \"原因\" 才会写入")
            return
        reason = require_reason(args)
        for item, urls in changes:
            payload = {key: item.get(key) for key in MEDIA_FIELDS}
            payload["profile_links"] = urls
            payload["website_url"] = urls[0]["url"]
            client.request(f"/api/media/{item['id']}", method="PUT", data=payload, reason=reason)
        print(f"已拆分并保存 {len(changes)} 条媒体主页")
    elif args.media_action == "clean-status":
        result = client.request("/api/media", query={"page_size": 500})
        changes = []
        for item in result["items"]:
            raw = (item.get("cooperation_status") or "").strip()
            if not raw or raw in CANONICAL_COOPERATION_STATUSES:
                continue
            target = classify_legacy_cooperation_status(raw)
            marker = f"[原合作状态] {raw}"
            notes = (item.get("notes") or "").strip()
            next_notes = notes if marker in notes else "\n".join(part for part in [notes, marker] if part)
            changes.append({"id": item["id"], "name": item["name"], "before": raw, "after": target, "notes": next_notes})
        summary: dict[str, int] = {}
        for change in changes:
            summary[change["after"]] = summary.get(change["after"], 0) + 1
        if args.json:
            dump_json({"total": len(changes), "summary": summary, "items": changes})
        else:
            print(f"发现 {len(changes)} 条非标准合作状态")
            for status, count in sorted(summary.items(), key=lambda pair: (-pair[1], pair[0])):
                print(f"- {status}: {count}")
            for change in changes[:30]:
                print(f"  #{change['id']} {change['name']}: {change['before']} → {change['after']}")
        if not args.apply:
            print("当前为 dry-run；加上 --apply --reason \"原因\" 才会写入")
            return
        reason = require_reason(args)
        for change in changes:
            item = next(row for row in result["items"] if row["id"] == change["id"])
            payload = {key: item.get(key) for key in MEDIA_FIELDS}
            payload["cooperation_status"] = change["after"]
            payload["notes"] = change["notes"]
            client.request(f"/api/media/{change['id']}", method="PUT", data=payload, reason=reason)
        print(f"已清洗 {len(changes)} 条合作状态，原始内容已保留到备注")


def collaboration_command(args: argparse.Namespace, client: Client) -> None:
    if args.collaboration_action == "list":
        result = client.request("/api/campaigns", query={"media_id": args.media_id, "owner_id": args.owner_id, "page_size": args.limit})
        if args.json:
            dump_json(result)
        else:
            rows = []
            for item in result["items"]:
                rows.append({**item, "media_name": (item.get("media") or {}).get("name"), "project_name": (item.get("project") or {}).get("name"), "owner_name": (item.get("owner") or {}).get("name")})
            print_table(rows, [("id", "ID"), ("media_name", "媒体"), ("project_name", "项目"), ("execution_status", "状态"), ("workflow_label", "跟进健康"), ("follow_up_date", "跟进日期"), ("owner_name", "负责人")])
    elif args.collaboration_action == "show":
        dump_json(client.request(f"/api/collaborations/{args.id}"))
    elif args.collaboration_action == "update":
        before = client.request(f"/api/collaborations/{args.id}")
        updates = {key: value for key, value in {
            "execution_status": args.status,
            "next_action": args.next_action,
            "follow_up_date": args.follow_up_date,
            "follow_up_priority": args.priority,
            "owner_id": args.owner_id,
            "follow_up_done": True if args.done else None,
        }.items() if value is not None}
        if not updates:
            raise CliError("没有提供需要修改的字段")
        diff = show_diff(before, updates)
        if not diff:
            print("数据没有变化")
            return
        if not args.apply:
            print("预览完成；加上 --apply --reason \"原因\" 才会写入")
            return
        saved = client.request(f"/api/collaborations/{args.id}", method="PATCH", data=updates, reason=require_reason(args))
        dump_json(saved) if args.json else print(f"已更新执行单 #{saved['id']} · {saved['execution_status']}")


def tasks_command(args: argparse.Namespace, client: Client) -> None:
    result = client.request("/api/workbench", query={"queue": args.queue})
    if args.json:
        dump_json(result)
    else:
        print_table(result["items"], [("id", "ID"), ("media_name", "媒体"), ("project_name", "项目"), ("next_action", "下一步"), ("workflow_label", "跟进健康"), ("follow_up_date", "日期"), ("execution_status", "状态"), ("owner", "负责人")])


def audit_command(args: argparse.Namespace, client: Client) -> None:
    result = client.request("/api/audit-logs", query={"limit": args.limit})
    if args.json:
        dump_json(result)
    else:
        print_table(result["items"], [("id", "ID"), ("created_at", "时间"), ("user", "操作者"), ("action", "动作"), ("entity_type", "对象"), ("entity_id", "对象ID"), ("reason", "原因")])


def contacts_command(args: argparse.Namespace, client: Client) -> None:
    report = client.request("/api/contact-duplicates")
    if args.json:
        dump_json(report)
    else:
        print(f"联系人 {report['contact_total']} · 重复组 {report['duplicate_groups']} · 可删除副本 {report['duplicate_rows']} · 关联地址 {report['linked_addresses']}")
        for item in report["items"][:25]:
            print(f"- 媒体 #{item['media_id']} · {item['name'] or '未命名'}：{item['count']} 条（{','.join(map(str, item['contact_ids']))}）")
    if not args.apply:
        print("当前为 dry-run；加上 --apply --reason \"原因\" 才会合并")
        return
    result = client.request("/api/contact-duplicates/merge", method="POST", reason=require_reason(args))
    print(f"已合并 {result['merged_groups']} 个重复组，删除 {result['removed']} 条副本，剩余 {result['remaining']} 条联系人，转移 {result['transferred_addresses']} 条地址关联")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pangdun", description="Pangdun CRM 命令行")
    parser.add_argument("--url", help="CRM 地址，例如 http://127.0.0.1:8000")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    commands = parser.add_subparsers(dest="command", required=True)

    auth = commands.add_parser("auth", help="CLI 认证")
    auth_sub = auth.add_subparsers(dest="auth_action", required=True)
    login = auth_sub.add_parser("login")
    login.add_argument("--email")
    login.add_argument("--password-env", default="PANGDUN_PASSWORD", help="从指定环境变量读取密码")
    auth_sub.add_parser("status")
    auth_sub.add_parser("logout")

    media = commands.add_parser("media", help="媒体/KOL")
    media_sub = media.add_subparsers(dest="media_action", required=True)
    media_list = media_sub.add_parser("list")
    media_list.add_argument("--query")
    media_list.add_argument("--country")
    media_list.add_argument("--channel")
    media_list.add_argument("--min-volume", type=float, help="最小体量，单位 K")
    media_list.add_argument("--max-volume", type=float, help="最大体量，单位 K")
    media_list.add_argument("--status")
    media_list.add_argument("--limit", type=int, default=50)
    media_show = media_sub.add_parser("show")
    media_show.add_argument("id", type=int)
    media_update = media_sub.add_parser("update")
    media_update.add_argument("id", type=int)
    media_update.add_argument("--name")
    media_update.add_argument("--country")
    media_update.add_argument("--category")
    media_update.add_argument("--channel")
    media_update.add_argument("--tier")
    media_update.add_argument("--status")
    media_update.add_argument("--followers", type=float, help="粉丝量或月访问量，单位 K")
    media_update.add_argument("--metric-type", choices=["粉丝量", "月访问量"])
    media_update.add_argument("--website")
    media_update.add_argument("--profiles-json", help='平台主页 JSON 数组，可包含 followers_k，例如 [{"platform":"Instagram","url":"https://...","followers_k":34.5}]')
    media_update.add_argument("--notes")
    media_update.add_argument("--apply", action="store_true")
    media_update.add_argument("--reason")
    normalize = media_sub.add_parser("normalize")
    normalize.add_argument("--apply", action="store_true")
    normalize.add_argument("--reason")
    split_links = media_sub.add_parser("split-links", help="将历史粘连主页拆为独立平台链接")
    split_links.add_argument("--apply", action="store_true")
    split_links.add_argument("--reason")
    clean_status = media_sub.add_parser("clean-status", help="清理历史合作状态并保留原始内容")
    clean_status.add_argument("--apply", action="store_true")
    clean_status.add_argument("--reason")

    collaboration = commands.add_parser("collaboration", aliases=["collab"], help="合作执行单")
    collab_sub = collaboration.add_subparsers(dest="collaboration_action", required=True)
    collab_list = collab_sub.add_parser("list")
    collab_list.add_argument("--media-id", type=int)
    collab_list.add_argument("--owner-id", type=int)
    collab_list.add_argument("--limit", type=int, default=50)
    collab_show = collab_sub.add_parser("show")
    collab_show.add_argument("id", type=int)
    collab_update = collab_sub.add_parser("update")
    collab_update.add_argument("id", type=int)
    collab_update.add_argument("--status")
    collab_update.add_argument("--next-action")
    collab_update.add_argument("--follow-up-date")
    collab_update.add_argument("--priority", choices=["高", "普通", "低"])
    collab_update.add_argument("--owner-id", type=int)
    collab_update.add_argument("--done", action="store_true")
    collab_update.add_argument("--apply", action="store_true")
    collab_update.add_argument("--reason")

    tasks = commands.add_parser("tasks", help="工作台任务")
    tasks.add_argument("queue", choices=["today", "overdue", "upcoming", "all"], default="today", nargs="?")
    audit = commands.add_parser("audit", help="审计日志")
    audit.add_argument("--limit", type=int, default=50)
    contacts = commands.add_parser("contacts", help="联系人数据治理")
    contacts.add_argument("--apply", action="store_true")
    contacts.add_argument("--reason")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        config = load_config()
        if args.command == "auth":
            auth_command(args, config)
            return 0
        token = os.environ.get("PANGDUN_TOKEN") or config.get("token")
        if not token:
            raise CliError("尚未登录。请先运行 pangdun auth login，或设置 PANGDUN_TOKEN")
        client = Client(args.url or config.get("url") or DEFAULT_URL, token)
        if args.command == "media":
            media_command(args, client)
        elif args.command in {"collaboration", "collab"}:
            collaboration_command(args, client)
        elif args.command == "tasks":
            tasks_command(args, client)
        elif args.command == "audit":
            audit_command(args, client)
        elif args.command == "contacts":
            contacts_command(args, client)
        return 0
    except CliError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
