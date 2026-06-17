"""Oracle agent loop — tool-calling iteration engine, mode-aware."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from oracle.context import system_prompt as _sp
from oracle.llm.capabilities import ModelCapability
from oracle.fallback import react_parser

if TYPE_CHECKING:
    from fastapi.websockets import WebSocket
    from oracle.config import Config
    from oracle.context.history import HistoryDB
    from oracle.context.memory import OracleMemory
    from oracle.llm.ollama_client import OllamaClient
    from oracle.skills.loader import Skill, SkillRegistry
    from oracle.tools.base import ToolRegistry
    from oracle.ui.permissions import PermissionGate

log = logging.getLogger(__name__)


@dataclass
class SessionState:
    session_id: str
    session_db_id: int = 0
    history: list = field(default_factory=list)  # non-system messages, grows across turns

    # Per-turn state (reset at start of each turn)
    original_message: str = ""
    modified_paths: set = field(default_factory=set)
    completion_retry_used: bool = False
    hit_iteration_limit: bool = False
    iterations_used: int = 0
    tool_errors: list = field(default_factory=list)
    turn_outcome_id: int | None = None
    completion_check_result: str | None = None

    # Skill activated for next turn
    active_skill: "Skill | None" = None

    # Token counts from last turn
    last_prompt_eval_count: int | None = None
    last_eval_count: int | None = None

    # Plan-mode gate
    _plan_event: asyncio.Event = field(default_factory=asyncio.Event)
    _plan_approved: bool = False


def _format_tool_summary(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        if msg.get("role") == "assistant":
            calls = msg.get("tool_calls") or []
            for c in calls:
                fn = c.get("function", {})
                lines.append(f"- Called {fn.get('name')} with {fn.get('arguments', {})}")
        elif msg.get("role") == "tool":
            content = (msg.get("content") or "")[:200]
            lines.append(f"  → Result: {content}")
    return "\n".join(lines) or "(no tool calls)"


def _estimate_tokens(messages: list[dict]) -> int:
    total = sum(len((m.get("content") or "").encode("utf-8")) for m in messages)
    return total // 3


async def _generate_plan(
    user_message: str,
    llm: "OllamaClient",
    tool_registry: "ToolRegistry",
) -> list[str]:
    system = (
        "You are in plan mode. Given the user's request and available tools, "
        "produce a numbered execution plan. Do not execute tools yet. "
        "Format: one step per line, starting with 'Step N: …'"
    )
    tool_names = [t.name for t in tool_registry.list_all()]
    prompt = (
        f"Available tools: {', '.join(tool_names)}\n\n"
        f"User request: {user_message}\n\n"
        "Produce a concise numbered execution plan:"
    )
    chunk = await llm.chat([
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ])
    steps = []
    for line in chunk.text.splitlines():
        line = line.strip()
        if line and (line[0].isdigit() or line.lower().startswith("step")):
            steps.append(line)
    return steps or [chunk.text.strip()]


async def run_turn(
    user_message: str,
    session: "SessionState",
    llm: "OllamaClient",
    tool_registry: "ToolRegistry",
    memory: "OracleMemory",
    history_db: "HistoryDB",
    config: "Config",
    ws: "WebSocket",
    skill_registry: "SkillRegistry",
    capability: ModelCapability,
    permission_gate: "PermissionGate",
) -> None:
    # Reset per-turn state
    session.original_message = user_message
    session.modified_paths = set()
    session.completion_retry_used = False
    session.hit_iteration_limit = False
    session.iterations_used = 0
    session.tool_errors = []
    session.turn_outcome_id = None
    session.completion_check_result = None

    # 1. Retrieve memories
    memories = await memory.retrieve(user_message, top_k=config.memory_top_k)

    # 2. Build system prompt (consumes active_skill, clears it)
    active_skill = session.active_skill
    session.active_skill = None
    system_content = _sp.build(
        config_model=config.model,
        memories=memories,
        active_skill=active_skill,
        project_instructions_file=config.project_instructions_file,
        tool_xml_instructions=(capability == ModelCapability.TEXT_ONLY),
    )

    # 3. Plan mode — generate and await approval before tool loop
    if config.mode == "plan":
        plan_steps = await _generate_plan(user_message, llm, tool_registry)
        await ws.send_json({"type": "plan", "steps": plan_steps})
        session._plan_event.clear()
        session._plan_approved = False
        try:
            await asyncio.wait_for(session._plan_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            await ws.send_json({"type": "done"})
            return
        if not session._plan_approved:
            await ws.send_json({"type": "done"})
            return

    # 4. Prepare messages — system + history + user message
    messages: list[dict] = [
        {"role": "system", "content": system_content},
        *session.history,
        {"role": "user", "content": user_message},
    ]
    # Include user message in the slice we'll save to history
    history_start = len(messages) - 1

    tool_schemas = tool_registry.schemas() if capability == ModelCapability.TOOLS else None
    last_assistant_text = ""

    # 5. Tool loop
    for iteration in range(config.max_tool_iterations):
        session.iterations_used = iteration + 1

        # Stream LLM response
        final_chunk = None
        async for chunk in llm.stream_chat(messages, tools=tool_schemas):
            if not chunk.done:
                if chunk.text:
                    await ws.send_json({"type": "token", "content": chunk.text})
            else:
                final_chunk = chunk

        if final_chunk is None:
            break

        session.last_prompt_eval_count = final_chunk.prompt_eval_count
        session.last_eval_count = final_chunk.eval_count

        # Determine tool calls (native or XML fallback)
        if capability == ModelCapability.TEXT_ONLY:
            parsed_calls = react_parser.parse(final_chunk.text)
            display_text = react_parser.strip_tool_calls(final_chunk.text)
        else:
            parsed_calls = final_chunk.tool_calls
            display_text = final_chunk.text

        if not parsed_calls:
            # Pure text response — no tool calls
            last_assistant_text = display_text
            messages.append({"role": "assistant", "content": display_text})

            # Auto-mode completion check (Mechanism 2)
            if config.mode == "auto" and not session.completion_retry_used:
                await ws.send_json({"type": "completion_check", "status": "checking"})
                tool_summary = _format_tool_summary(messages)
                check_chunk = await llm.chat([{
                    "role": "user",
                    "content": (
                        f"Original request: {session.original_message}\n\n"
                        f"Actions taken:\n{tool_summary}\n\n"
                        "Is this task fully complete? Reply YES or NO, then briefly explain. "
                        "If NO, describe exactly what remains."
                    ),
                }])
                check_result = check_chunk.text.strip()
                if check_result.upper().startswith("NO"):
                    session.completion_retry_used = True
                    session.completion_check_result = "resumed"
                    await ws.send_json({"type": "completion_check", "status": "resuming"})
                    messages.append({"role": "user", "content":
                        f"[Completion check] {check_result}\nPlease complete the remaining steps."})
                    continue  # continue the for loop
                session.completion_check_result = "complete"
                await ws.send_json({"type": "completion_check", "status": "complete"})
            break  # turn done

        # Build assistant message with tool calls
        tool_call_list = []
        for tc in parsed_calls:
            call_id = getattr(tc, "id", None) or str(uuid4())
            fn_name = tc.function.name if hasattr(tc, "function") else tc.name
            fn_args = tc.function.arguments if hasattr(tc, "function") else tc.arguments
            tool_call_list.append({
                "id": call_id,
                "type": "function",
                "function": {"name": fn_name, "arguments": fn_args},
            })

        messages.append({
            "role": "assistant",
            "content": display_text or None,
            "tool_calls": tool_call_list,
        })

        # Execute each tool call
        for tc_dict in tool_call_list:
            call_id = tc_dict["id"]
            call_name = tc_dict["function"]["name"]
            call_args = tc_dict["function"]["arguments"]
            if not isinstance(call_args, dict):
                call_args = {}

            await ws.send_json({"type": "tool_start", "name": call_name, "args": call_args})

            # Permission gate
            tool_def = tool_registry.get(call_name)
            needs_permission = (
                (tool_def is None or tool_def.requires_permission)
                and not config.auto_approve
            )

            if needs_permission:
                request_id = str(uuid4())
                permission_gate.register(request_id)
                await ws.send_json({
                    "type": "permission_request",
                    "request_id": request_id,
                    "tool": call_name,
                    "args": call_args,
                })
                action = await permission_gate.wait(request_id)
                if action == "deny":
                    result = "[Denied by user]"
                    await ws.send_json({"type": "tool_result", "name": call_name, "result": result, "truncated": False})
                    messages.append({"role": "tool", "content": result, "tool_call_id": call_id})
                    continue
                if action == "always":
                    config.auto_approve = True

            # Dispatch
            try:
                result = await tool_registry.dispatch(call_name, call_args)
            except Exception as e:
                result = f"[Tool error] {type(e).__name__}: {e}"
                session.tool_errors.append({"tool": call_name, "error": str(e)})

            # Truncate large output
            result_bytes = result.encode("utf-8", errors="replace")
            truncated = len(result_bytes) > config.max_output_bytes
            if truncated:
                result = result_bytes[:config.max_output_bytes].decode("utf-8", errors="replace") + "\n[...truncated]"

            # Post-write read-back (Mechanism 1)
            if call_name == "write_file":
                path = call_args.get("path", "")
                session.modified_paths.add(path)
                try:
                    actual = Path(path).read_text(errors="replace")
                    intended = call_args.get("content", "")
                    if actual.strip() != intended.strip():
                        await ws.send_json({
                            "type": "review_warning",
                            "message": f"Content mismatch in {path}",
                        })
                        result += f"\n[Read-back mismatch — actual file content]:\n{actual}"
                except Exception:
                    pass

            elif call_name == "edit_file":
                path = call_args.get("path", "")
                session.modified_paths.add(path)
                try:
                    actual = Path(path).read_text(errors="replace")
                    new_str = call_args.get("new_string", "")
                    if new_str and new_str not in actual:
                        await ws.send_json({
                            "type": "review_warning",
                            "message": f"Edit may not have applied in {path}",
                        })
                        old_str = call_args.get("old_string", "")[:200]
                        result += (
                            f"\n[Read-back check — new_string not found in file. "
                            f"Tried to replace:\n{old_str!r}\n"
                            f"Actual file (first 500 chars):\n{actual[:500]}]"
                        )
                except Exception:
                    pass

            await ws.send_json({"type": "tool_result", "name": call_name, "result": result, "truncated": truncated})
            messages.append({"role": "tool", "content": result, "tool_call_id": call_id})

    else:
        session.hit_iteration_limit = True

    # 6. Update session history (exclude system prompt)
    new_messages = messages[history_start:]
    session.history.extend(new_messages)

    # 7. Persist to SQLite (new_messages already starts with the user turn)
    try:
        for msg in new_messages:
            role = msg.get("role", "")
            content = msg.get("content")
            tool_calls = msg.get("tool_calls")
            history_db.append_message(session.session_db_id, role, content, tool_calls)
    except Exception as e:
        log.warning(f"SQLite persist failed (non-fatal): {e}")

    # 8. Save to MemPalace
    try:
        await memory.save_turn(user_message, last_assistant_text)
    except Exception as e:
        log.warning(f"Memory save failed (non-fatal): {e}")

    # 9. Phase 11 — record outcome
    try:
        outcome_id = history_db.record_outcome(session.session_db_id, {
            "original_message": session.original_message,
            "iterations_used": session.iterations_used,
            "hit_iteration_limit": session.hit_iteration_limit,
            "tool_errors_count": len(session.tool_errors),
            "tool_errors_summary": session.tool_errors or None,
            "completion_check_result": session.completion_check_result,
            "modified_paths": session.modified_paths,
        })
        session.turn_outcome_id = outcome_id
    except Exception as e:
        log.warning(f"Outcome recording failed (non-fatal): {e}")

    # 10. Send context usage update
    used = (
        (session.last_prompt_eval_count or 0) + (session.last_eval_count or 0)
        or _estimate_tokens(messages)
    )
    await ws.send_json({"type": "context", "used": used, "budget": config.context_token_budget})

    await ws.send_json({"type": "done"})
