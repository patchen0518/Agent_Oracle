"""Detect Ollama model capabilities via /api/show."""

from __future__ import annotations

import enum
import httpx
import logging

log = logging.getLogger(__name__)


class ModelCapability(enum.Enum):
    TOOLS = "tools"
    TEXT_ONLY = "text_only"


async def detect(model: str, host: str = "http://localhost:11434") -> ModelCapability:
    """Query /api/show and check if the model supports native tool calling."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{host}/api/show", json={"name": model})
            resp.raise_for_status()
            data = resp.json()
            caps = data.get("capabilities", [])
            if "tools" in caps:
                log.info(f"Model {model!r} supports native tool calling")
                return ModelCapability.TOOLS
    except Exception as e:
        log.warning(f"Capability detection failed ({e}); defaulting to TOOLS")
    return ModelCapability.TOOLS  # optimistic default — gemma4 has tools
