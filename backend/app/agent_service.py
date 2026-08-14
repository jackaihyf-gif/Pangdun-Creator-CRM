from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse, urlunsplit

import httpx

from .media_taxonomy import COOPERATION_STATUSES, MEDIA_CHANNELS
from .profile_links import clean_profile_links


DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
MAX_SOURCE_CHARS = 45_000
MAX_DOWNLOAD_BYTES = 2_000_000


class AgentConfigurationError(RuntimeError):
    pass


class AgentSourceError(ValueError):
    pass


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored and data.strip():
            self.parts.append(data.strip())


def agent_config() -> dict[str, Any]:
    from .youtube_service import youtube_config

    return {
        "configured": bool(os.getenv("DEEPSEEK_API_KEY")),
        "provider": "DeepSeek",
        "model": DEEPSEEK_MODEL,
        "youtube": youtube_config(),
    }


def test_deepseek_connection() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise AgentConfigurationError("尚未配置 DEEPSEEK_API_KEY")
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": "Reply only: OK"}],
        "thinking": {"type": "disabled"},
        "temperature": 0,
        "max_tokens": 4,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code in {401, 403}:
            raise AgentConfigurationError("DeepSeek API Key 无效或无访问权限")
        response.raise_for_status()
        body = response.json()
        if not body.get("choices"):
            raise RuntimeError("DeepSeek 返回了异常响应")
    except httpx.TimeoutException as exc:
        raise RuntimeError("连接 DeepSeek 超时") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"DeepSeek 连接失败（HTTP {exc.response.status_code}）") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("无法连接 DeepSeek 服务") from exc
    return f"{DEEPSEEK_MODEL} 可用"


def source_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_public_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AgentSourceError("请输入完整的 http:// 或 https:// 地址")
    host = parsed.hostname.casefold()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise AgentSourceError("Agent 不允许读取本机或局域网地址")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise AgentSourceError("无法解析该网址") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise AgentSourceError("Agent 不允许读取本机、局域网或保留地址")
    return value.strip()


