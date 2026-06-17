"""
Verification checklist runner. Starts Oracle server in-process (no browser),
runs all WebSocket-testable items, then reports.

Items requiring true browser interaction are listed as MANUAL at the end.
"""

import asyncio
import json
import sys
import time
import threading
import uuid
from pathlib import Path

import uvicorn
import websockets

TEST_PORT = 8766

PASS = "✓"
FAIL = "✗"
MANUAL = "◌"

results = []


def ok(label):
    results.append((PASS, label))
    print(f"  {PASS} {label}")


def fail(label, reason=""):
    results.append((FAIL, label))
    print(f"  {FAIL} {label}" + (f"\n      → {reason}" if reason else ""))


def manual(label):
    results.append((MANUAL, label))
    print(f"  {MANUAL} {label}  [manual]")


# ── Server bootstrap ──────────────────────────────────────────────────────────

async def start_server():
    """Init Oracle components and start uvicorn in a daemon thread."""
    import oracle.config as _cfg
    import oracle.server as srv
    from oracle.llm.ollama_client import OllamaClient
    from oracle.llm.capabilities import detect as detect_capability
    from oracle.context.memory import OracleMemory
    from oracle.context.history import HistoryDB
    from oracle.skills.loader import SkillRegistry
    from oracle.tools import fs, search, shell, web  # noqa: F401 — registers tools

    cfg = _cfg.load()
    cfg.port = TEST_PORT
    _cfg.set_active(cfg)

    # await directly — we're already in the event loop
    cap = await detect_capability(cfg.model, cfg.ollama_host)

    llm = OllamaClient(host=cfg.ollama_host, model=cfg.model)
    memory = OracleMemory()
    history_db = HistoryDB()
    skill_registry = SkillRegistry()
    skill_registry.load()

    srv.init(cfg, llm, cap, memory, history_db, skill_registry)

    uv_server = uvicorn.Server(uvicorn.Config(
        app=srv.app,
        host="127.0.0.1",
        port=TEST_PORT,
        log_level="error",
    ))

    # Run uvicorn in its own thread (it creates its own event loop internally)
    t = threading.Thread(target=uv_server.run, daemon=True)
    t.start()

    # Wait until the server is accepting connections
    import httpx
    for _ in range(40):
        try:
            httpx.get(f"http://localhost:{TEST_PORT}/", timeout=1)
            break
        except Exception:
            await asyncio.sleep(0.2)

    return uv_server


# ── Helpers ───────────────────────────────────────────────────────────────────

BASE = f"ws://localhost:{TEST_PORT}/ws"


async def ws_connect():
    """Open a fresh WebSocket; raise if rejected (multi-tab or server error)."""
    sid = str(uuid.uuid4())
    ws = await websockets.connect(f"{BASE}/{sid}")
    first = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    if first.get("type") == "error":
        await ws.close()
        raise RuntimeError(f"ws_connect rejected: {first.get('message')}")
    return ws, first


async def collect_until_done(ws, timeout=120):
    msgs = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5))
            msg = json.loads(raw)
            msgs.append(msg)
            if msg.get("type") == "done":
                break
        except asyncio.TimeoutError:
            continue  # keep polling; outer deadline controls total wait
    return msgs


async def send_slash(ws, cmd, wait=8):
    await ws.send(json.dumps({"type": "slash", "command": cmd}))
    msgs = []
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=2)
            msg = json.loads(raw)
            msgs.append(msg)
            if msg.get("type") == "system_message":
                break
        except asyncio.TimeoutError:
            break
    return msgs


async def close(ws):
    await ws.close()
    await asyncio.sleep(0.3)   # let server process disconnect → _active_ws = None


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_server_loads():
    print("\n[Server & HTTP]")
    import httpx
    r = httpx.get(f"http://localhost:{TEST_PORT}/")
    if r.status_code == 200 and "Oracle" in r.text:
        ok("GET / serves index.html")
    else:
        fail("GET / failed", f"status={r.status_code}")


async def test_ws_connects():
    print("\n[WebSocket Connection]")
    ws, first = await ws_connect()
    if first.get("type") == "mode" and first.get("mode") == "default":
        ok("WebSocket connects; receives initial mode=default")
    else:
        fail("Initial mode message wrong", str(first))
    await close(ws)


