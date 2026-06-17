"use strict";

const PORT = location.port || 8000;
const SESSION_ID = crypto.randomUUID();
const WS_URL = `ws://${location.hostname}:${PORT}/ws/${SESSION_ID}`;

const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const stopBtn = document.getElementById("stop-btn");
const logo = document.getElementById("logo");
const modeBadge = document.getElementById("mode-badge");
const ctxText = document.getElementById("ctx-text");
const ctxFill = document.getElementById("ctx-fill");
const reconnectBanner = document.getElementById("reconnect-banner");
const reconnectCount = document.getElementById("reconnect-count");
const lostBanner = document.getElementById("lost-banner");
const cwdDisplay = document.getElementById("cwd-display");
const modelDisplay = document.getElementById("model-display");
const slashPicker = document.getElementById("slash-picker");

const SLASH_COMMANDS = [
  { cmd: "/help",      desc: "Show all commands and shortcuts" },
  { cmd: "/clear",     desc: "Wipe conversation history" },
  { cmd: "/history",   desc: "Show last 20 messages from this session" },
  { cmd: "/compact",   desc: "Summarize history to free context" },
  { cmd: "/model",     desc: "List or switch Ollama model" },
  { cmd: "/tools",     desc: "List all available tools" },
  { cmd: "/yolo",      desc: "Toggle auto-approve all actions" },
  { cmd: "/auto-mode", desc: "Toggle autonomous tool loop" },
  { cmd: "/plan-mode", desc: "Toggle plan-before-act mode" },
  { cmd: "/memory",    desc: "Search MemPalace memories" },
  { cmd: "/verify",    desc: "Review modified files for correctness" },
  { cmd: "/skills",    desc: "List available skills" },
  { cmd: "/mcp",       desc: "Show MCP server status" },
  { cmd: "/quit",      desc: "Stop Oracle and close the tab" },
];

let ws = null;
let retries = 0;
const MAX_RETRIES = 10;
let generating = false;
let currentMode = "default";
const MODE_CYCLE = ["default", "auto", "plan", "yolo"];

// Picker shared state
let pickerMode = "none";   // "slash" | "at" | "none"
let pickerIndex = -1;
let atMentionRange = null; // { start, end } positions in textarea
let atDebounce = null;
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
    case "cwd":
      cwdDisplay.textContent = msg.path;
      cwdDisplay.title = `Working directory: ${msg.path}`;
      break;
    case "model_info":
      modelDisplay.textContent = msg.model;
      modelDisplay.title = `Model: ${msg.model}`;
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
  if (currentAssistantBubble) {
    currentAssistantBubble.innerHTML = renderMarkdown(currentAssistantText);
    scrollBottom();
  }
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

  // Collapse and mark done after result is shown
  setTimeout(() => { details.open = false; details.classList.add("done"); }, 2000);
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
  currentMode = mode;
  modeBadge.textContent = mode.toUpperCase();
  modeBadge.className = `badge badge-${mode}`;
}

function cycleMode() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const next = MODE_CYCLE[(MODE_CYCLE.indexOf(currentMode) + 1) % MODE_CYCLE.length];
  ws.send(JSON.stringify({ type: "slash", command: `/mode ${next}` }));
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
  hidePicker();
}

function setGenerating(value) {
  generating = value;
  sendBtn.disabled = value;
  input.disabled = value;
  stopBtn.disabled = !value;
  logo.classList.toggle("active", value);
}

// ── Command / file picker ─────────────────────────────────────────────────────

function hidePicker() {
  slashPicker.classList.add("hidden");
  slashPicker.innerHTML = "";
  pickerIndex = -1;
  pickerMode = "none";
  atMentionRange = null;
}

function setPickerIndex(idx) {
  const items = slashPicker.querySelectorAll(".slash-item");
  items.forEach(el => el.classList.remove("active"));
  if (idx >= 0 && idx < items.length) {
    items[idx].classList.add("active");
    items[idx].scrollIntoView({ block: "nearest" });
  }
  pickerIndex = idx;
}

// ── Slash picker ──────────────────────────────────────────────────────────────

