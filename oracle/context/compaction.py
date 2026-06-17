"""Compact in-memory history via LLM summarization."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oracle.llm.ollama_client import OllamaClient

log = logging.getLogger(__name__)


async def compact(
    history: list[dict],
    llm: "OllamaClient",
) -> tuple[list[dict], int]:
    """
    Summarize history into a single synthetic assistant message.
    Returns (new_history, original_message_count).
    """
    original_count = len(history)
    if not history:
        return history, 0

    # Build a readable transcript for summarization
    lines = []
    for msg in history:
        role = msg.get("role", "?")
        content = msg.get("content") or ""
        if role == "tool":
            lines.append(f"[tool result]: {content[:500]}")
        elif role == "assistant":
            calls = msg.get("tool_calls", [])
            if calls:
                names = [c.get("function", {}).get("name", "?") for c in calls]
                lines.append(f"assistant called: {', '.join(names)}")
            if content:
                lines.append(f"assistant: {content}")
        else:
            lines.append(f"{role}: {content}")

    transcript = "\n".join(lines)

    prompt = (
        "Summarize the following conversation history into a concise context block. "
        "Preserve key facts, decisions, and outcomes. Omit tool invocation details "
        "unless they produced important results. Be thorough but compact.\n\n"
        f"HISTORY:\n{transcript}"
    )

    try:
        chunk = await llm.chat([{"role": "user", "content": prompt}])
        summary = chunk.text.strip()
    except Exception as e:
        log.warning(f"Compaction LLM call failed: {e}")
        return history, 0

    new_history = [{"role": "assistant", "content": f"[Compacted context]\n{summary}"}]
    return new_history, original_count
