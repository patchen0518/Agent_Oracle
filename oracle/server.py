"""FastAPI app, WebSocket handler, static file mount, slash command dispatcher."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from oracle.agent_loop import SessionState, run_turn
from oracle.context import compaction
from oracle.context.history import HistoryDB
from oracle.context.memory import OracleMemory
from oracle.llm.capabilities import ModelCapability, detect as detect_capability
from oracle.llm.ollama_client import OllamaClient
from oracle.skills.loader import SkillRegistry
from oracle.tools.base import ToolRegistry, REGISTRY
from oracle.ui.permissions import PermissionGate
import oracle.config as _cfg

log = logging.getLogger(__name__)

_STATIC = Path(__file__).parent / "ui" / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

# Single active connection guard
_active_ws: WebSocket | None = None

# Module-level shared state (set in startup)
_llm: OllamaClient | None = None
_capability: ModelCapability = ModelCapability.TOOLS
_memory: OracleMemory | None = None
_history_db: HistoryDB | None = None
_skill_registry: SkillRegistry | None = None


@app.get("/")
async def index():
    return FileResponse(str(_STATIC / "index.html"))


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    global _active_ws

    await websocket.accept()

    # Multi-tab protection
    if _active_ws is not None:
        await websocket.send_json({
            "type": "error",
            "message": "Oracle is already open in another tab. Please close this tab.",
        })
        await websocket.close()
        return

    _active_ws = websocket
    config = _cfg.get()
    llm = _llm
    memory = _memory or OracleMemory()
    history_db = _history_db or HistoryDB()
    skill_registry = _skill_registry or SkillRegistry()

    session = SessionState(session_id=session_id)
    session.session_db_id = history_db.create_session(session_id)

    permission_gate = PermissionGate()

    # Active turn task reference for cancellation
    _turn_task: asyncio.Task | None = None

    # Send initial mode
    await websocket.send_json({"type": "mode", "mode": config.mode})

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "stop":
                if _turn_task and not _turn_task.done():
                    _turn_task.cancel()
                    # Task's CancelledError handler sends done
                else:
                    await websocket.send_json({"type": "done"})
                continue

            if msg_type == "permission":
                permission_gate.resolve(raw.get("request_id", ""), raw.get("action", "deny"))
                continue

            if msg_type == "plan_approve":
                session._plan_approved = True
                session._plan_event.set()
                continue

            if msg_type == "plan_reject":
                session._plan_approved = False
                session._plan_event.set()
                continue

            if msg_type == "proposal_decision":
                # Phase 11 — handled by evolution module when present
                continue

            if msg_type == "slash":
                cmd = raw.get("command", "").strip()
                await _handle_slash(cmd, session, websocket, config, llm, history_db, skill_registry, permission_gate)
                continue

            if msg_type == "message":
                content = raw.get("content", "").strip()
                if not content:
                    continue

                # Detect slash in message body
                if content.startswith("/"):
                    await _handle_slash(content, session, websocket, config, llm, history_db, skill_registry, permission_gate)
                    continue

                # Reject new messages while a turn is in progress
                if _turn_task and not _turn_task.done():
                    await websocket.send_json({"type": "error", "message": "Busy — please wait for the current turn to finish."})
                    continue

                async def _do_turn(msg=content):
                    try:
                        await run_turn(
                            user_message=msg,
                            session=session,
                            llm=llm,
                            tool_registry=REGISTRY,
                            memory=memory,
                            history_db=history_db,
                            config=config,
                            ws=websocket,
                            skill_registry=skill_registry,
                            capability=_capability,
                            permission_gate=permission_gate,
                        )
                    except asyncio.CancelledError:
                        try:
                            await websocket.send_json({"type": "done"})
                        except Exception:
                            pass
                    except Exception as e:
                        log.exception(f"Turn error: {e}")
                        try:
                            await websocket.send_json({"type": "error", "message": str(e)})
                            await websocket.send_json({"type": "done"})
                        except Exception:
                            pass

                _turn_task = asyncio.create_task(_do_turn())
                # Don't await — the receive loop must stay alive to handle
                # permission responses, plan approvals, and stop signals

    except WebSocketDisconnect:
        log.info(f"Session {session_id} disconnected")
    except Exception as e:
        log.exception(f"WebSocket error: {e}")
    finally:
        _active_ws = None


async def _handle_slash(
    cmd: str,
    session: SessionState,
    ws: WebSocket,
    config,
    llm: OllamaClient | None,
    history_db: HistoryDB,
    skill_registry: SkillRegistry,
    permission_gate: PermissionGate,
) -> None:
    """Dispatch slash commands."""
    parts = cmd.lstrip("/").split(None, 1)
    name = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if name == "help":
        await ws.send_json({"type": "system_message", "content": _help_text()})

    elif name == "clear":
        session.history.clear()
        session.modified_paths.clear()
        await ws.send_json({"type": "mode", "mode": config.mode})
        await ws.send_json({"type": "system_message", "content": "Conversation cleared."})

    elif name == "history":
        msgs = history_db.get_messages(session.session_db_id, limit=20)
        lines = []
        for m in msgs:
            role = m.get("role", "?")
            content = (m.get("content") or "")[:300]
            lines.append(f"[{role}]: {content}")
        text = "\n\n".join(lines) if lines else "(no history)"
        await ws.send_json({"type": "system_message", "content": text})

    elif name == "compact":
        if not llm:
            await ws.send_json({"type": "system_message", "content": "LLM not available."})
            return
        await ws.send_json({"type": "system_message", "content": "Compacting history…"})
        new_history, old_count = await compaction.compact(session.history, llm)
        session.history = new_history
        await ws.send_json({"type": "compact_done", "collapsed": old_count})
        await ws.send_json({"type": "system_message", "content": f"Compacted {old_count} messages into 1 summary."})

    elif name == "yolo":
        config.auto_approve = not config.auto_approve
        state = "ON" if config.auto_approve else "OFF"
        if config.auto_approve:
            config.mode = "yolo"
        else:
            config.mode = "default"
        await ws.send_json({"type": "mode", "mode": config.mode})
        await ws.send_json({"type": "system_message", "content": f"YOLO mode {state}. All permissions auto-approved."})

    elif name == "auto-mode":
        if config.mode == "auto":
            config.mode = "default"
            await ws.send_json({"type": "mode", "mode": "default"})
            await ws.send_json({"type": "system_message", "content": "Auto mode OFF."})
        else:
            config.mode = "auto"
            config.auto_approve = False
            await ws.send_json({"type": "mode", "mode": "auto"})
            await ws.send_json({"type": "system_message", "content": "Auto mode ON — tool loop runs to completion."})

    elif name == "plan-mode":
        if config.mode == "plan":
            config.mode = "default"
            await ws.send_json({"type": "mode", "mode": "default"})
            await ws.send_json({"type": "system_message", "content": "Plan mode OFF."})
        else:
            config.mode = "plan"
            config.auto_approve = False
            await ws.send_json({"type": "mode", "mode": "plan"})
            await ws.send_json({"type": "system_message", "content": "Plan mode ON — Oracle will present a plan before acting."})

    elif name == "tools":
        from oracle.tools.base import REGISTRY
        lines = []
        for td in REGISTRY.list_all():
            perm = "🔒" if td.requires_permission else "✓"
            lines.append(f"{perm} {td.name}: {td.description}")
        await ws.send_json({"type": "system_message", "content": "Tools:\n" + "\n".join(lines)})

    elif name == "verify":
        if not session.modified_paths:
            await ws.send_json({"type": "system_message", "content": "Nothing was modified this turn — nothing to verify."})
            return
        if not llm:
            await ws.send_json({"type": "system_message", "content": "LLM not available."})
            return
        await _handle_verify(session, ws, llm)

    elif name == "memory":
        from oracle.context.memory import OracleMemory
        mem = OracleMemory()
        if not mem.available:
            await ws.send_json({"type": "system_message", "content": "MemPalace not available (no-memory mode)."})
            return
        results = await mem.retrieve(arg, top_k=5)
        text = "\n\n".join(f"- {r}" for r in results) if results else "(no relevant memories found)"
        await ws.send_json({"type": "system_message", "content": f"Memory results for '{arg}':\n{text}"})

    elif name == "model":
        if not arg:
            # List models
            from oracle.tools.base import REGISTRY
            result = await REGISTRY.dispatch("bash_exec", {"cmd": "ollama list"})
            await ws.send_json({"type": "system_message", "content": f"Installed models:\n{result}"})
        else:
            # Switch model
            global _llm, _capability
            config.model = arg
            if _llm:
                _llm.model = arg
            new_cap = await detect_capability(arg, config.ollama_host)
            _capability = new_cap
            await ws.send_json({"type": "system_message", "content": f"Switched to model: {arg} ({new_cap.value})"})
            await ws.send_json({"type": "mode", "mode": config.mode})

    elif name == "skills":
        skill_registry.load()
        skills = skill_registry.list_all()
        if not skills:
            await ws.send_json({"type": "system_message", "content": "No skills found. Add .md files to ~/.oracle/skills/ or .oracle/skills/"})
            return
        lines = []
        for s in skills:
            lines.append(f"{s.name:20}  {s.description:50}  [{s.source}]")
        await ws.send_json({"type": "system_message", "content": "Skills:\n" + "\n".join(lines)})

    elif name == "mcp":
        await ws.send_json({"type": "system_message", "content": "MCP support available — configure servers in ~/.oracle/config.toml"})

    elif name == "quit":
        await ws.send_json({"type": "quit_ack"})
        await ws.close()

    else:
        # Try as a skill name
        skill = skill_registry.get(name)
        if skill:
            session.active_skill = skill
            await ws.send_json({
                "type": "system_message",
                "content": f"Skill '{skill.name}' activated. Send your next message to use it.",
            })
        else:
            await ws.send_json({
                "type": "system_message",
                "content": f"Unknown command: /{name}. Type /help for a list of commands.",
            })


async def _handle_verify(session: SessionState, ws: WebSocket, llm: OllamaClient) -> None:
    """Run /verify: read modified files, ask LLM for completeness report."""
    file_contents = {}
    for path in session.modified_paths:
        try:
            file_contents[path] = Path(path).read_text(errors="replace")
        except Exception as e:
            file_contents[path] = f"(could not read: {e})"

    files_text = "\n\n".join(
        f"=== {p} ===\n{c}" for p, c in file_contents.items()
    )
    verify_prompt = (
        f"You completed a task. Review your work for accuracy and completeness.\n\n"
        f"Original request: {session.original_message}\n\n"
        f"Files you modified and their current content:\n{files_text}\n\n"
        "Report:\n"
        "1. What was done correctly\n"
        "2. Anything missing, incorrect, or incomplete\n"
        "3. Overall verdict: COMPLETE / INCOMPLETE / UNCERTAIN"
    )
    try:
        result = await llm.chat([{"role": "user", "content": verify_prompt}])
        text = result.text.strip()

        # Update SQLite verdict if we have an outcome ID
        if session.turn_outcome_id:
            try:
                from oracle.context.history import HistoryDB
                db = HistoryDB()
                verdict = "COMPLETE" if "COMPLETE" in text.upper() else ("INCOMPLETE" if "INCOMPLETE" in text.upper() else "UNCERTAIN")
                db.attach_verify_verdict(session.turn_outcome_id, verdict, text)
            except Exception:
                pass

        await ws.send_json({"type": "system_message", "content": f"[Verify]\n{text}"})
    except Exception as e:
        await ws.send_json({"type": "system_message", "content": f"[Verify error] {e}"})


def _help_text() -> str:
    return """Oracle Commands
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/help           This help message
/clear          Wipe conversation history
/history        Show last 20 messages from this session
/compact        Summarize history into one context block
/model [name]   List Ollama models or switch to a model
/tools          List all available tools
/yolo           Toggle auto-approve for all actions
/auto-mode      Toggle autonomous tool loop
/plan-mode      Toggle plan-before-act mode
/memory <q>     Search MemPalace for relevant memories
/verify         Review modified files for correctness
/skills         List all available skills
/mcp            Show MCP server status
/quit           Stop Oracle and close the browser

Keyboard shortcuts:
  Enter          Submit message
  Shift+Enter    New line"""


def init(
    config,
    llm: OllamaClient,
    capability: ModelCapability,
    memory: OracleMemory,
    history_db: HistoryDB,
    skill_registry: SkillRegistry,
) -> None:
    """Called from cli.py after startup to inject shared state."""
    global _llm, _capability, _memory, _history_db, _skill_registry
    _llm = llm
    _capability = capability
    _memory = memory
    _history_db = history_db
    _skill_registry = skill_registry
    _cfg.set_active(config)