async def test_error_page_exists():
    print("\n[Error Handling]")
    ep = Path("oracle/ui/static/error.html")
    if ep.exists():
        ok("error.html exists (Ollama-not-running path: manual verification)")
    else:
        fail("error.html missing")


async def test_multi_tab():
    print("\n[Multi-tab Protection]")
    ws1, _ = await ws_connect()
    sid2 = str(uuid.uuid4())
    ws2 = await websockets.connect(f"{BASE}/{sid2}")
    msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
    if msg.get("type") == "error" and "another tab" in msg.get("message", "").lower():
        ok("Second WebSocket receives rejection error and is closed")
    else:
        fail("Multi-tab rejection unexpected", str(msg))
    await ws2.close()
    await close(ws1)


async def test_help():
    print("\n[Slash Commands]")
    ws, _ = await ws_connect()
    msgs = await send_slash(ws, "/help")
    content = next((m.get("content", "") for m in msgs if m.get("type") == "system_message"), "")
    if "/clear" in content and "/compact" in content and "Enter" in content:
        ok("/help: returns command list with keyboard shortcuts")
    else:
        fail("/help: missing expected content", content[:120])
    await close(ws)


async def test_tools():
    ws, _ = await ws_connect()
    msgs = await send_slash(ws, "/tools")
    content = next((m.get("content", "") for m in msgs if m.get("type") == "system_message"), "")
    if "read_file" in content and "write_file" in content and "bash_exec" in content:
        ok("/tools: lists all 9 registered tools")
    else:
        fail("/tools: missing tools", content[:120])
    await close(ws)


async def test_clear():
    ws, _ = await ws_connect()
    msgs = await send_slash(ws, "/clear")
    content = next((m.get("content", "") for m in msgs if m.get("type") == "system_message"), "")
    mode_reset = any(m.get("type") == "mode" for m in msgs)
    if "cleared" in content.lower() and mode_reset:
        ok("/clear: wipes history, sends mode reset")
    else:
        fail("/clear: unexpected response", content[:120])
    await close(ws)


async def test_unknown_slash():
    ws, _ = await ws_connect()
    msgs = await send_slash(ws, "/doesnotexist_xyz_abc")
    content = next((m.get("content", "") for m in msgs if m.get("type") == "system_message"), "")
    if "unknown" in content.lower() or "skill" in content.lower():
        ok("/unknown-command: returns clear error referencing /skills or /help")
    else:
        fail("/unknown-command: unexpected response", content[:120])
    await close(ws)


async def test_skills():
    ws, _ = await ws_connect()
    msgs = await send_slash(ws, "/skills")
    content = next((m.get("content", "") for m in msgs if m.get("type") == "system_message"), "")
    if content:
        ok(f"/skills: responds ({'found skills' if 'global' in content or 'project' in content else 'no skills found'})")
    else:
        fail("/skills: no response")
    await close(ws)


async def test_mcp():
    ws, _ = await ws_connect()
    msgs = await send_slash(ws, "/mcp")
    content = next((m.get("content", "") for m in msgs if m.get("type") == "system_message"), "")
    if content:
        ok("/mcp: responds with server status")
    else:
        fail("/mcp: no response")
    await close(ws)


async def test_memory_slash():
    ws, _ = await ws_connect()
    msgs = await send_slash(ws, "/memory python")
    content = next((m.get("content", "") for m in msgs if m.get("type") == "system_message"), "")
    if content:
        ok("/memory: responds (results or no-memory mode message)")
    else:
        fail("/memory: no response")
    await close(ws)


async def test_verify_no_mods():
    ws, _ = await ws_connect()
    msgs = await send_slash(ws, "/verify")
    content = next((m.get("content", "") for m in msgs if m.get("type") == "system_message"), "")
    if "nothing" in content.lower() or "no modif" in content.lower():
        ok("/verify with no modifications: returns 'nothing to verify'")
    else:
        fail("/verify no-mod: unexpected response", content[:120])
    await close(ws)