function updateSlashPicker() {
  const val = input.value;
  if (!val.startsWith("/")) { hidePicker(); return; }

  const query = val.slice(1).toLowerCase();
  const matches = SLASH_COMMANDS.filter(c => c.cmd.slice(1).startsWith(query));
  if (!matches.length) { hidePicker(); return; }

  slashPicker.innerHTML = "";
  pickerIndex = -1;
  pickerMode = "slash";

  matches.forEach((item) => {
    const row = document.createElement("div");
    row.className = "slash-item";

    const cmd = document.createElement("span");
    cmd.className = "slash-item-cmd";
    cmd.textContent = item.cmd;

    const desc = document.createElement("span");
    desc.className = "slash-item-desc";
    desc.textContent = item.desc;

    row.appendChild(cmd);
    row.appendChild(desc);
    row.addEventListener("mousedown", (e) => {
      e.preventDefault();
      selectSlashItem(item.cmd);
    });
    slashPicker.appendChild(row);
  });

  slashPicker.classList.remove("hidden");
}

function selectSlashItem(cmd) {
  input.value = cmd + " ";
  hidePicker();
  input.focus();
}

// ── @ file picker ─────────────────────────────────────────────────────────────

function getAtQuery() {
  const pos = input.selectionStart;
  const before = input.value.slice(0, pos);
  const match = before.match(/@(\S*)$/);
  if (!match) return null;
  return { query: match[1], start: pos - match[0].length, end: pos };
}

function updateAtPicker() {
  const info = getAtQuery();
  if (!info) { hidePicker(); return; }

  clearTimeout(atDebounce);
  atDebounce = setTimeout(async () => {
    try {
      const resp = await fetch(`/api/files?q=${encodeURIComponent(info.query)}`);
      const data = await resp.json();
      if (!data.files || !data.files.length) { hidePicker(); return; }
      showAtResults(data.files, info);
    } catch (_) {
      hidePicker();
    }
  }, 150);
}

function showAtResults(files, info) {
  atMentionRange = info;
  slashPicker.innerHTML = "";
  pickerIndex = -1;
  pickerMode = "at";

  files.forEach((file) => {
    const row = document.createElement("div");
    row.className = "slash-item";

    const parts = file.split("/");
    const name = document.createElement("span");
    name.className = "slash-item-cmd";
    name.textContent = parts[parts.length - 1];

    const path = document.createElement("span");
    path.className = "slash-item-desc";
    path.textContent = file;

    row.appendChild(name);
    row.appendChild(path);
    row.addEventListener("mousedown", (e) => {
      e.preventDefault();
      selectAtItem(file);
    });
    slashPicker.appendChild(row);
  });

  slashPicker.classList.remove("hidden");
}

function selectAtItem(file) {
  if (!atMentionRange) return;
  const { start, end } = atMentionRange;
  const val = input.value;
  input.value = val.slice(0, start) + "@" + file + val.slice(end);
  const newPos = start + 1 + file.length;
  input.setSelectionRange(newPos, newPos);
  hidePicker();
  input.focus();
}

function updatePicker() {
  const val = input.value;
  const pos = input.selectionStart;
  const before = val.slice(0, pos);

  if (before.match(/@(\S*)$/)) {
    updateAtPicker();
  } else if (val.startsWith("/")) {
    updateSlashPicker();
  } else {
    hidePicker();
  }
}

// ── Events ────────────────────────────────────────────────────────────────────

input.addEventListener("input", () => { updatePicker(); });

