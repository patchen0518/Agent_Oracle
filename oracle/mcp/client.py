"""MCP session manager — connect to external MCP servers and proxy tool calls."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oracle.config import MCPServerConfig

log = logging.getLogger(__name__)

MCP_CONNECT_TIMEOUT = 30

try:
    from mcp import ClientSession, StdioServerParameters  # type: ignore[import-not-found]
    from mcp.client.stdio import stdio_client  # type: ignore[import-not-found]
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    log.info("mcp package not installed — MCP support disabled")


class MCPSessionManager:
    def __init__(self, server_configs: "list[MCPServerConfig]") -> None:
        self._configs = server_configs
        self._sessions: dict[str, object] = {}
        self._errors: dict[str, str] = {}
        self._tools: dict[str, list[dict]] = {}

    async def connect_all(self) -> None:
        if not _MCP_AVAILABLE:
            return
        for cfg in self._configs:
            try:
                transport = await asyncio.wait_for(
                    stdio_client(StdioServerParameters(
                        command=cfg.command[0],
                        args=cfg.command[1:],
                        env=cfg.env or None,
                    )),
                    timeout=MCP_CONNECT_TIMEOUT,
                )
                session = ClientSession(*transport)
                await asyncio.wait_for(session.initialize(), timeout=MCP_CONNECT_TIMEOUT)
                self._sessions[cfg.name] = session

                # Discover tools
                tools_result = await session.list_tools()
                self._tools[cfg.name] = [
                    {"name": t.name, "description": t.description or "", "schema": t.inputSchema}
                    for t in tools_result.tools
                ]
                log.info(f"MCP server '{cfg.name}' connected with {len(self._tools[cfg.name])} tools")

            except asyncio.TimeoutError:
                reason = f"timed out after {MCP_CONNECT_TIMEOUT}s"
                self._errors[cfg.name] = reason
                log.warning(f"MCP server '{cfg.name}' {reason}")
            except Exception as e:
                reason = str(e)
                self._errors[cfg.name] = reason
                log.warning(f"MCP server '{cfg.name}' failed to connect: {e}")

    async def list_tools(self) -> dict[str, list[dict]]:
        return dict(self._tools)

    async def call_tool(self, server_name: str, tool_name: str, args: dict) -> str:
        session = self._sessions.get(server_name)
        if session is None:
            err = self._errors.get(server_name, "not connected")
            return f'[MCP error] server "{server_name}" is disconnected: {err}'
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, args),
                timeout=MCP_CONNECT_TIMEOUT,
            )
            if hasattr(result, "content"):
                parts = result.content
                text_parts = [p.text for p in parts if hasattr(p, "text")]
                return "\n".join(text_parts)
            return str(result)
        except asyncio.TimeoutError:
            return f"[MCP error] call timed out after {MCP_CONNECT_TIMEOUT}s"
        except json.JSONDecodeError as e:
            log.warning(f"MCP malformed response from {server_name}/{tool_name}: {e}")
            return f"[MCP error] malformed response: {e}"
        except Exception as e:
            return f"[MCP error] {type(e).__name__}: {e}"

    def status(self) -> list[dict]:
        result = []
        for cfg in self._configs:
            name = cfg.name
            connected = name in self._sessions
            result.append({
                "name": name,
                "connected": connected,
                "tool_count": len(self._tools.get(name, [])),
                "error": self._errors.get(name),
            })
        return result
