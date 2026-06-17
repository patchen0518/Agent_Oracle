"""WebSocket-based permission gate using asyncio.Event per request_id."""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)


class PermissionGate:
    """Manages pending permission requests keyed by request_id."""

    def __init__(self) -> None:
        self._pending: dict[str, tuple[asyncio.Event, list[str]]] = {}

    def register(self, request_id: str) -> None:
        event = asyncio.Event()
        self._pending[request_id] = (event, ["pending"])

    async def wait(self, request_id: str, timeout: float = 120) -> str:
        """Block until the request is resolved. Returns 'allow', 'deny', or 'always'."""
        if request_id not in self._pending:
            return "allow"
        event, result = self._pending[request_id]
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning(f"Permission request {request_id} timed out — defaulting to deny")
            result[0] = "deny"
        del self._pending[request_id]
        return result[0]

    def resolve(self, request_id: str, action: str) -> None:
        """Resolve a pending request with the given action."""
        if request_id in self._pending:
            event, result = self._pending[request_id]
            result[0] = action
            event.set()
