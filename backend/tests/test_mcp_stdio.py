from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[2]


def test_local_mcp_stdio_lists_expected_tools():
    async def run() -> None:
        env = os.environ.copy()
        env["PANGDUN_TOKEN"] = "protocol-test-token"
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "pangdun_mcp.server"],
            cwd=str(ROOT),
            env=env,
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                assert "search_media" in tools
                assert "prepare_media_update" in tools
                assert "preview_bulk_status_cleanup" in tools
                assert "apply_bulk_profile_link_split" in tools
                assert tools["search_media"].annotations.readOnlyHint is True
                assert tools["apply_bulk_profile_link_split"].annotations.readOnlyHint is False

    asyncio.run(run())
