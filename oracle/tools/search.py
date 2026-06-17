"""Search tools: grep (ripgrep fallback) and glob."""

from __future__ import annotations

import asyncio
import glob as _glob
import logging
import shutil
from pathlib import Path
from typing import Annotated

from oracle.tools.base import tool

log = logging.getLogger(__name__)

_RG = shutil.which("rg")


@tool(description="Search file contents by pattern. Uses ripgrep if available, falls back to grep.", requires_permission=False, read_only=True)
async def grep(
    pattern: Annotated[str, "Regex or literal search pattern"],
    path: Annotated[str, "File or directory to search"] = ".",
    case_sensitive: Annotated[bool, "Enable case-sensitive matching"] = True,
    max_results: Annotated[int, "Maximum number of matching lines to return"] = 200,
) -> str:
    if _RG:
        cmd = [_RG, "--line-number", "--no-heading"]
        if not case_sensitive:
            cmd.append("--ignore-case")
        cmd += [pattern, path]
    else:
        cmd = ["grep", "-rn"]
        if not case_sensitive:
            cmd.append("-i")
        cmd += [pattern, path]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        lines = stdout.decode(errors="replace").splitlines()
        if len(lines) > max_results:
            lines = lines[:max_results]
            lines.append(f"[...truncated at {max_results} results]")
        return "\n".join(lines) if lines else "(no matches)"
    except asyncio.TimeoutError:
        return "[Tool error] grep timed out after 30s"
    except Exception as e:
        return f"[Tool error] {type(e).__name__}: {e}"


@tool(description="Find files matching a glob pattern.", requires_permission=False, read_only=True)
async def glob(
    pattern: Annotated[str, "Glob pattern (e.g. '**/*.py')"],
    base_path: Annotated[str, "Base directory for the search"] = ".",
) -> str:
    base = Path(base_path).resolve()
    matches = sorted(base.glob(pattern))
    if not matches:
        return "(no files matched)"
    lines = [str(m.relative_to(base)) for m in matches[:500]]
    if len(matches) > 500:
        lines.append("[...truncated at 500 results]")
    return "\n".join(lines)
