from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_URL = "http://127.0.0.1:8000"


class PangdunError(RuntimeError):
    pass


class PangdunClient:
    """Small shared client used by both the human CLI and the local MCP server."""

    def __init__(self, base_url: str = DEFAULT_URL, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(
        self,
        path: str,
        method: str = "GET",
        data: Any = None,
        query: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> Any:
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
            raise PangdunError(f"API {exc.code}: {detail}") from exc
        except URLError as exc:
            raise PangdunError(f"无法连接 CRM：{exc.reason}") from exc
