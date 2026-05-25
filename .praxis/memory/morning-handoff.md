# Morning handoff — Phase 0 complete, ready for Phase A

**Date:** 2026-05-25
**Status:** Phase 0 **done**. Minimal Python orchestrator built, 43 tests
green, §5 hook enforced. Phase A (runtime abstraction) is next.

---

## 1. Exact repo state

**Repo:** `Ashtonantony28/Praxis_AgenticOSKernel`
**Branch:** `claude/blissful-franklin-VIMiH`
**Main branch:** `claude/plan-execute-mode-switch-zCz38`

```
praxis-system-prompt.md              # the spec (§0–§11), WORKSPACE_ROOT now env-var based
CLAUDE.md                            # project conventions — read this first
pyproject.toml                       # deps: anthropic, pytest

praxis/                              # the orchestrator (524 lines total)
  __init__.py                        #   package marker, version
  __main__.py                        #   `python -m praxis` entrypoint
  config.py                          #   Config.from_env() — workspace/memory/hook from env
  subagents.py                       #   parse .claude/agents/*.md → SubagentDef
  hooks.py                           #   run_pretool_hook() — subprocess to escalation-boundary.py
  tools.py                           #   7 tool schemas + implementations
  orchestrator.py                    #   Orchestrator class — agent loop on anthropic messages API

tests/                               # 43 tests, all pass, all mocked (592 lines total)
  conftest.py                        #   FakeClient, FakeResponse, workspace fixtures
  test_config.py                     #   6 tests — env resolution, restrictive fallback
  test_subagents.py                  #   8 tests — YAML parsing, model mapping, all 5 agents
  test_hooks.py                      #   9 tests — allow/block for writes, network, control plane
  test_tools.py                      #   13 tests — Bash, Read, Edit, Write, Grep, Glob, schemas
  test_orchestrator.py               #   7 tests — init, end-to-end, hook block, subagent dispatch

.claude/agents/                      # 5 subagent definitions (unchanged)
  builder.md                         #   sonnet — executes approved plans
  planner.md                         #   sonnet — produces ordered plans
  scout.md                           #   haiku — read-only investigation
  scribe.md                          #   haiku — maintains memory
  verifier.md                        #   sonnet — checks builder output

.claude/hooks/escalation-boundary.py # §5 hook (unchanged)
.claude/settings.json                # hook wiring — now uses relative path

.praxis/memory/
  morning-handoff.md                 # this file
  phase0-plan.md                     # Phase 0 design plan (archived)
  .gitkeep

.gitignore
```

---

## 2. What Phase 0 built

A minimal Python orchestrator that makes the markdown spec executable:

1. **Agent loop** (`orchestrator.py`): Uses `anthropic` SDK
   `client.messages.create()` with tool use. Simple while loop — send
   message, process tool_use blocks, send results back, repeat until
   end_turn. Safety cap at 50 iterations.

2. **Tool dispatch** (`tools.py`): 7 tools registered — Bash, Read, Edit,
   Write, Grep, Glob, Agent. Each has a JSON schema for the API and a
   Python implementation. Agent is dispatched by the orchestrator (not
   tools.py).

3. **§5 hook enforcement** (`hooks.py`): Every tool call — in both
   orchestrator and subagent sessions — passes through
   `run_pretool_hook()` before execution. Subprocess call to
   `escalation-boundary.py`, JSON on stdin, exit 0 = allow, exit 2 =
   block. Blocked calls return an error string to the model.

4. **Subagent dispatch** (`subagents.py` + `orchestrator.py`): When the
   model calls `Agent(name="scout", prompt="...")`, the orchestrator
   looks up the SubagentDef, creates a new agent loop with the
   subagent's system prompt, restricted tools, and model. The subagent
   inherits the §5 hook unconditionally.

5. **Config** (`config.py`): Reads `PRAXIS_WORKSPACE_ROOT` and
   `PRAXIS_MEMORY_ROOT` from env vars. Restrictive fallback per §0: cwd
   if unset. Hook path derived as `workspace_root/.claude/hooks/escalation-boundary.py`.

### Path fixes applied
- `praxis-system-prompt.md` §0: `WORKSPACE_ROOT` and `MEMORY_ROOT` now
  reference `$PRAXIS_WORKSPACE_ROOT` instead of a stale hardcoded path.
- `.claude/settings.json`: hook command changed from absolute path to
  `python3 .claude/hooks/escalation-boundary.py` (portable across clones).

### What was deliberately left out
- `io.py` — no session transport needed yet
- `ExitPlanMode` — no plan/execute state machine yet
- `WebFetch` — wired in the hook (blocked) but not in tool schemas
- Runtime abstraction — that's Phase A

---

## 3. How to verify

```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)
python -m pytest tests/ -v          # 43 tests, all should pass
python -c "from praxis.orchestrator import Orchestrator"  # import check
```

No `ANTHROPIC_API_KEY` needed — all tests use FakeClient.

---

## 4. What Phase A should do

**Goal:** Wrap the Phase 0 orchestrator in a `Runtime` abstraction so
that different backends (local subprocess, hosted API, etc.) can be
swapped without changing the orchestrator logic.

The orchestrator at `praxis/orchestrator.py` is the working baseline.
Phase A should:

1. Extract an abstract `Runtime` interface from the concrete
   `Orchestrator` class — the agent loop, tool dispatch, and hook
   enforcement become capabilities the Runtime provides.
2. Keep the existing 43 tests green throughout. Add tests for the new
   abstraction layer.
3. Add `ExitPlanMode` tool and plan/execute state tracking (§4.5).
4. Do not touch the §5 hook behavior.
5. Do not add OAuth, API key plumbing, or MCP — those are later phases.

---

## 5. Recommended next-session prompt

> Begin Phase A: wrap the Phase 0 orchestrator in a Runtime abstraction.
> Read `CLAUDE.md` and `.praxis/memory/morning-handoff.md` for current
> state. The orchestrator at `praxis/orchestrator.py` is the baseline —
> 43 tests green. Use the full pipeline: Scout → Plan → Build → Verify →
> Scribe. Do not expand scope beyond the Runtime abstraction.