input.addEventListener("keydown", (e) => {
  // Shift+Tab cycles through modes
  if (e.key === "Tab" && e.shiftKey) {
    e.preventDefault();
    cycleMode();
    return;
  }

  // Picker navigation
  if (!slashPicker.classList.contains("hidden")) {
    const items = slashPicker.querySelectorAll(".slash-item");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setPickerIndex(Math.min(pickerIndex + 1, items.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setPickerIndex(Math.max(pickerIndex - 1, 0));
      return;
    }
    if (e.key === "Escape") {
      hidePicker();
      return;
    }
    if (e.key === "Enter" || e.key === "Tab") {
      if (pickerIndex >= 0) {
        e.preventDefault();
        const items = slashPicker.querySelectorAll(".slash-item");
        const active = items[pickerIndex];
        if (active) {
          if (pickerMode === "slash") {
            const cmd = active.querySelector(".slash-item-cmd").textContent;
            selectSlashItem(cmd);
          } else if (pickerMode === "at") {
            const file = active.querySelector(".slash-item-desc").textContent;
            selectAtItem(file);
          }
        }
        return;
      }
    }
  }

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

// ── Settings panel ────────────────────────────────────────────────────────────

const settingsOverlay = document.getElementById("settings-overlay");
const oracleMdOverlay = document.getElementById("oracle-md-overlay");

document.getElementById("settings-btn").addEventListener("click", openSettings);
document.getElementById("settings-close").addEventListener("click", closeSettings);
document.getElementById("settings-cancel").addEventListener("click", closeSettings);
document.getElementById("settings-save").addEventListener("click", saveSettings);

settingsOverlay.addEventListener("click", (e) => {
  if (e.target === settingsOverlay) closeSettings();
});

async function openSettings() {
  try {
    const resp = await fetch("/api/config");
    const cfg = await resp.json();
    document.getElementById("cfg-model").value = cfg.model || "";
    document.getElementById("cfg-max-iter").value = cfg.max_tool_iterations ?? 20;
    document.getElementById("cfg-ctx-budget").value = cfg.context_token_budget ?? 100000;
    document.getElementById("cfg-max-output").value = cfg.max_output_bytes ?? 16384;
    document.getElementById("cfg-memory-k").value = cfg.memory_top_k ?? 5;
    document.getElementById("cfg-brave-key").value = cfg.brave_api_key || "";
    document.getElementById("cfg-ollama-host").value = cfg.ollama_host || "";
    document.getElementById("cfg-port").value = cfg.port || 8000;
    settingsOverlay.classList.remove("hidden");
  } catch (e) {
    appendSystemBubble(`⚠ Could not load settings: ${e.message}`);
  }
}

function closeSettings() {
  settingsOverlay.classList.add("hidden");
}

async function saveSettings() {
  const scope = document.querySelector('input[name="cfg-scope"]:checked').value;
  const values = {
    model: document.getElementById("cfg-model").value.trim(),
    max_tool_iterations: parseInt(document.getElementById("cfg-max-iter").value, 10),
    context_token_budget: parseInt(document.getElementById("cfg-ctx-budget").value, 10),
    max_output_bytes: parseInt(document.getElementById("cfg-max-output").value, 10),
    memory_top_k: parseInt(document.getElementById("cfg-memory-k").value, 10),
    brave_api_key: document.getElementById("cfg-brave-key").value.trim(),
    ollama_host: document.getElementById("cfg-ollama-host").value.trim(),
    port: parseInt(document.getElementById("cfg-port").value, 10),
  };

  const saveBtn = document.getElementById("settings-save");
  saveBtn.disabled = true;
  saveBtn.textContent = "Saving…";

  try {
    const resp = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, values }),
    });
    const result = await resp.json();
    if (result.ok) {
      closeSettings();
      appendSystemBubble(`✓ Settings saved to ${result.path}`);
    } else {
      appendSystemBubble(`⚠ Save failed: ${result.error}`);
    }
  } catch (e) {
    appendSystemBubble(`⚠ Save failed: ${e.message}`);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save";
  }
}

// ── ORACLE.md editor ──────────────────────────────────────────────────────────

let oracleScope = "local";

document.getElementById("oracle-md-btn").addEventListener("click", openOracleEditor);
document.getElementById("oracle-md-close").addEventListener("click", closeOracleEditor);
document.getElementById("oracle-md-cancel").addEventListener("click", closeOracleEditor);
document.getElementById("oracle-md-save").addEventListener("click", saveOracleEditor);
document.getElementById("oracle-tab-local").addEventListener("click", () => switchOracleTab("local"));
document.getElementById("oracle-tab-global").addEventListener("click", () => switchOracleTab("global"));

oracleMdOverlay.addEventListener("click", (e) => {
  if (e.target === oracleMdOverlay) closeOracleEditor();
});

async function openOracleEditor() {
  oracleScope = "local";
  updateOracleTabs();
  await loadOracleContent();
  oracleMdOverlay.classList.remove("hidden");
  document.getElementById("oracle-textarea").focus();
}

