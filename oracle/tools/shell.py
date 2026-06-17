"""Shell tool: bash_exec with async subprocess and timeout."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from oracle.tools.base import tool

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60


@tool(description="Run a shell command and capture stdout+stderr. Requires user approval.", requires_permission=True)
async def bash_exec(
    cmd: Annotated[str, "Shell command to execute"],
    timeout: Annotated[int, "Timeout in seconds (max 300)"] = _DEFAULT_TIMEOUT,
    workdir: Annotated[str | None, "Working directory (defaults to project root)"] = None,
) -> str:
    timeout = min(int(timeout), 300)
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=workdir,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[Command timed out after {timeout}s]"

        output = stdout.decode(errors="replace")
        exit_code = proc.returncode
        if exit_code != 0:
            return f"[exit {exit_code}]\n{output}"
        return output or "(no output)"
    except Exception as e:
        return f"[Tool error] {type(e).__name__}: {e}"
