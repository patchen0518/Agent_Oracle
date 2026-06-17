"""Parse <tool_call>…</tool_call> XML from text-only model responses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)


@dataclass
class ParsedToolCall:
    name: str
    arguments: dict
    id: str = ""

    # Compatibility with ollama tool call interface
    @property
    def function(self):
        return self

    def __getattr__(self, item):
        return None


def parse(text: str) -> list[ParsedToolCall]:
    """Extract all <tool_call>{json}</tool_call> blocks from raw model text."""
    calls = []
    for match in _TOOL_CALL_RE.finditer(text):
        raw = match.group(1)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        name = data.get("name") or data.get("tool") or ""
        args = data.get("arguments") or data.get("args") or data.get("parameters") or {}
        if name:
            calls.append(ParsedToolCall(name=name, arguments=args))
    return calls


def strip_tool_calls(text: str) -> str:
    """Remove <tool_call>…</tool_call> blocks from display text."""
    return _TOOL_CALL_RE.sub("", text).strip()