function closeOracleEditor() {
  oracleMdOverlay.classList.add("hidden");
}

async function switchOracleTab(scope) {
  oracleScope = scope;
  updateOracleTabs();
  await loadOracleContent();
}

function updateOracleTabs() {
  document.getElementById("oracle-tab-local").className = "modal-tab" + (oracleScope === "local" ? " active" : "");
  document.getElementById("oracle-tab-global").className = "modal-tab" + (oracleScope === "global" ? " active" : "");
}

async function loadOracleContent() {
  try {
    const resp = await fetch(`/api/oracle-md?scope=${oracleScope}`);
    const data = await resp.json();
    document.getElementById("oracle-textarea").value = data.content || "";
    document.getElementById("oracle-path-hint").textContent = data.path || "";
  } catch (e) {
    document.getElementById("oracle-textarea").value = "";
    document.getElementById("oracle-path-hint").textContent = "";
  }
}

async function saveOracleEditor() {
  const content = document.getElementById("oracle-textarea").value;
  const saveBtn = document.getElementById("oracle-md-save");
  saveBtn.disabled = true;
  saveBtn.textContent = "Saving…";

  try {
    const resp = await fetch("/api/oracle-md", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: oracleScope, content }),
    });
    const result = await resp.json();
    if (result.ok) {
      closeOracleEditor();
      appendSystemBubble(`✓ ORACLE.md saved to ${result.path}`);
    } else {
      appendSystemBubble(`⚠ Save failed: ${result.error}`);
    }
  } catch (e) {
    appendSystemBubble(`⚠ Save failed: ${e.message}`);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save";
  }
}

// ── Markdown renderer ─────────────────────────────────────────────────────────

function renderMarkdown(md) {
  function esc(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function inline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
      .replace(/~~(.+?)~~/g, '<del>$1</del>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) =>
        /^https?:\/\//i.test(url) ? `<a href="${url}">${text}</a>` : text);
  }

  const lines = md.split('\n');
  let html = '';
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.startsWith('```')) {
      i++;
      const codeLines = []; while (i < lines.length && !lines[i].startsWith('```')) codeLines.push(lines[i++]);
      html += `<pre><code>${esc(codeLines.join('\n'))}</code></pre>`;
      i++; continue;
    }

    // Heading
    const hm = line.match(/^(#{1,6}) (.+)/);
    if (hm) { html += `<h${hm[1].length}>${inline(hm[2])}</h${hm[1].length}>`; i++; continue; }

    // Horizontal rule
    if (/^[-*_]{3,}\s*$/.test(line)) { html += '<hr>'; i++; continue; }

    // Blockquote
    if (line.startsWith('> ')) {
      const bq = []; while (i < lines.length && lines[i].startsWith('> ')) bq.push(lines[i++].slice(2));
      html += `<blockquote><p>${inline(bq.join(' '))}</p></blockquote>`;
      continue;
    }

    // Unordered list
    if (/^[-*+] /.test(line)) {
      html += '<ul>';
      while (i < lines.length && /^[-*+] /.test(lines[i]))
        html += `<li>${inline(lines[i++].replace(/^[-*+] /, ''))}</li>`;
      html += '</ul>'; continue;
    }

    // Ordered list
    if (/^\d+\. /.test(line)) {
      html += '<ol>';
      while (i < lines.length && /^\d+\. /.test(lines[i]))
        html += `<li>${inline(lines[i++].replace(/^\d+\. /, ''))}</li>`;
      html += '</ol>'; continue;
    }

    // Empty line
    if (!line.trim()) { i++; continue; }

    // Paragraph — collect consecutive plain lines, preserving line breaks
    const paraLines = [];
    while (i < lines.length && lines[i].trim() &&
        !lines[i].startsWith('#') && !lines[i].startsWith('```') &&
        !lines[i].startsWith('> ') && !/^[-*+] /.test(lines[i]) &&
        !/^\d+\. /.test(lines[i]) && !/^[-*_]{3,}\s*$/.test(lines[i])) {
      paraLines.push(lines[i++]);
    }
    if (paraLines.length) html += `<p>${paraLines.map(inline).join('<br>')}</p>`;
  }

  return html;
}

// ── Start ─────────────────────────────────────────────────────────────────────

connect();
