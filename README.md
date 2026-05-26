# Praxis

A governed agentic OS kernel. Not a coding assistant — an orchestrator that perceives, plans, acts, verifies, and remembers on your behalf, with a security boundary that cannot be bypassed.

Praxis turns a Claude (or any OpenAI-compatible) model into a disciplined system that runs inside a sandbox it cannot escape. Every tool call passes through an escalation boundary hook. Writes outside the workspace are blocked. Network egress is blocked. The model must escalate to you — the human — for anything beyond its permitted scope.

## Why Praxis

**Security-first.** The `§5 escalation boundary` is not a suggestion — it's a PreToolUse hook that inspects every tool call before execution. The model cannot write outside the workspace, cannot modify its own control plane, and cannot reach the network without explicit domain allowlisting. When it tries, the hook blocks the call and the model escalates to you instead of proceeding.

**Model-agnostic.** Three runtime backends — Anthropic Claude API (subscription or pay-per-token), any local model via Ollama/vLLM/llama.cpp, or any cloud API that speaks the OpenAI protocol (OpenAI, Gemini, OpenRouter, Groq). Switch with one environment variable. Route different subagents to different providers with `convergence.yaml`.

**Flat subscription cost.** When using `CLAUDE_CODE_OAUTH_TOKEN`, you run on your Claude subscription — no per-token billing surprises.

## The Security Gate in Action

```
$ python -m praxis "Write a config file to /etc/myapp/config.yaml"

[praxis] Planning...
[praxis] Calling tool: Write { file_path: "/etc/myapp/config.yaml", ... }

BLOCKED by §5 escalation boundary: Write would write outside
WORKSPACE_ROOT (/home/user/project): /etc/myapp/config.yaml
Escalate to the human per §5 — do not retry without approval.

[praxis] The write was blocked by the security boundary.
         /etc/myapp/config.yaml is outside the workspace.
         I'll save it inside the project instead — does
         config/myapp.yaml work for you?
```

The hook didn't just warn — it exited with code 2, which killed the tool call. The model received the block message and changed its approach instead of retrying. This is the core contract: **the model adapts to its boundaries rather than working around them.**

## Quick Start

```bash
git clone https://github.com/Ashtonantony28/Praxis_AgenticOSKernel.git
cd Praxis_AgenticOSKernel
bash install.sh
```

The installer checks Python 3.10+, creates a virtual environment, installs the package, and prints a setup checklist.

Then edit `.env` with your auth credentials and run:

```bash
source .venv/bin/activate
export PRAXIS_WORKSPACE_ROOT=$(pwd)
export PRAXIS_MEMORY_ROOT=$PRAXIS_WORKSPACE_ROOT/.praxis/memory
python -m praxis "hello, what can you do?"
```

### Use a local model instead

```bash
pip install praxis[local]
export PRAXIS_RUNTIME=local
export PRAXIS_LOCAL_BASE_URL=http://localhost:11434   # Ollama
export PRAXIS_LOCAL_MODEL=llama3.1:8b
python -m praxis "hello"
```

### Use a cloud provider

```bash
pip install praxis[cloud]
export PRAXIS_RUNTIME=cloud
export PRAXIS_CLOUD_API_KEY=sk-...
export PRAXIS_CLOUD_MODEL=gpt-4o
python -m praxis "hello"
```

## Architecture

```
                    ┌─────────────────────────┐
                    │     Human Operator       │
                    └────────────┬─────────────┘
                                 │ prompt / approval
                    ┌────────────▼─────────────┐
                    │      Orchestrator         │
                    │  (tool dispatch + §5 hook)│
                    └────────────┬─────────────┘
                                 │
              ┌──────────┬───────┼───────┬──────────┐
              ▼          ▼       ▼       ▼          ▼
          ┌───────┐ ┌────────┐ ┌─────┐ ┌────────┐ ┌───────┐
          │ Scout │ │Planner │ │Build│ │Verifier│ │Scribe │
          │ (read)│ │ (plan) │ │(act)│ │(check) │ │(memo) │
          └───────┘ └────────┘ └─────┘ └────────┘ └───────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
     ┌────────────────┐ ┌───────────────┐ ┌────────────────┐
     │ ClaudeCode     │ │ Local         │ │ OpenAICloud    │
     │ Runtime        │ │ Runtime       │ │ Runtime        │
     │ (Anthropic API)│ │ (Ollama/vLLM) │ │ (OpenAI/Gemini)│
     └────────────────┘ └───────────────┘ └────────────────┘
```

