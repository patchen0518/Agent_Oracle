"use strict";

const PORT = location.port || 8000;
const SESSION_ID = crypto.randomUUID();
const WS_URL = `ws://${location.hostname}:${PORT}/ws/${SESSION_ID}`;

const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const stopBtn = document.getElementById("stop-btn");
const modeBadge = document.getElementById("mode-badge");
const ctxText = document.getElementById("ctx-text");
const ctxFill = document.getElementById("ctx-fill");
const reconnectBanner = document.getElementById("reconnect-banner");
const reconnectCount = document.getElementById("reconnect-count");
const lostBanner = document.getElementById("lost-banner");

let ws = null;
let retries = 0;
const MAX_RETRIES = 10;
let generating = false;
let currentAssistantBubble = null;
let currentAssistantText = "";

// ── WebSocket connection ──────────────────────────────────────────────────────

function connect() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    retries = 0;
    reconnectBanner.classList.add("hidden");
    lostBanner.classList.add("hidden");
  };

  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    handleMessage(msg);
  };

  ws.onclose = () => {
    if (!generating) scheduleReconnect();
  };

  ws.onerror = () => {
    ws.close();
  };
}

function scheduleReconnect() {
  if (retries >= MAX_RETRIES) {
    lostBanner.classList.remove("hidden");
    return;
  }
  retries++;
  reconnectBanner.classList.remove("hidden");
  reconnectCount.textContent = `(${retries}/${MAX_RETRIES})`;
  setTimeout(connect, 2000);
}

// ── Message dispatch ──────────────────────────────────────────────────────────

function handleMessage(msg) {
  switch (msg.type) {
    case "token":
      appendToken(msg.content);
      break;
    case "done":
      finalizeAssistant();
      setGenerating(false);
      break;
    case "tool_start":
      appendToolStart(msg.name, msg.args);
      break;
    case "tool_result":
      appendToolResult(msg.name, msg.result, msg.truncated);
      break;
    case "permission_request":
      appendPermissionCard(msg.request_id, msg.tool, msg.args);
      break;
    case "plan":
      appendPlanCard(msg.steps);
      break;
    case "system_message":
      appendSystemBubble(msg.content);
      break;
    case "mode":
      updateModeBadge(msg.mode);
      break;
    case "context":
      updateContextBar(msg.used, msg.budget);
      break;
    case "review_warning":
      appendReviewWarning(msg.message);
      break;
    case "completion_check":
      appendCompletionStatus(msg.status);
      break;
    case "compact_done":
      break;
    case "error":
      // If this is the first message, it's the multi-tab rejection
      appendSystemBubble(`⚠ ${msg.message}`);
      break;
    case "proposal_batch":
      appendProposalBatch(msg.proposals || []);
      break;
    case "quit_ack":
      window.close();
      break;
  }
}

// ── Token streaming ───────────────────────────────────────────────────────────

function appendToken(text) {
  if (!currentAssistantBubble) {
    currentAssistantBubble = document.createElement("div");
    currentAssistantBubble.className = "bubble bubble-assistant";
    chat.appendChild(currentAssistantBubble);
  }
  currentAssistantText += text;
  currentAssistantBubble.textContent = currentAssistantText;
  scrollBottom();
}

function finalizeAssistant() {
  currentAssistantBubble = null;
  currentAssistantText = "";
}

// ── Tool panels ───────────────────────────────────────────────────────────────

let _lastToolPanel = null;

function appendToolStart(name, args) {
  const wrap = document.createElement("div");
  wrap.className = "tool-panel";
  wrap.dataset.toolName = name;

  const details = document.createElement("details");
  details.open = true;

  const summary = document.createElement("summary");
  summary.textContent = ` ${name}`;

  const argsDiv = document.createElement("div");
  argsDiv.className = "tool-args";
  argsDiv.textContent = JSON.stringify(args, null, 2);

  details.appendChild(summary);
  details.appendChild(argsDiv);
  wrap.appendChild(details);
  chat.appendChild(wrap);
  _lastToolPanel = { wrap, details };
  scrollBottom();
}

