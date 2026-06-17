"""System prompt builder."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oracle.skills.loader import Skill


def build(
    config_model: str,
    memories: list[str],
    active_skill: "Skill | None" = None,
    project_instructions_file: str = "ORACLE.md",
    tool_xml_instructions: bool = False,
) -> str:
    parts: list[str] = []

    parts.append(
        "You are Oracle, a powerful local AI agent. "
        "You have access to tools for reading/writing files, running shell commands, "
        "searching the web, and more. "
        "Use tools proactively to complete tasks accurately. "
        "Always read files before editing them. "
        "Return tool-free plain text only when the task is fully complete."
    )

    # Operating context
    parts.append(
        f"\n[Environment]\n"
        f"OS: {platform.system()} {platform.machine()}\n"
        f"Shell: {os.environ.get('SHELL', 'bash')}\n"
        f"Working directory: {Path.cwd()}\n"
        f"Model: {config_model}"
    )

    # Memories
    if memories:
        mem_lines = "\n".join(f"- {m}" for m in memories)
        parts.append(f"\n[Memory — relevant prior context]\n{mem_lines}")

    # Global instructions (~/.oracle/ORACLE.md) — applied before project-local
    global_oracle = Path.home() / ".oracle" / "ORACLE.md"
    if global_oracle.exists():
        parts.append(f"\n[Global Instructions]\n{global_oracle.read_text()}")

    # Project instructions (ORACLE.md in cwd) — overrides or extends global
    if project_instructions_file:
        oracle_md = Path(project_instructions_file)
        if oracle_md.exists():
            parts.append(f"\n[Project Instructions]\n{oracle_md.read_text()}")

    # Active skill injection
    if active_skill is not None:
        parts.append(f"\n[Skill: {active_skill.name}]\n{active_skill.body}")

    # Text-only model XML tool instructions
    if tool_xml_instructions:
        parts.append(
            "\n[Tool Use]\n"
            "To call a tool, output EXACTLY:\n"
            "<tool_call>\n"
            '{"name": "tool_name", "arguments": {"param": "value"}}\n'
            "</tool_call>\n"
            "Do not call multiple tools in one response. Wait for the result before proceeding."
        )

    return "\n".join(parts)
