"""Click CLI entry point. Handles startup, health check, and server launch."""

from __future__ import annotations

import asyncio
import logging
import time
import webbrowser
from pathlib import Path

import click
import httpx
import uvicorn
from rich.console import Console

console = Console()
log = logging.getLogger(__name__)


def _check_ollama(host: str) -> bool:
    """Return True if Ollama is reachable."""
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{host}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


@click.command()
@click.option("--model", "-m", default=None, help="Ollama model tag (e.g. gemma4:12b)")
@click.option("--port", "-p", default=None, type=int, help="Server port (default: 8000)")
@click.option("--yolo", is_flag=True, default=False, help="Auto-approve all actions")
@click.option("--no-stream", is_flag=True, default=False, help="Disable token streaming (debug)")
@click.option("--host", default=None, help="Ollama host URL")
def main(model, port, yolo, no_stream, host):
    """Oracle — local AI agent powered by Ollama."""
    import oracle.config as _cfg
    from oracle.context.history import HistoryDB
    from oracle.context.memory import OracleMemory
    from oracle.llm.capabilities import detect as detect_capability
    from oracle.llm.ollama_client import OllamaClient
    from oracle.skills.loader import SkillRegistry
    from oracle.tools import fs, search, shell, web  # trigger tool registration
    from oracle import server as srv

    logging.basicConfig(level=logging.WARNING)

    # Load config
    cfg = _cfg.load(model=model, port=port, yolo=yolo)
    if host:
        cfg.ollama_host = host
    _cfg.set_active(cfg)

    # Ensure ~/.oracle/ directories exist
    oracle_home = Path.home() / ".oracle"
    (oracle_home / "skills").mkdir(parents=True, exist_ok=True)
    (oracle_home / "palace").mkdir(parents=True, exist_ok=True)

    # Ollama health check
    if not _check_ollama(cfg.ollama_host):
        console.print(
            f"\n[bold red]Error:[/bold red] Cannot reach Ollama at {cfg.ollama_host}\n"
            "[yellow]To fix:[/yellow]\n"
            "  1. Install Ollama: https://ollama.com/download\n"
            "  2. Run: [bold]ollama serve[/bold]\n"
            "  3. Pull a model: [bold]ollama pull gemma4:12b[/bold]"
        )
        # Open error page in browser (uses static error.html if present)
        _open_error_page(cfg.port)
        return

    console.print(f"[green]✓[/green] Ollama reachable at {cfg.ollama_host}")
    console.print(f"[green]✓[/green] Model: {cfg.model}")

    # Async startup tasks
    async def _startup() -> tuple:
        cap = await detect_capability(cfg.model, cfg.ollama_host)
        return cap

    capability = asyncio.run(_startup())
    console.print(f"[green]✓[/green] Capability: {capability.value}")

    # Init shared components
    llm = OllamaClient(host=cfg.ollama_host, model=cfg.model)
    memory = OracleMemory(palace_path=str(oracle_home / "palace"))
    history_db = HistoryDB()
    skill_registry = SkillRegistry()
    skill_registry.load()

    # Wire into server
    srv.init(cfg, llm, capability, memory, history_db, skill_registry)

    # Open browser after short delay
    url = f"http://localhost:{cfg.port}"

    async def _open_browser():
        await asyncio.sleep(1.0)
        webbrowser.open(url)

    console.print(f"\n[bold green]Oracle ready![/bold green] Opening {url}\n")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    # Start uvicorn with browser open task
    config = uvicorn.Config(
        app=srv.app,
        host="127.0.0.1",
        port=cfg.port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    async def _serve():
        task = asyncio.create_task(_open_browser())
        await server.serve()
        task.cancel()

    asyncio.run(_serve())


def _open_error_page(port: int) -> None:
    """Try to open a simple error page. Falls back to printing instructions."""
    error_html = Path(__file__).parent / "ui" / "static" / "error.html"
    if error_html.exists():
        webbrowser.open(f"file://{error_html}")
