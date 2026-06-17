"""MemPalace semantic memory — degrades gracefully if not installed."""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)

try:
    from mempalace import Palace  # type: ignore[import-not-found]
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    log.warning("mempalace not installed — running in no-memory mode")


class OracleMemory:
    """Semantic memory via MemPalace. No-ops when unavailable."""

    def __init__(self, palace_path: str = "~/.oracle/palace") -> None:
        self._palace = None
        if not _AVAILABLE:
            return
        try:
            self._palace = Palace(palace_path)
        except Exception as e:
            log.warning(f"MemPalace failed to initialize ({e}) — running in no-memory mode")

    @property
    def available(self) -> bool:
        return self._palace is not None

    async def save_turn(self, user_msg: str, assistant_msg: str) -> None:
        if not self.available:
            return
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                self._palace.add,
                f"User: {user_msg}\nOracle: {assistant_msg}",
            )
        except Exception as e:
            log.warning(f"MemPalace save_turn failed (non-fatal): {e}")

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        if not self.available:
            return []
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(
                None, self._palace.search, query, top_k
            )
            return [r.content for r in results]
        except Exception as e:
            log.warning(f"MemPalace retrieve failed (non-fatal): {e}")
            return []