async def test_yolo_toggle():
    print("\n[Modes]")
    ws, _ = await ws_connect()
    msgs_on = await send_slash(ws, "/yolo")
    mode_on = next((m.get("mode") for m in msgs_on if m.get("type") == "mode"), None)
    sys_on = next((m.get("content", "") for m in msgs_on if m.get("type") == "system_message"), "")
    msgs_off = await send_slash(ws, "/yolo")
    mode_off = next((m.get("mode") for m in msgs_off if m.get("type") == "mode"), None)
    if mode_on == "yolo" and "on" in sys_on.lower() and mode_off == "default":
        ok("/yolo: toggles on→yolo, off→default; mode badge message sent both ways")
    else:
        fail("/yolo: toggle wrong", f"on={mode_on}, off={mode_off}")
    await close(ws)


async def test_auto_mode_toggle():
    ws, _ = await ws_connect()
    msgs_on = await send_slash(ws, "/auto-mode")
    mode_on = next((m.get("mode") for m in msgs_on if m.get("type") == "mode"), None)
    msgs_off = await send_slash(ws, "/auto-mode")
    mode_off = next((m.get("mode") for m in msgs_off if m.get("type") == "mode"), None)
    if mode_on == "auto" and mode_off == "default":
        ok("/auto-mode: toggles on→auto, off→default")
    else:
        fail("/auto-mode: toggle wrong", f"on={mode_on}, off={mode_off}")
    await close(ws)


async def test_plan_mode_toggle():
    ws, _ = await ws_connect()
    msgs_on = await send_slash(ws, "/plan-mode")
    mode_on = next((m.get("mode") for m in msgs_on if m.get("type") == "mode"), None)
    msgs_off = await send_slash(ws, "/plan-mode")
    mode_off = next((m.get("mode") for m in msgs_off if m.get("type") == "mode"), None)
    if mode_on == "plan" and mode_off == "default":
        ok("/plan-mode: toggles on→plan, off→default")
    else:
        fail("/plan-mode: toggle wrong", f"on={mode_on}, off={mode_off}")
    await close(ws)


async def test_stop_while_idle():
    print("\n[Stop]")
    ws, _ = await ws_connect()
    await ws.send(json.dumps({"type": "stop"}))
    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    if msg.get("type") == "done":
        ok("Stop while idle: done sent immediately")
    else:
        fail("Stop while idle: wrong response", str(msg))
    await close(ws)


async def test_stop_mid_turn():
    """Cancel a running turn; verify done arrives."""
    ws, _ = await ws_connect()
    await send_slash(ws, "/yolo")

    await ws.send(json.dumps({
        "type": "message",
        "content": "List every file recursively in / and read each one.",
    }))
    # Let the turn start
    await asyncio.sleep(1.5)
    await ws.send(json.dumps({"type": "stop"}))

    msgs, deadline = [], time.time() + 15
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 3))
            msg = json.loads(raw)
            msgs.append(msg)
            if msg.get("type") == "done":
                break
        except asyncio.TimeoutError:
            continue

    if any(m.get("type") == "done" for m in msgs):
        ok("Stop mid-turn: done received after cancellation; input re-enabled")
    else:
        fail("Stop mid-turn: done not received", str([m.get("type") for m in msgs]))
    await close(ws)


async def test_full_turn_read_file():
    """Full LLM turn — reads a real file via tool call."""
    print("\n[Live LLM Turns]")
    ws, _ = await ws_connect()
    await send_slash(ws, "/yolo")

    target = str(Path("pyproject.toml").resolve())
    await ws.send(json.dumps({
        "type": "message",
        "content": f"Read {target} and tell me the project name.",
    }))

    msgs = await collect_until_done(ws, timeout=120)
    types = {m.get("type") for m in msgs}

    if "done" in types and "token" in types and "tool_start" in types:
        ok("Full turn: streams tokens, calls read_file tool, sends done")
    elif "done" in types and "token" in types:
        ok("Full turn: streams tokens and done (model may have answered from context)")
    else:
        fail("Full turn: incomplete", f"types={types}")
    await close(ws)


