"""File system tools: read_file, write_file, edit_file, list_dir."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from oracle.tools.base import tool
import oracle.config as _cfg

log = logging.getLogger(__name__)


def _resolve_safe(path: str) -> Path:
    """Resolve path and ensure it stays within cwd. Raises PermissionError otherwise."""
    resolved = Path(path).expanduser().resolve()
    cwd = Path.cwd().resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError:
        raise PermissionError(f"Path '{path}' escapes the project root.")
    return resolved


def _check_path_policy(path: str) -> None:
    """Raise PermissionError if path targets an Oracle-protected source file."""
    cfg = _cfg.get()
    resolved = Path(path).expanduser().resolve()
    cwd = Path.cwd().resolve()
    for protected in cfg.core_protected_paths:
        p = (cwd / protected.rstrip("/")).resolve()
        # Use path-aware containment: resolved == p or resolved is inside p
        if resolved == p:
            raise PermissionError(
                f"[Path policy] Writing to '{path}' is not permitted. "
                "Oracle cannot modify its own source code."
            )
        try:
            resolved.relative_to(p)
            raise PermissionError(
                f"[Path policy] Writing to '{path}' is not permitted. "
                "Oracle cannot modify its own source code."
            )
        except ValueError:
            pass  # not under this protected path


@tool(description="Read file contents, optionally within a line range.", requires_permission=False, read_only=True)
async def read_file(
    path: Annotated[str, "Path to the file to read"],
    start_line: Annotated[int | None, "Starting line number (1-indexed, inclusive)"] = None,
    end_line: Annotated[int | None, "Ending line number (1-indexed, inclusive)"] = None,
) -> str:
    resolved = _resolve_safe(path)
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not resolved.is_file():
        raise IsADirectoryError(f"Path is a directory: {path}")

    text = resolved.read_text(errors="replace")
    if start_line is None and end_line is None:
        return text

    lines = text.splitlines(keepends=True)
    s = (start_line - 1) if start_line else 0
    e = end_line if end_line else len(lines)
    return "".join(lines[s:e])


@tool(description="Write full content to a file, creating parent directories if needed.", requires_permission=True)
async def write_file(
    path: Annotated[str, "Path to write"],
    content: Annotated[str, "Full file content to write"],
) -> str:
    _check_path_policy(path)
    resolved = _resolve_safe(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content)
    return f"Written {len(content)} bytes to {path}"


@tool(description="Replace an exact string within a file.", requires_permission=True)
async def edit_file(
    path: Annotated[str, "Path to the file to edit"],
    old_string: Annotated[str, "Exact string to find and replace"],
    new_string: Annotated[str, "Replacement string"],
) -> str:
    _check_path_policy(path)
    resolved = _resolve_safe(path)
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {path}")

    original = resolved.read_text(errors="replace")
    if old_string not in original:
        raise ValueError(
            f"old_string not found in {path}. "
            f"The string you tried to replace (first 200 chars): {old_string[:200]!r}"
        )

    count = original.count(old_string)
    updated = original.replace(old_string, new_string, 1)
    resolved.write_text(updated)
    note = "" if count == 1 else f" (warning: {count} matches, replaced first occurrence)"
    return f"Edited {path}{note}"


@tool(description="List directory contents with file/directory type annotation.", requires_permission=False, read_only=True)
async def list_dir(
    path: Annotated[str, "Directory path to list"] = ".",
) -> str:
    resolved = _resolve_safe(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries = []
    for entry in sorted(resolved.iterdir(), key=lambda e: (not e.is_dir(), e.name)):
        tag = "[dir]" if entry.is_dir() else "[file]"
        entries.append(f"{tag}  {entry.name}")
    return "\n".join(entries) if entries else "(empty directory)"
