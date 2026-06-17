"""Bridge MCP tool schemas into the main ToolRegistry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oracle.mcp.client import MCPSessionManager
    from oracle.tools.base import ToolRegistry

log = logging.getLogger(__name__)


async def register_mcp_tools(
    session_manager: "MCPSessionManager",
    registry: "ToolRegistry",
) -> None:
    """Discover tools from connected MCP servers and add them to the tool registry."""
    from oracle.tools.base import ToolDef

    tools_by_server = await session_manager.list_tools()
    for server_name, tools in tools_by_server.items():
        for tool_info in tools:
            tool_name = f"mcp:{server_name}/{tool_info['name']}"
            schema = tool_info.get("schema") or {"type": "object", "properties": {}}

            # Create a closure capturing server_name and the original tool name
            _sn = server_name
            _tn = tool_info["name"]

            async def _dispatch(_sn=_sn, _tn=_tn, **kwargs) -> str:
                return await session_manager.call_tool(_sn, _tn, kwargs)

            registry.register(ToolDef(
                name=tool_name,
                description=tool_info.get("description", ""),
                func=_dispatch,
                parameters_schema=schema,
                requires_permission=True,
                read_only=False,
            ))
            log.debug(f"Registered MCP tool: {tool_name}")
