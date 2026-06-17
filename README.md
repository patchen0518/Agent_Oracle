# Oracle

A local AI agent that runs in your browser, powered by [Ollama](https://ollama.com). Streams responses token-by-token, calls tools with your permission, and remembers context across sessions.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/download) running locally
- A tool-calling model: `ollama pull gemma4:12b` (recommended)

## Install

```bash
git clone <repo>
cd local-llm
uv sync
```

To enable semantic memory (optional):

```bash
uv sync --extra memory
```

## Run

```bash
uv run oracle
```

Oracle serves from the **current working directory** — run it from any project folder and it will read that project's `ORACLE.md` and `.oracle.toml` automatically.

### Global install

Install Oracle as a uv tool so `oracle` is available from any directory:

```bash
uv tool install /path/to/local-llm

# With semantic memory:
uv tool install /path/to/local-llm[memory]
```

To update after pulling changes:

```bash
uv tool install --reinstall /path/to/local-llm
```

To remove:

```bash
uv tool uninstall oracle
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--model`, `-m` | `gemma4:12b` | Ollama model tag |
| `--port`, `-p` | `8000` | Server port |
| `--host` | `http://localhost:11434` | Ollama host URL |
| `--yolo` | off | Auto-approve all tool actions on startup |
| `--no-stream` | off | Disable token streaming (debug) |

```bash
oracle --model llama3.2:3b --port 8080
```

## File Mentions

Type `@` in your message to reference a file from the current project:

```
Review @src/auth.py for security issues
```

Oracle reads the file and injects its contents into the context — the agent sees the full file without needing to call `read_file` first. Only files within the current working directory are accessible.

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/clear` | Wipe in-memory conversation history |
| `/history` | Show the last 20 messages from this session |
| `/compact` | Summarize history into one context block (frees context) |
| `/model [name]` | List installed models, or switch to a model by name |
| `/mode <name>` | Set mode: `default`, `auto`, `plan`, or `yolo` |
| `/tools` | List all registered tools |
| `/yolo` | Toggle auto-approve for all tool actions |
| `/auto-mode` | Toggle autonomous tool loop (runs to completion without pausing) |
| `/plan-mode` | Toggle plan-before-act mode (shows plan for approval first) |
| `/memory <query>` | Search semantic memory for relevant past context |
| `/verify` | Ask Oracle to review its own modified files for correctness |
| `/skills` | List available skills |
| `/<skill-name>` | Activate a skill for the next turn |
| `/mcp` | Show MCP server connection status |
| `/quit` | Stop the server |

## Agent Modes

| Mode | Behavior |
|------|----------|
| Default | One tool loop per turn; approval required for write/exec tools |
| Auto | Tool loop runs to completion; auto-checks if task is done |
| Plan | Generates a numbered plan for your approval before any tools run |
| YOLO | All tool permissions auto-approved |

Switch modes with `/mode <name>` or `--yolo` at startup.

## Tools

Read-only tools run automatically. Write and exec tools require your approval before running.

| Tool | Permission | Description |
|------|-----------|-------------|
| `read_file` | Auto | Read file contents, optionally within a line range |
| `write_file` | Required | Write full content to a file |
| `edit_file` | Required | Replace an exact string within a file |
| `list_dir` | Auto | List directory contents |
| `grep` | Auto | Search file contents with regex |
| `glob` | Auto | Find files matching a pattern |
| `bash_exec` | Required | Run a shell command with timeout |
| `web_fetch` | Required | Fetch and strip a URL to plain text |
| `web_search` | Required | Search the web (Brave API or DuckDuckGo fallback) |

> **File sandbox:** `read_file`, `write_file`, `edit_file`, `list_dir`, `grep`, and `glob` are restricted to the current working directory. `bash_exec` can reach anywhere on the filesystem but always requires explicit permission.

Each tool is capped at 3 failures per turn.

## Skills

Skills inject a persona or set of instructions into one turn's system prompt. Create `.md` files with YAML frontmatter:

```
~/.oracle/skills/reviewer.md       # global (always available)
.oracle/skills/reviewer.md         # project-local (overrides global on name collision)
```

**Format:**

```markdown
---
name: reviewer
description: Strict code reviewer focused on correctness and security
---

You are a rigorous code reviewer. For every change, check:
1. Correctness — does it do what it claims?
2. Edge cases — what inputs break it?
3. Security — any injections, path traversals, or information leaks?

Be blunt. Approve only when all three pass.
```

Activate with `/reviewer` before sending your message.

## Project Instructions (`ORACLE.md`)

Place an `ORACLE.md` file in your project root to inject standing instructions into every turn's system prompt:

```markdown
# Project: my-app

Stack: FastAPI + React + PostgreSQL
Python version: 3.12
Test runner: pytest (always run tests after edits)

Never modify migrations directly — describe the change and ask me first.
```

## Configuration

Oracle reads config from (later sources override earlier ones):

1. Built-in defaults
2. `~/.oracle/config.toml` (global)
3. `.oracle.toml` (project-local)
4. Environment variables
5. CLI flags

**`~/.oracle/config.toml` example:**

```toml
model = "gemma4:12b"
port = 8000
ollama_host = "http://localhost:11434"
memory_top_k = 5
context_token_budget = 100000
max_tool_iterations = 20
max_output_bytes = 16384

[brave]
api_key = "BSA..."   # or set BRAVE_API_KEY env var

[[mcp_servers]]
name = "filesystem"
url = "http://localhost:3001"
```

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `ORACLE_MODEL` | Model tag |
| `ORACLE_HOST` | Ollama host URL |
| `ORACLE_YOLO` | Set to `1` to enable YOLO mode |
| `BRAVE_API_KEY` | Brave Search API key (web_search falls back to DuckDuckGo without it) |

## MCP Servers

Oracle connects to [Model Context Protocol](https://modelcontextprotocol.io) servers at startup. Configure them in `~/.oracle/config.toml`:

```toml
[[mcp_servers]]
name = "filesystem"
url = "http://localhost:3001"

[[mcp_servers]]
name = "github"
url = "http://localhost:3002"
```

MCP tools appear in the registry as `mcp:{server}/{tool_name}`. A server that fails to connect at startup is skipped — Oracle launches normally and `/mcp` shows the error reason.

## Semantic Memory

When the `memory` extra is installed, Oracle stores each conversation turn in a local [ChromaDB](https://www.trychroma.com) vector database and retrieves relevant past context at the start of every new turn.

Without it, Oracle starts in no-memory mode.

Memories are stored at `~/.oracle/palace/`. Use `/memory <query>` to search them directly.

## Session Storage

Every session is recorded in `~/.oracle/history.db` (SQLite). Oracle never loads past sessions on startup — each browser open is a fresh conversation.

## Text-Only Models

Models without native tool support use a `<tool_call>{json}</tool_call>` XML fallback, detected automatically at startup. All tools work; performance may be lower.

## Multi-Tab Protection

Only one Oracle tab can be active at a time.