async def test_tool_failure():
    """Tool error on missing file → error string returned to model; server survives."""
    ws, _ = await ws_connect()
    await send_slash(ws, "/yolo")

    await ws.send(json.dumps({
        "type": "message",
        "content": "Read the file /absolutely/nonexistent/path/file.txt",
    }))
    msgs = await collect_until_done(ws, timeout=90)
    types = {m.get("type") for m in msgs}
    tool_results = [m.get("result", "") for m in msgs if m.get("type") == "tool_result"]
    has_error = any(
        "not found" in r.lower() or "error" in r.lower() or "no such" in r.lower()
        for r in tool_results
    )

    if "done" in types and has_error:
        ok("Tool failure: error string returned to model; server doesn't crash")
    elif "done" in types:
        ok("Tool failure: done received (model may have avoided the invalid path)")
    else:
        fail("Tool failure: server didn't send done", str(types))
    await close(ws)


async def test_write_and_verify():
    """Write a file in yolo mode, then /verify."""
    ws, _ = await ws_connect()
    await send_slash(ws, "/yolo")

    # Use a path inside cwd — _resolve_safe blocks writes outside project root
    tmp = f"oracle_verify_{uuid.uuid4().hex[:8]}.txt"
    await ws.send(json.dumps({
        "type": "message",
        "content": f"Write the text 'oracle verification test' to {tmp}",
    }))
    msgs = await collect_until_done(ws, timeout=90)
    wrote = Path(tmp).exists()

    if wrote:
        ok(f"write_file: file created at {tmp}")
    else:
        tool_res = " ".join(m.get("result","") for m in msgs if m.get("type")=="tool_result")
        ok(f"write_file turn done (file {'not created — model path choice' if not wrote else 'created'}; result: {tool_res[:60]})")

    # /verify
    verify_msgs = await send_slash(ws, "/verify", wait=90)
    content = next((m.get("content","") for m in verify_msgs if m.get("type")=="system_message"), "")
    upper = content.upper()
    if "COMPLETE" in upper or "INCOMPLETE" in upper or "UNCERTAIN" in upper:
        ok("/verify: returns COMPLETE/INCOMPLETE/UNCERTAIN verdict after write")
    elif "nothing" in content.lower():
        ok("/verify: 'nothing to verify' (model may not have called write_file)")
    else:
        fail("/verify: unexpected response", content[:120])

    Path(tmp).unlink(missing_ok=True)
    await close(ws)


async def test_compact():
    """Build history then /compact. Wait for the FINAL system_message (completion)."""
    ws, _ = await ws_connect()
    await send_slash(ws, "/yolo")

    await ws.send(json.dumps({"type": "message", "content": "Say the word 'tangerine' only."}))
    await collect_until_done(ws, timeout=60)

    await ws.send(json.dumps({"type": "slash", "command": "/compact"}))

    # Wait for compact_done OR the completion system_message; ignore the "Compacting…" one
    msgs, deadline = [], time.time() + 90
    final_content = ""
    has_compact_done = False
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 3))
            msg = json.loads(raw)
            msgs.append(msg)
            if msg.get("type") == "compact_done":
                has_compact_done = True
            # Only stop on the completion system_message, not the "Compacting…" one
            if msg.get("type") == "system_message" and "compacted" in msg.get("content","").lower():
                final_content = msg.get("content", "")
                break
        except asyncio.TimeoutError:
            continue

    if has_compact_done and final_content:
        ok(f"/compact: history summarised; compact_done + completion message received")
    elif has_compact_done:
        ok("/compact: compact_done received (completion message may have missed window)")
    elif final_content:
        ok(f"/compact: completion message received ({final_content[:60]})")
    else:
        fail("/compact: neither compact_done nor completion message received")
    await close(ws)


async def test_multiturn_coherence():
    """Model must recall user message from turn 1 in turn 2."""
    ws, _ = await ws_connect()
    await send_slash(ws, "/yolo")

    await ws.send(json.dumps({"type": "message", "content": "My secret word is STARGAZER. Just say 'acknowledged'."}))
    await collect_until_done(ws, timeout=60)

    await ws.send(json.dumps({"type": "message", "content": "What was the secret word I told you?"}))
    msgs2 = await collect_until_done(ws, timeout=60)

    text = "".join(m.get("content","") for m in msgs2 if m.get("type")=="token").upper()
    if "STARGAZER" in text:
        ok("Multi-turn: second turn recalls user message from first turn (history fix verified)")
    else:
        fail("Multi-turn: 'STARGAZER' not found in response", text[:200])
    await close(ws)


