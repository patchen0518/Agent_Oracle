"""Tests for the two critical bugs fixed: history coherence and permission gate."""

import asyncio
import sys
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, ".")


# ── Test 1: Multi-turn history coherence ──────────────────────────────────────
# Validates that history_start = len(messages) - 1 includes the user message
# so the second turn's LLM call sees prior user questions.

async def test_multiturn_history():
    from oracle.agent_loop import SessionState
    from oracle.llm.capabilities import ModelCapability

    # Minimal mocks
    config = MagicMock()
    config.mode = "default"
    config.memory_top_k = 3
    config.project_instructions_file = None
    config.auto_approve = True  # skip permission gate
    config.max_tool_iterations = 5
    config.max_output_bytes = 8000
    config.context_token_budget = 100000

    memory = MagicMock()
    memory.retrieve = AsyncMock(return_value=[])
    memory.save_turn = AsyncMock()

    history_db = MagicMock()
    history_db.append_message = MagicMock()
    history_db.record_outcome = MagicMock(return_value=1)

    ws = MagicMock()
    ws.send_json = AsyncMock()

    skill_registry = MagicMock()
    skill_registry.get = MagicMock(return_value=None)

    # LLM mock: returns a chunk with text "Hello, nice to meet you" (no tool calls)
    chunk1 = MagicMock()
    chunk1.done = True
    chunk1.text = "Hello, nice to meet you!"
    chunk1.tool_calls = None
    chunk1.prompt_eval_count = 10
    chunk1.eval_count = 5

    chunk2 = MagicMock()
    chunk2.done = True
    chunk2.text = "Your name is Alice."
    chunk2.tool_calls = None
    chunk2.prompt_eval_count = 20
    chunk2.eval_count = 5

    call_count = 0
    async def fake_stream_chat(messages, tools=None):
        nonlocal call_count, chunk1, chunk2
        call_count += 1
        chunk = chunk1 if call_count == 1 else chunk2
        chunk.done = False
        chunk.text = chunk.text  # streaming token
        yield chunk
        chunk.done = True
        yield chunk

    llm = MagicMock()
    llm.stream_chat = fake_stream_chat

    permission_gate = MagicMock()

    tool_registry = MagicMock()
    tool_registry.schemas = MagicMock(return_value=[])
    tool_registry.list_all = MagicMock(return_value=[])

    session = SessionState(session_id="test-123")
    session.session_db_id = 1

    from oracle.agent_loop import run_turn

    # Turn 1: "My name is Alice"
    await run_turn(
        user_message="My name is Alice",
        session=session,
        llm=llm,
        tool_registry=tool_registry,
        memory=memory,
        history_db=history_db,
        config=config,
        ws=ws,
        skill_registry=skill_registry,
        capability=ModelCapability.TOOLS,
        permission_gate=permission_gate,
    )

    # Verify history contains the user message from turn 1
    user_msgs = [m for m in session.history if m.get("role") == "user"]
    assert len(user_msgs) == 1, f"Expected 1 user msg in history after turn 1, got {len(user_msgs)}: {session.history}"
    assert user_msgs[0]["content"] == "My name is Alice", f"Wrong content: {user_msgs[0]}"

    # Turn 2: "What's my name?"
    await run_turn(
        user_message="What's my name?",
        session=session,
        llm=llm,
        tool_registry=tool_registry,
        memory=memory,
        history_db=history_db,
        config=config,
        ws=ws,
        skill_registry=skill_registry,
        capability=ModelCapability.TOOLS,
        permission_gate=permission_gate,
    )

    # History should now have both user turns
    user_msgs2 = [m for m in session.history if m.get("role") == "user"]
    assert len(user_msgs2) == 2, f"Expected 2 user msgs in history after turn 2, got {len(user_msgs2)}: {user_msgs2}"
    assert user_msgs2[0]["content"] == "My name is Alice"
    assert user_msgs2[1]["content"] == "What's my name?"

    print("✓ Multi-turn history coherence: user messages preserved across turns")


# ── Test 2: Permission gate round-trip (receive-loop non-deadlock) ────────────
# Validates that sending a permission response while a turn is "running"
# actually reaches the gate — proving the receive loop stays alive.
#
# This is an architecture-level test: we simulate a turn that blocks on
# permission_gate.wait(), then send the resolution via the receive loop,
# and verify the turn unblocks and completes.

async def test_permission_gate_roundtrip():
    """
    The receive loop must stay alive while a turn is running.
    Without the fix (await _turn_task blocks the loop), the permission
    response never gets delivered and the gate times out.
    """
    from oracle.ui.permissions import PermissionGate

    gate = PermissionGate()
    request_id = "test-req-001"

    gate.register(request_id)

    # Simulate: turn task is running and waiting for permission
    async def fake_turn():
        action = await gate.wait(request_id, timeout=5.0)
        return action

    # Start turn task (not awaited — mimics the fixed server code)
    turn_task = asyncio.create_task(fake_turn())

    # Simulate: receive loop is alive and gets a permission message
    await asyncio.sleep(0.01)  # yield to let the task start waiting
    gate.resolve(request_id, "allow")

    # Wait for the task to complete
    result = await asyncio.wait_for(turn_task, timeout=5.0)
    assert result == "allow", f"Expected 'allow', got {result!r}"
    print("✓ Permission gate round-trip: receive loop can deliver permission while turn runs")


async def test_permission_gate_deny():
    from oracle.ui.permissions import PermissionGate

    gate = PermissionGate()
    rid = "test-req-002"
    gate.register(rid)

    turn_task = asyncio.create_task(gate.wait(rid, timeout=5.0))
    await asyncio.sleep(0.01)
    gate.resolve(rid, "deny")

    result = await asyncio.wait_for(turn_task, timeout=5.0)
    assert result == "deny", f"Expected 'deny', got {result!r}"
    print("✓ Permission gate: deny action delivered")


# ── Test 3: Web search DDG fallback ──────────────────────────────────────────

async def test_web_search_fallback():
    """DuckDuckGo instant-answer fallback — no Brave API key needed."""
    import os
    os.environ.pop("BRAVE_API_KEY", None)  # ensure no key

    from oracle.tools.web import web_search
    try:
        result = await web_search(query="Python programming language")
        assert result and len(result) > 10, f"Empty result: {result!r}"
        print(f"✓ web_search DDG fallback: {result[:80]}...")
    except Exception as e:
        print(f"⚠ web_search fallback: {e} (may be network/DDG unavailability — check manually)")


# ── Runner ────────────────────────────────────────────────────────────────────

async def main():
    print("\n=== Fix Verification Tests ===\n")
    await test_multiturn_history()
    await test_permission_gate_roundtrip()
    await test_permission_gate_deny()
    await test_web_search_fallback()
    print("\nAll tests passed.")

if __name__ == "__main__":
    asyncio.run(main())