### Five Subagents

| Agent | Role | Tools |
|-------|------|-------|
| **Scout** | Read-only investigation. Finds files, greps symbols, summarizes. | Read, Grep, Glob, Bash |
| **Planner** | Designs implementation plans. Read-only — never executes. | Read, Grep, Glob, Bash |
| **Builder** | Executes approved plans. Edits files, runs commands. | Read, Edit, Write, Bash, Grep, Glob |
| **Verifier** | Independently checks Builder output. Runs tests, probes health. | Read, Grep, Glob, Bash |
| **Scribe** | Maintains durable memory. Updates records across sessions. | Read, Edit, Write, Grep, Glob |

### Three Runtimes

| Runtime | Backend | Config |
|---------|---------|--------|
| `claude` (default) | Anthropic Messages API | `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` |
| `local` | Ollama, vLLM, llama.cpp | `PRAXIS_LOCAL_BASE_URL` + `PRAXIS_LOCAL_MODEL` |
| `cloud` | OpenAI, Gemini, OpenRouter, Groq | `PRAXIS_CLOUD_API_KEY` + `PRAXIS_CLOUD_BASE_URL` |

Set `PRAXIS_RUNTIME=local` or `PRAXIS_RUNTIME=cloud` to switch. Use `convergence.yaml` to route different subagents to different runtimes.

### Three Operating Modes

- **Assistant** — personal computing: documents, notes, schedules
- **Workstation** — software development: code, tests, version control
- **Operator** — infrastructure: services, deployments, live systems

The orchestrator infers the mode from workspace contents. Each mode adjusts defaults for caution level and verification strategy.

## Integrations

Eight built-in tools for workstation tasks:

| Tool | What it does | Requires |
|------|-------------|----------|
| **GitHub** | PRs, issues, diffs | `gh` CLI + `GITHUB_TOKEN` |
| **Analyze** | Coverage, complexity, lint | `coverage`, `radon`, `pylint` |
| **TestRunner** | pytest with parsed output | `pytest` |
| **Dependencies** | Outdated packages, vulnerability scan | `pip`, `pip-audit` |
| **WebResearch** | Search + page fetch | `PRAXIS_WEB_SEARCH_API_KEY` + domain allowlist |
| **FileManager** | Search, summarize, git status, disk usage | (stdlib — no extra deps) |
| **Email** | IMAP inbox read + local draft staging | `PRAXIS_EMAIL_*` vars |
| **Calendar** | iCal feed read + event proposal staging | `PRAXIS_CALENDAR_URL` |

Email and Calendar follow the **read-safe / write-escalate** pattern: read operations run autonomously, but there is no send or create action. `draft_email` and `propose_event` save files locally for human review.

Install analysis tools: `pip install praxis[analyze]`

See `.env.example` for full configuration reference.

## Queue and Daemon

Praxis can run unattended, processing tasks from a queue:

```bash
# Add tasks to .praxis/queue/tasks.jsonl, then:
python -m praxis --queue            # process queue, exit when empty
python -m praxis --daemon           # run in background
python -m praxis --status           # check daemon + queue stats
python -m praxis --stop             # graceful shutdown
```

Multi-stage tasks are checkpointed — if the daemon crashes, it resumes from the last completed stage.

## Running Tests

```bash
pip install praxis[dev]
python -m pytest tests/ -v          # 388 tests, all mocked
```

No real API calls. All tests use a mock client from `tests/conftest.py`.

## Contributing

1. Fork and create a feature branch
2. Write tests for new functionality (no real API calls — use `FakeClient`)
3. Run the full test suite: `python -m pytest tests/ -v`
4. Ensure the §5 hook still passes for all tool calls
5. Open a PR against `main`

The `§5 escalation boundary` is the one thing you should never bypass, weaken, or work around — in code or in tests.

## License

MIT