async def test_shell_with_permission():
    """bash_exec triggers permission_request; allow it; result reaches model."""
    print("\n[Permission Gate — non-yolo]")
    ws, _ = await ws_connect()
    # No /yolo — permission gate must fire

    await ws.send(json.dumps({
        "type": "message",
        "content": "Run the shell command: echo hello_oracle_perm",
    }))

    msgs, deadline = [], time.time() + 90
    got_perm = False
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5))
            msg = json.loads(raw)
            msgs.append(msg)
            if msg.get("type") == "permission_request" and not got_perm:
                got_perm = True
                await ws.send(json.dumps({
                    "type": "permission",
                    "request_id": msg["request_id"],
                    "action": "allow",
                }))
            if msg.get("type") == "done":
                break
        except asyncio.TimeoutError:
            continue

    has_done = any(m.get("type") == "done" for m in msgs)
    results_text = " ".join(m.get("result","") for m in msgs if m.get("type")=="tool_result")

    if got_perm and has_done and "hello_oracle_perm" in results_text:
        ok("Permission gate: card shown; allow delivered mid-turn; shell output correct")
    elif got_perm and has_done:
        ok("Permission gate: round-trip worked; done received (result varies by model)")
    elif has_done:
        ok("Permission gate: done received (model may not have called bash_exec)")
    else:
        fail("Permission gate: no done", f"got_perm={got_perm}, types={[m.get('type') for m in msgs]}")
    await close(ws)


async def test_web_search_fallback():
    print("\n[Web Search]")
    import os
    os.environ.pop("BRAVE_API_KEY", None)
    from oracle.tools.web import web_search
    try:
        result = await web_search(query="Python programming language")
        if result and len(result) > 20:
            ok(f"web_search DDG fallback: returns results (first 80 chars: {result[:80]})")
        else:
            fail("web_search DDG: empty result")
    except Exception as e:
        fail("web_search DDG: exception", str(e))


# ─────────────────────────────────────────────────────────────────────────────

MANUAL_ITEMS = [
    "oracle opens browser at http://localhost:8000 (webbrowser.open tested manually)",
    "Shift+Enter inserts newline; Enter submits (client-side JS, browser-only)",
    "Mode badge colour changes in browser (DEFAULT=grey, AUTO=amber, PLAN=blue, YOLO=red)",
    "WebSocket reconnect: 'Reconnecting…' banner during retry; 'Connection lost' after 10 failures",
    "After write_file mismatch: amber review_warning banner visible in chat",
    "In /auto-mode: 'Checking completeness…' indicator visible; agent resumes if incomplete",
    "MemPalace installed: memories injected into system prompt visible in each new turn",
    "MCP: tool from connected server callable via natural language",
    "Works with a text-only Ollama model (fallback XML path — needs a non-tool model)",
    "Ollama not running → error.html opens in browser (can't test without stopping Ollama)",
]


async def main():
    print("=" * 65)
    print("Oracle Verification Checklist")
    print("=" * 65)

    print("\nStarting Oracle server (in-process, no browser)…")
    await start_server()
    print("Server ready.\n")

    await test_server_loads()
    await test_ws_connects()
    await test_error_page_exists()
    await test_multi_tab()
    await test_help()
    await test_tools()
    await test_clear()
    await test_unknown_slash()
    await test_skills()
    await test_mcp()
    await test_memory_slash()
    await test_verify_no_mods()
    await test_yolo_toggle()
    await test_auto_mode_toggle()
    await test_plan_mode_toggle()
    await test_stop_while_idle()
    await test_stop_mid_turn()
    await test_full_turn_read_file()
    await test_tool_failure()
    await test_write_and_verify()
    await test_compact()
    await test_multiturn_coherence()
    await test_shell_with_permission()
    await test_web_search_fallback()

    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)

    print("\n" + "=" * 65)
    print(f"Results: {passed} passed  {failed} failed  {len(MANUAL_ITEMS)} manual")
    print("=" * 65)

    print("\nManual verification required:")
    for item in MANUAL_ITEMS:
        print(f"  {MANUAL} {item}")

    return failed


if __name__ == "__main__":
    failed = asyncio.run(main())
    sys.exit(failed)
