# Morning handoff — Phase C complete, Phase D resequenced

**Date:** 2026-05-25 (evening update)
**Status:** Phase C complete. Real workload testing revealed 2 error handling gaps;
Phase D resequenced: harden failure paths first (D-1), then convergence.yaml (D-2).

---

## 1. Exact repo state

**Repo:** `Ashtonantony28/Praxis_AgenticOSKernel`
**Branch:** `claude/blissful-franklin-VIMiH`
**Main branch:** `claude/plan-execute-mode-switch-zCz38`

```
praxis-system-prompt.md              # the spec (§0–§11)
CLAUDE.md                            # project conventions — read this first
pyproject.toml                       # deps: anthropic, openai[local], pytest

praxis/                              # the orchestrator
  __init__.py                        #   package marker, version
  __main__.py                        #   `python -m praxis` — PRAXIS_RUNTIME selection
  config.py                          #   Config.from_env() — workspace/memory/hook from env
  subagents.py                       #   parse .claude/agents/*.md → SubagentDef
  hooks.py                           #   run_pretool_hook() — §5 enforcement
  tools.py                           #   7 tool schemas + implementations
  orchestrator.py                    #   Orchestrator — delegates to Runtime, owns tools/hooks
  runtime/                           #   Provider abstraction (Phase A + C)
    __init__.py                      #     exports Runtime, ClaudeCodeRuntime, LocalRuntime
    base.py                          #     Abstract Runtime (4 abstract methods)
    claude_code.py                   #     ClaudeCodeRuntime — from_env() with OAuth/API key
    local.py                         #     LocalRuntime — OpenAI-compatible (Ollama, vLLM)

tests/                               # 69 tests, all pass, all mocked
  conftest.py                        #   FakeClient, FakeResponse, workspace fixtures
  test_config.py                     #   6 tests — env resolution, restrictive fallback
  test_subagents.py                  #   8 tests — YAML parsing, model mapping
  test_hooks.py                      #   13 tests — allow/block + space-in-path regression
  test_tools.py                      #   13 tests — Bash, Read, Edit, Write, Grep, Glob, schemas
  test_orchestrator.py               #   7 tests — uses ClaudeCodeRuntime(FakeClient) now
  test_runtime.py                    #   5 tests — OAuth/API key priority, env scrubbing
  test_local_runtime.py              #   17 tests — LocalRuntime: from_env, run_loop, tools

.claude/agents/                      # 5 subagent definitions (unchanged)
.claude/hooks/escalation-boundary.py # §5 hook (unchanged)
.claude/settings.json                # hook wiring (unchanged)

.praxis/memory/
  morning-handoff.md                 # this file
  phase-c-plan.md                    # Phase C design plan
  phase-b-plan.md                    # Phase B design plan (archived)
  runtime-abstraction-plan.md        # Phase A design plan (archived)
  phase0-plan.md                     # Phase 0 design plan (archived)
  .gitkeep
```

---

## 2. What Phase C built

### LocalRuntime (`praxis/runtime/local.py`)

Full `Runtime` implementation targeting any OpenAI-compatible endpoint:

1. **`run_loop`** — client-side agent loop via `chat.completions.create()`.
   Converts tool schemas (Anthropic → OpenAI format), handles tool_calls
   with JSON-string arguments, feeds results back as `role: "tool"` messages.
2. **`spawn_subagent`** — delegates to `run_loop` (no native subagent support).
3. **`execute_tool`** — parses OpenAI tool_call objects (or dicts), decodes
   JSON arguments, invokes the Orchestrator's tool_executor callback.
4. **`manage_context`** — appends messages in OpenAI format (handles both
   plain strings and full message dicts with `role` key).

### Runtime selection (`__main__.py`)

`PRAXIS_RUNTIME` env var: `"claude"` (default) or `"local"`.
Logs runtime info to stderr on startup.

### Configuration

| Env var                 | Default                  | Purpose              |
|------------------------|--------------------------|----------------------|
| `PRAXIS_RUNTIME`       | `claude`                 | Runtime selection    |
| `PRAXIS_LOCAL_BASE_URL`| `http://localhost:11434` | Server URL           |
| `PRAXIS_LOCAL_MODEL`   | `llama3.1:8b`            | Default local model  |