def fetch_public_source(url: str) -> tuple[str, str]:
    current_url = validate_public_url(url)
    headers = {"User-Agent": "PangdunCRM-Agent/1.0 (+human-reviewed extraction)"}
    with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
        for _ in range(5):
            with client.stream("GET", current_url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise AgentSourceError("网页重定向缺少目标地址")
                    current_url = validate_public_url(urljoin(current_url, location))
                    continue
                response.raise_for_status()
                network_stream = response.extensions.get("network_stream")
                peer = network_stream.get_extra_info("server_addr") if network_stream else None
                if peer and not ipaddress.ip_address(peer[0]).is_global:
                    raise AgentSourceError("Agent 不允许读取本机、局域网或保留地址")
                try:
                    declared_size = int(response.headers.get("content-length") or 0)
                except ValueError:
                    declared_size = 0
                if declared_size > MAX_DOWNLOAD_BYTES:
                    raise AgentSourceError("网页内容过大，请粘贴需要提取的文字")
                chunks: list[bytes] = []
                received = 0
                for chunk in response.iter_bytes():
                    received += len(chunk)
                    if received > MAX_DOWNLOAD_BYTES:
                        raise AgentSourceError("网页内容过大，请粘贴需要提取的文字")
                    chunks.append(chunk)
                raw_body = b"".join(chunks)
                content_type = response.headers.get("content-type", "").casefold()
                encoding = response.encoding or "utf-8"
                body_text = raw_body.decode(encoding, errors="replace")
                final_url = str(response.url)
                break
        else:
            raise AgentSourceError("网页重定向次数过多")
    if "text/html" in content_type:
        parser = TextExtractor()
        parser.feed(body_text)
        text = "\n".join(parser.parts)
    elif "text/" in content_type or "json" in content_type:
        text = body_text
    else:
        raise AgentSourceError("当前网址不是可读取的网页文本；PDF Media Kit 请先复制文字到 Agent")
    compact = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not compact:
        raise AgentSourceError("网页没有可用于提取的文字")
    parsed_final = urlparse(final_url)
    safe_final_url = urlunsplit((parsed_final.scheme, parsed_final.netloc, parsed_final.path, "", ""))
    return compact[:MAX_SOURCE_CHARS], safe_final_url


SYSTEM_PROMPT = """你是 Pangdun KOL CRM 的档案提取助手。你的任务是从用户提供的网页、Media Kit、邮件或表格文本中提取可核验事实。
只输出 JSON 对象，不输出 Markdown。禁止猜测；没有证据的字段必须为 null 或空数组。
每个非空字段必须在 evidence 中提供不超过 160 字的原文证据，并在 confidence 中提供 0 到 1 的置信度。
粉丝量或网站月访问量统一换算为 K，例如 1250000 = 1250 K。合作状态只能使用：%s。
渠道优先使用：%s。联系人只提取明确出现的姓名、职位、邮箱、电话、WhatsApp 或 Telegram。
联系人最多返回 3 个，优先编辑、商务、PR 或寄样联系人；没有明确联系方式的普通作者不要逐个列出。
JSON 结构必须是：
{
  "summary": "一句话摘要",
  "media": {
    "name": null, "country": null, "platform_type": null, "category": null,
    "profile_links": [{"platform":"YouTube","url":"https://...","followers_k":null}],
    "followers_or_traffic": null, "audience_metric_type": null,
    "cooperation_status": null, "notes": null
  },
  "contacts": [{"name":null,"role":null,"email":null,"phone":null,"whatsapp":null,"telegram":null}],
  "evidence": {"media.name":"原文", "contacts.0.email":"原文"},
  "confidence": {"media.name":0.9, "contacts.0.email":1.0},
  "warnings": ["需要人工注意的矛盾或缺口"]
}""" % ("、".join(COOPERATION_STATUSES), "、".join(MEDIA_CHANNELS))


def deepseek_json_extract(content: str, source_label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise AgentConfigurationError("尚未配置 DEEPSEEK_API_KEY")
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"来源：{source_label}\n\n待提取内容：\n{content[:MAX_SOURCE_CHARS]}"},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0.1,
        "max_tokens": 2500,
        "stream": False,
    }
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
    body = response.json()
    choice = (body.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError("模型输出被截断，请缩短输入内容后重试")
    raw = ((choice.get("message") or {}).get("content") or "").strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("模型没有返回有效 JSON") from exc
    return normalize_agent_proposal(result, source_label), body.get("usage") or {}


def deepseek_json_object(system_prompt: str, user_prompt: str, *, max_tokens: int = 5000) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run a constrained JSON task without coupling it to the media profile schema."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise AgentConfigurationError("尚未配置 DEEPSEEK_API_KEY")
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt[:MAX_SOURCE_CHARS]},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0.05,
        "max_tokens": max_tokens,
        "stream": False,
    }
    with httpx.Client(timeout=90) as client:
        response = client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
    body = response.json()
    choice = (body.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError("模型输出被截断，请减少文件内容后重试")
    raw = ((choice.get("message") or {}).get("content") or "").strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("模型没有返回有效 JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("模型返回的 JSON 结构不正确")
    return result, body.get("usage") or {}


def normalize_agent_proposal(raw: dict[str, Any], source_label: str) -> dict[str, Any]:
    media = raw.get("media") if isinstance(raw.get("media"), dict) else {}
    contacts = raw.get("contacts") if isinstance(raw.get("contacts"), list) else []
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    confidence = raw.get("confidence") if isinstance(raw.get("confidence"), dict) else {}
    links = clean_profile_links(media.get("profile_links"), None)
    allowed_media = {
        "name": (str(media.get("name") or "").strip() or None),
        "country": (str(media.get("country") or "").strip() or None),
        "platform_type": (str(media.get("platform_type") or "").strip() or None),
        "category": (str(media.get("category") or "").strip() or None),
        "profile_links": links,
        "followers_or_traffic": media.get("followers_or_traffic"),
        "audience_metric_type": media.get("audience_metric_type"),
        "metric_source": (str(media.get("metric_source") or "").strip() or None),
        "metric_verified_at": media.get("metric_verified_at"),
        "cooperation_status": media.get("cooperation_status") if media.get("cooperation_status") in COOPERATION_STATUSES else None,
        "notes": (str(media.get("notes") or "").strip() or None),
    }
    clean_contacts = []
    for item in contacts[:10]:
        if not isinstance(item, dict):
            continue
        contact = {key: (str(item.get(key) or "").strip() or None) for key in ("name", "role", "email", "phone", "whatsapp", "telegram")}
        if any(contact.values()):
            clean_contacts.append(contact)
    clean_evidence = {str(key): str(value)[:160] for key, value in evidence.items() if value}
    clean_confidence = {}
    for key, value in confidence.items():
        try:
            score = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            continue
        # A model score is never sufficient without visible source evidence.
        clean_confidence[str(key)] = round(min(score, 0.95 if str(key) in clean_evidence else 0.49), 3)
    warnings = [str(item)[:240] for item in (raw.get("warnings") or []) if item][:20]
    missing_evidence = [key for key, value in flatten_proposed_fields(allowed_media, clean_contacts).items() if value not in (None, "", []) and key not in clean_evidence]
    if missing_evidence:
        warnings.append(f"{len(missing_evidence)} 个字段缺少原文证据，写入前必须人工核对")
    return {
        "summary": str(raw.get("summary") or "已生成媒体档案建议")[:300],
        "media": allowed_media,
        "contacts": clean_contacts,
        "evidence": clean_evidence,
        "confidence": clean_confidence,
        "warnings": warnings,
        "source_label": source_label,
    }


def flatten_proposed_fields(media: dict[str, Any], contacts: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {f"media.{key}": value for key, value in media.items()}
    for index, contact in enumerate(contacts):
        fields.update({f"contacts.{index}.{key}": value for key, value in contact.items()})
    return fields
