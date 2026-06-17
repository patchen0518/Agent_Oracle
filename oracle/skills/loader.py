"""Skill discovery and registry."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    source: str  # "global" | "project"
    created_by: str | None = None  # Phase 11 oracle-authored skills


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def load(self) -> None:
        """Discover and parse skills. Project-local skills override global ones."""
        self._skills.clear()
        self._load_dir(Path.home() / ".oracle" / "skills", "global")
        self._load_dir(Path.cwd() / ".oracle" / "skills", "project")

    def _load_dir(self, path: Path, source: str) -> None:
        if not path.exists():
            return
        for skill_file in sorted(path.glob("*.md")):
            try:
                skill = _parse_skill_file(skill_file, source)
                if skill:
                    self._skills[skill.name] = skill
            except Exception as e:
                log.warning(f"Failed to load skill {skill_file}: {e}")

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_all(self) -> list[Skill]:
        return list(self._skills.values())


def _parse_skill_file(path: Path, source: str) -> Skill | None:
    text = path.read_text()
    if not text.startswith("---"):
        return None

    # Split frontmatter from body
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter_raw = parts[1].strip()
    body = parts[2].strip()

    try:
        meta = yaml.safe_load(frontmatter_raw) or {}
    except Exception as e:
        log.warning(f"Invalid YAML in {path}: {e}")
        return None

    name = meta.get("name", "").strip()
    if not name:
        return None

    return Skill(
        name=name,
        description=meta.get("description", "").strip(),
        body=body,
        source=source,
        created_by=meta.get("created_by"),
    )