function appendToolResult(name, result, truncated) {
  if (!_lastToolPanel) return;
  const { details } = _lastToolPanel;

  const resultDiv = document.createElement("div");
  resultDiv.className = "tool-result";
  resultDiv.textContent = result + (truncated ? "\n[...truncated]" : "");
  details.appendChild(resultDiv);

  // Collapse after result is shown
  setTimeout(() => { details.open = false; }, 2000);
  _lastToolPanel = null;
  scrollBottom();
}

// ── Permission card ───────────────────────────────────────────────────────────

function appendPermissionCard(requestId, tool, args) {
  const card = document.createElement("div");
  card.className = "permission-card";

  const title = document.createElement("div");
  title.className = "permission-title";
  title.textContent = `Permission required: ${tool}`;

  const detail = document.createElement("div");
  detail.className = "permission-detail";
  detail.textContent = JSON.stringify(args, null, 2);

  const buttons = document.createElement("div");
  buttons.className = "permission-buttons";

  function resolve(action) {
    ws.send(JSON.stringify({ type: "permission", request_id: requestId, action }));
    card.style.opacity = "0.4";
    buttons.querySelectorAll("button").forEach(b => b.disabled = true);
  }

  const allow = document.createElement("button");
  allow.className = "btn-allow";
  allow.textContent = "Allow";
  allow.onclick = () => resolve("allow");

  const deny = document.createElement("button");
  deny.className = "btn-deny";
  deny.textContent = "Deny";
  deny.onclick = () => resolve("deny");

  const always = document.createElement("button");
  always.className = "btn-always";
  always.textContent = "Always allow";
  always.onclick = () => resolve("always");

  buttons.appendChild(allow);
  buttons.appendChild(deny);
  buttons.appendChild(always);

  card.appendChild(title);
  card.appendChild(detail);
  card.appendChild(buttons);
  chat.appendChild(card);
  scrollBottom();
}

// ── Plan card ─────────────────────────────────────────────────────────────────

function appendPlanCard(steps) {
  const card = document.createElement("div");
  card.className = "plan-card";

  const title = document.createElement("div");
  title.className = "plan-title";
  title.textContent = "📋 Execution Plan";

  const list = document.createElement("ol");
  list.className = "plan-steps";
  steps.forEach(step => {
    const li = document.createElement("li");
    li.textContent = step.replace(/^step\s*\d+:\s*/i, "");
    list.appendChild(li);
  });

  const buttons = document.createElement("div");
  buttons.className = "plan-buttons";

  function send(type) {
    ws.send(JSON.stringify({ type }));
    buttons.querySelectorAll("button").forEach(b => b.disabled = true);
    card.style.opacity = "0.4";
  }

  const proceed = document.createElement("button");
  proceed.className = "btn-proceed";
  proceed.textContent = "Proceed";
  proceed.onclick = () => send("plan_approve");

  const abort = document.createElement("button");
  abort.className = "btn-abort";
  abort.textContent = "Abort";
  abort.onclick = () => send("plan_reject");

  buttons.appendChild(proceed);
  buttons.appendChild(abort);

  card.appendChild(title);
  card.appendChild(list);
  card.appendChild(buttons);
  chat.appendChild(card);
  scrollBottom();
}

// ── System bubble ─────────────────────────────────────────────────────────────

function appendSystemBubble(content) {
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble-system";
  bubble.textContent = content;
  chat.appendChild(bubble);
  scrollBottom();
}

// ── Review warning ────────────────────────────────────────────────────────────

function appendReviewWarning(message) {
  const el = document.createElement("div");
  el.className = "review-warning";
  el.textContent = `⚠ ${message}`;
  chat.appendChild(el);
  scrollBottom();
}

// ── Completion status ─────────────────────────────────────────────────────────

function appendCompletionStatus(status) {
  const el = document.createElement("div");
  el.className = "completion-status";
  const labels = {
    checking: "Checking completeness…",
    resuming: "⚠ Task incomplete — continuing…",
    complete: "✓ Complete",
  };
  el.textContent = labels[status] || status;
  chat.appendChild(el);
  scrollBottom();
  if (status === "complete") {
    setTimeout(() => el.classList.add("fade"), 500);
  }
}

