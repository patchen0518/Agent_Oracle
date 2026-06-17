"""Layered config: defaults → ~/.oracle/config.toml → .oracle.toml → env vars → CLI flags."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class MCPServerConfig:
    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    auto_approve: bool = False


@dataclass
class Config:
    # LLM
    model: str = "gemma4:12b"
    ollama_host: str = "http://localhost:11434"

    # Agent behaviour
    auto_approve: bool = False
    mode: str = "default"  # "default" | "auto" | "plan" | "yolo"
    max_tool_iterations: int = 20
    max_output_bytes: int = 16_384
    context_token_budget: int = 100_000

    # Persistence
    project_instructions_file: str = "ORACLE.md"
    brave_api_key: str | None = None

    # Server
    port: int = 8000
    memory_top_k: int = 5

    # MCP
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)

    # Phase 11 — self-evolution
    evolution_enabled: bool = True
    reflection_min_outcomes: int = 5
    reflection_window_days: int = 30
    max_generated_skills: int = 10
    core_protected_paths: list[str] = field(default_factory=lambda: [
        "oracle/", "oracle_server.py", "pyproject.toml"
    ])


def load(
    model: str | None = None,
    port: int | None = None,
    yolo: bool = False,
) -> Config:
    """Load config with layered precedence."""
    cfg = Config()

    # Layer 2: ~/.oracle/config.toml
    global_cfg = Path.home() / ".oracle" / "config.toml"
    if global_cfg.exists():
        _apply_toml(cfg, global_cfg)

    # Layer 3: .oracle.toml in cwd
    local_cfg = Path.cwd() / ".oracle.toml"
    if local_cfg.exists():
        _apply_toml(cfg, local_cfg)

    # Layer 4: environment variables
    if v := os.environ.get("ORACLE_MODEL"):
        cfg.model = v
    if v := os.environ.get("ORACLE_HOST"):
        cfg.ollama_host = v
    if os.environ.get("ORACLE_YOLO", "").strip() in ("1", "true", "yes"):
        cfg.auto_approve = True
    if v := os.environ.get("BRAVE_API_KEY"):
        cfg.brave_api_key = v

    # Layer 5: CLI flags
    if model:
        cfg.model = model
    if port is not None:
        cfg.port = port
    if yolo:
        cfg.auto_approve = True

    return cfg


def _apply_toml(cfg: Config, path: Path) -> None:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    if v := data.get("model"):
        cfg.model = str(v)
    if v := data.get("ollama_host"):
        cfg.ollama_host = str(v)
    if v := data.get("auto_approve"):
        cfg.auto_approve = bool(v)
    if v := data.get("mode"):
        cfg.mode = str(v)
    if v := data.get("max_tool_iterations"):
        cfg.max_tool_iterations = int(v)
    if v := data.get("max_output_bytes"):
        cfg.max_output_bytes = int(v)
    if v := data.get("context_token_budget"):
        cfg.context_token_budget = int(v)
    if v := data.get("port"):
        cfg.port = int(v)
    if v := data.get("memory_top_k"):
        cfg.memory_top_k = int(v)
    if v := data.get("brave_api_key"):
        cfg.brave_api_key = str(v)

    # MCP servers
    for srv in data.get("mcp_servers", []):
        cfg.mcp_servers.append(MCPServerConfig(
            name=srv["name"],
            command=srv["command"],
            env=srv.get("env", {}),
            auto_approve=srv.get("auto_approve", False),
        ))

    # Phase 11
    if v := data.get("evolution_enabled"):
        cfg.evolution_enabled = bool(v)
    if v := data.get("reflection_min_outcomes"):
        cfg.reflection_min_outcomes = int(v)
    if v := data.get("reflection_window_days"):
        cfg.reflection_window_days = int(v)
    if v := data.get("max_generated_skills"):
        cfg.max_generated_skills = int(v)
    if v := data.get("core_protected_paths"):
        cfg.core_protected_paths = list(v)


def save_toml(cfg: Config, scope: str = "local") -> Path:
    """Persist editable config fields using read-merge-write (preserves unknown keys)."""
    import tomli_w  # not imported at module level to keep startup lean

    if scope == "global":
        path = Path.home() / ".oracle" / "config.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        path = Path.cwd() / ".oracle.toml"

    # Read existing file so keys we don't own (mcp_servers, evolution fields, etc.) survive
    data: dict = {}
    if path.exists():
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            data = {}

    # Overlay only the fields the settings panel exposes
    data["model"] = cfg.model
    data["ollama_host"] = cfg.ollama_host
    data["port"] = cfg.port
    data["max_tool_iterations"] = cfg.max_tool_iterations
    data["max_output_bytes"] = cfg.max_output_bytes
    data["context_token_budget"] = cfg.context_token_budget
    data["memory_top_k"] = cfg.memory_top_k
    if cfg.brave_api_key:
        data["brave_api_key"] = cfg.brave_api_key
    else:
        data.pop("brave_api_key", None)

    with open(path, "wb") as f:
        tomli_w.dump(data, f)

    return path


# Module-level active config (set once in cli.py startup)
_active: Config | None = None


def get() -> Config:
    return _active if _active is not None else Config()


def set_active(cfg: Config) -> None:
    global _active
    _active = cfg
