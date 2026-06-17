"""Ollama AsyncClient wrapper with streaming and tool-calling support."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import AsyncIterator

from ollama import AsyncClient

log = logging.getLogger(__name__)


@dataclass
class ChatChunk:
    text: str = ""
    tool_calls: list = field(default_factory=list)
    done: bool = False
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class OllamaClient:
    def __init__(self, host: str, model: str) -> None:
        self._client = AsyncClient(host=host)
        self.model = model

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """
        Yields ChatChunk objects.
        - Mid-stream: chunk.text = new token, chunk.done = False
        - Final: chunk.text = full text, chunk.tool_calls = [...], chunk.done = True
        """
        kwargs: dict = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools

        full_text = ""
        final_tool_calls: list = []
        prompt_eval_count = None
        eval_count = None

        async for raw in await self._client.chat(**kwargs):
            content = (raw.message.content or "") if raw.message else ""
            if content:
                full_text += content
                yield ChatChunk(text=content, done=False)

            if raw.message and raw.message.tool_calls:
                final_tool_calls = list(raw.message.tool_calls)

            if raw.done:
                prompt_eval_count = getattr(raw, "prompt_eval_count", None)
                eval_count = getattr(raw, "eval_count", None)

        yield ChatChunk(
            text=full_text,
            tool_calls=final_tool_calls,
            done=True,
            prompt_eval_count=prompt_eval_count,
            eval_count=eval_count,
        )

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatChunk:
        """Non-streaming chat. Returns a single ChatChunk with full response."""
        kwargs: dict = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            kwargs["tools"] = tools

        resp = await self._client.chat(**kwargs)
        return ChatChunk(
            text=resp.message.content or "",
            tool_calls=list(resp.message.tool_calls or []),
            done=True,
            prompt_eval_count=getattr(resp, "prompt_eval_count", None),
            eval_count=getattr(resp, "eval_count", None),
        )