// ── Proposal cards (Phase 11) ─────────────────────────────────────────────────

function appendProposalBatch(proposals) {
  const card = document.createElement("div");
  card.className = "proposal-card";

  const title = document.createElement("div");
  title.style.cssText = "font-weight:700;color:var(--accent-light);margin-bottom:10px";
  title.textContent = `🔮 Self-improvement proposals (${proposals.length})`;
  card.appendChild(title);

  proposals.forEach((p, idx) => {
    const item = document.createElement("div");
    item.className = "proposal-item";

    const badge = document.createElement("span");
    badge.className = "proposal-action-badge";
    badge.textContent = p.action;

    const path = document.createElement("span");
    path.style.fontWeight = "600";
    path.textContent = p.target_path;

    const rationale = document.createElement("div");
    rationale.style.cssText = "font-size:12px;color:var(--text-dim);margin:6px 0";
    rationale.textContent = p.rationale;

    const btns = document.createElement("div");
    btns.style.display = "flex";
    btns.style.gap = "8px";

    function decide(action) {
      ws.send(JSON.stringify({ type: "proposal_decision", index: idx, action }));
      btns.querySelectorAll("button").forEach(b => b.disabled = true);
      item.style.opacity = "0.4";
    }

    const approve = document.createElement("button");
    approve.className = "btn-allow";
    approve.textContent = "Approve";
    approve.onclick = () => decide("approve");

    const skip = document.createElement("button");
    skip.className = "btn-deny";
    skip.textContent = "Skip";
    skip.onclick = () => decide("reject");

    btns.appendChild(approve);
    btns.appendChild(skip);
    item.appendChild(badge);
    item.appendChild(path);
    item.appendChild(rationale);
    item.appendChild(btns);
    card.appendChild(item);
  });

  chat.appendChild(card);
  scrollBottom();
}

// ── Mode badge ────────────────────────────────────────────────────────────────

function updateModeBadge(mode) {
  modeBadge.textContent = mode.toUpperCase();
  modeBadge.className = `badge badge-${mode}`;
}

// ── Context bar ───────────────────────────────────────────────────────────────

function updateContextBar(used, budget) {
  const pct = budget > 0 ? (used / budget) * 100 : 0;
  const usedK = (used / 1000).toFixed(1);
  const budgetK = (budget / 1000).toFixed(0);
  ctxText.textContent = `ctx: ${usedK}k / ${budgetK}k`;
  ctxFill.style.width = `${Math.min(pct, 100)}%`;
  ctxFill.className = pct >= 95 ? "red" : pct >= 85 ? "amber" : "";
}

// ── Sending ───────────────────────────────────────────────────────────────────

function sendMessage() {
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

  // Append user bubble
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble-user";
  bubble.textContent = text;
  chat.appendChild(bubble);
  scrollBottom();

  if (text.startsWith("/")) {
    ws.send(JSON.stringify({ type: "slash", command: text }));
  } else {
    ws.send(JSON.stringify({ type: "message", content: text }));
    setGenerating(true);
  }

  input.value = "";
  input.style.height = "auto";
}

function setGenerating(value) {
  generating = value;
  sendBtn.disabled = value;
  input.disabled = value;
  stopBtn.disabled = !value;
}

// ── Events ────────────────────────────────────────────────────────────────────

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!generating) sendMessage();
  }
  // Auto-resize textarea
  setTimeout(() => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 200) + "px";
  }, 0);
});

sendBtn.addEventListener("click", () => {
  if (!generating) sendMessage();
});

stopBtn.addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "stop" }));
  }
  setGenerating(false);
});

// ── Utilities ─────────────────────────────────────────────────────────────────

function scrollBottom() {
  chat.scrollTop = chat.scrollHeight;
}

// ── Start ─────────────────────────────────────────────────────────────────────

connect();
