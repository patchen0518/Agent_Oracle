"""Semantic memory via ChromaDB — degrades gracefully if not installed."""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

log = logging.getLogger(__name__)

try:
    import chromadb  # type: ignore[import-not-found]
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    log.warning("chromadb not installed — running in no-memory mode")


class OracleMemory:
    """Persistent semantic memory backed by ChromaDB. No-ops when unavailable."""

    def __init__(self, palace_path: str = "~/.oracle/palace") -> None:
        self._collection = None
        if not _AVAILABLE:
            return
        try:
            import os
            path = os.path.expanduser(palace_path)
            client = chromadb.PersistentClient(path=path)
            self._collection = client.get_or_create_collection("oracle_memory")
        except Exception as e:
            log.warning(f"ChromaDB failed to initialize ({e}) — running in no-memory mode")

    @property
    def available(self) -> bool:
        return self._collection is not None

    async def save_turn(self, user_msg: str, assistant_msg: str) -> None:
        if not self.available:
            return
        loop = asyncio.get_running_loop()
        try:
            doc = f"User: {user_msg}\nOracle: {assistant_msg}"
            await loop.run_in_executor(
                None,
                lambda: self._collection.add(documents=[doc], ids=[str(uuid4())]),
            )
        except Exception as e:
            log.warning(f"Memory save failed (non-fatal): {e}")

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        if not self.available or not query.strip():
            return []
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(
                None,
                lambda: self._collection.query(query_texts=[query], n_results=top_k),
            )
            docs = results.get("documents", [[]])[0]
            return docs
        except Exception as e:
            log.warning(f"Memory retrieve failed (non-fatal): {e}")
            return []