### Model resolution

Claude model IDs (`claude-*`) are automatically replaced with
`PRAXIS_LOCAL_MODEL`. Non-Claude model IDs pass through unchanged.

### Dependency

`openai>=1.0` added as optional dependency: `pip install praxis[local]`.
Clean SystemExit if openai package is missing and local runtime is selected.

---

## 3. What stayed the same

- `runtime/base.py` — Runtime interface unchanged (4 abstract methods)
- `orchestrator.py` — unchanged
- `tools.py`, `hooks.py`, `config.py`, `subagents.py` — unchanged
- §5 hook enforcement — verified: all 13 hook tests pass
- All 52 pre-existing tests — unchanged and passing

---

## 4. How to verify

```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)
python -m pytest tests/ -v          # 69 tests, all should pass
python -c "from praxis.runtime import Runtime, ClaudeCodeRuntime, LocalRuntime"

# With Ollama running:
export PRAXIS_RUNTIME=local
python -m praxis "hello"            # should get a response from llama3.1:8b
```

---

## 5. Real workload test findings (2026-05-25 evening)

### Task 1: ClaudeCodeRuntime with OAuth
- Auth path selection: **PASS** — `[praxis] auth: oauth` logged correctly
- Env scrubbing: **PASS** — API key removed from os.environ when OAuth active
- No-auth error handling: **PASS** — clean SystemExit message
- API call: 401 (expected with placeholder token)
- §5 hook wiring: correct per scout trace, untested in live run (auth crash before tool dispatch)
- **Error gap:** raw anthropic SDK traceback on auth failure (no user-friendly wrapper)

### Task 2: ClaudeCodeRuntime with API key
- Auth path selection: **PASS** — `[praxis] auth: api_key` logged correctly
- Same auth error behavior as Task 1

### Task 3: LocalRuntime
- Runtime selection: **PASS** — logs runtime info correctly
- from_env(): **PASS** — client created, model resolved
- Connection refused: expected (Ollama not running)
- **Error gap:** 50+ line traceback from httpx internals (no user-friendly wrapper)

### Cross-cutting findings
- **Test suite:** 69 tests all green (all mocked, no real API calls)
- **Import error gap:** ClaudeCodeRuntime.from_env() missing try/except on `import anthropic`
  — raw ModuleNotFoundError. LocalRuntime wraps its import correctly.
- Invalid PRAXIS_RUNTIME: **PASS** — clean error message
- All runtime wiring confirmed correct by scout

---

## 6. Phase D resequenced: hardening first

**Phase D-1: Harden failure paths (PREREQUISITE)**
- [ ] Wrap `import anthropic` in try/except with clean SystemExit (match LocalRuntime pattern)
- [ ] Add connection error handling in both run_loop() implementations
- [ ] Wrap auth/network errors in user-friendly messages (not raw SDK tracebacks)

**Phase D-2: Convergence.yaml multi-runtime routing (ORIGINAL GOAL)**
- [ ] Define convergence.yaml schema — route subagent roles to different runtimes:
  ```yaml
  runtimes:
    default: claude
    overrides:
      scout: local
      scribe: local
  local:
    base_url: http://localhost:11434
    model: llama3.1:8b
  ```
- [ ] Update `Orchestrator` to hold multiple runtimes, route by subagent role
- [ ] Add config parsing in `praxis/config.py` or new `praxis/convergence.py`
- [ ] Tests: routing logic, fallback behavior, invalid config handling

**Phase D-3: Live integration test (REQUIRES REAL AUTH + OLLAMA)**
- [ ] Re-run 3-task workload with real credentials
- [ ] Confirm §5 hook fires during actual tool execution
- [ ] Write codebase-audit.md output to .praxis/memory/

---

## 7. Recommended next-session prompt

> Begin Phase D-1: harden failure paths in both runtimes. Read
> `CLAUDE.md` and `.praxis/memory/morning-handoff.md` for current state
> and the 2 error-handling gaps found in real workload testing. Wrap
> raw SDK tracebacks in user-friendly messages. Once D-1 is green,
> Phase D-2 (convergence.yaml routing) can proceed. Use the full
> pipeline: Scout → Plan → Build → Verify → Scribe. Do not expand
> scope beyond error handling and the routing config.
