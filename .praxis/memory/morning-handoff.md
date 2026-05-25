# Morning handoff — Phase G complete

**Date:** 2026-05-25
**Status:** Phase G complete. First live API round-trip confirmed. Full subagent path confirmed.

---

## 1. Exact repo state

**Repo:** `Ashtonantony28/Praxis_AgenticOSKernel`
**Branch:** `claude/blissful-franklin-VIMiH`
**Main branch:** `claude/plan-execute-mode-switch-zCz38`

```
praxis-system-prompt.md              # the spec (§0–§11)
CLAUDE.md                            # project conventions — read this first
pyproject.toml                       # deps: anthropic, pyyaml, openai[local], pytest

praxis/                              # the orchestrator
  __init__.py                        #   package marker, version
  __main__.py                        #   `python -m praxis` — convergence config + runtime creation
  config.py                          #   Config.from_env() — workspace/memory/hook from env
  convergence.py                     #   ConvergenceConfig.load() — multi-runtime routing (Phase D)
  subagents.py                       #   parse .claude/agents/*.md → SubagentDef
  hooks.py                           #   run_pretool_hook() — §5 enforcement
  tools.py                           #   7 tool schemas + implementations + secret filtering (Phase E)
  orchestrator.py                    #   Orchestrator — PRAXIS_MODEL support added (Phase G)
  runtime/                           #   Provider abstraction (Phase A + C + D)
    __init__.py                      #     exports Runtime, ClaudeCodeRuntime, LocalRuntime
    base.py                          #     Abstract Runtime (4 abstract methods)
    claude_code.py                   #     ClaudeCodeRuntime — auth_token= fix (Phase G)
    local.py                         #     LocalRuntime — hardened error handling (Phase D)

tests/                               # 116 tests, all pass, all mocked
  conftest.py                        #   FakeClient, FakeResponse, workspace fixtures
  test_config.py                     #   6 tests
  test_convergence.py                #   16 tests
  test_subagents.py                  #   8 tests
  test_hooks.py                      #   17 tests
  test_tools.py                      #   20 tests
  test_orchestrator.py               #   8 tests
  test_runtime.py                    #   9 tests — updated for auth_token= (Phase G)
  test_local_runtime.py              #   21 tests
  test_main.py                       #   11 tests

.claude/agents/                      # 5 subagent definitions (builder, planner, scout, scribe, verifier)
.claude/hooks/escalation-boundary.py # §5 hook (device path fix from F-3 still in place)
.claude/settings.json                # hook wiring (unchanged)

.praxis/memory/
  morning-handoff.md                 # this file
  first-live-run.md                  # Phase G milestone — full live run results
  phase-g-plan.md                    # Phase G design plan
  f1-selforch-test.md               # Phase F-1 assessment (now superseded)
  [archived phase plans...]
```

---

## 2. What Phase G built

### The fix

One line in `praxis/runtime/claude_code.py`:

```python
# Before: OAuth token in x-api-key header → 401
client = anthropic.Anthropic(api_key=oauth_token)

# After: OAuth token as Bearer → 200
client = anthropic.Anthropic(auth_token=oauth_token)
```

The F-1 report misdiagnosed the failure as "tokens sandboxed from child processes."
Tokens were always available. The real bug was the wrong SDK parameter.

### Additional change

`orchestrator.py` now reads `PRAXIS_MODEL` env var (default: `claude-sonnet-4-6`).
Needed to test with Haiku (Sonnet is rate-limited on the OAuth session token).

### What was confirmed live

1. OAuth → API: authentication works, `auth_token=` is correct for `sk-ant-oat` tokens
2. Direct tool call: orchestrator → Glob → §5 hook → tool result → response
3. Subagent call: orchestrator → Agent tool → Scout spawned → Scout uses Glob → result bubbles up
4. Secret filtering: token never leaked into output

Full output recorded in `.praxis/memory/first-live-run.md`.

---

## 3. What stayed the same

All 116 pre-G tests pass (2 assertions updated to expect `auth_token=` instead of `api_key=`).

---

## 4. How to verify

```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)
export PRAXIS_MODEL=claude-haiku-4-5-20251001   # Haiku avoids OAuth rate limits

# Direct tool call (confirms auth + tool dispatch):
python -m praxis "Use the Glob tool to list files matching '*.py' in praxis/"

# Subagent call (confirms full path):
python -m praxis "Use the Agent tool to spawn scout with: list the files in praxis/"

# Full test suite:
python -m pytest tests/ -v
```

---

## 5. What the next session should tackle

### Priority 1: Full five-subagent pipeline on a real task

The single-subagent path works. The next proof is a real task that drives
Scout → Planner → Builder → Verifier → Scribe:

```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)
export PRAXIS_MODEL=claude-haiku-4-5-20251001
python -m praxis "Investigate how error handling works in this codebase, plan a small improvement, implement it, verify tests still pass, and write a memory entry documenting what changed."
```

This exercises:
- Scout: read code, find the error handling
- Planner: design the improvement
- Builder: implement it
- Verifier: run tests
- Scribe: write memory

Watch for: context window exhaustion (append-only `manage_context`), rate limiting
between subagent calls, the model not naturally chaining all five agents.

### Priority 2: Context window management

`manage_context()` appends indefinitely. A five-agent pipeline will likely hit the
limit. Implement a sliding window (keep last N messages) or summarize-and-compact
before the next unattended session. This is the most critical gap remaining.

### Priority 3: Retry on rate limit

Current behavior: 429 → `SystemExit`. For the five-subagent test to complete, add
exponential backoff (3 retries, 1s/2s/4s) before giving up. Small change, high value.

---

## 6. Build history

| Phase | What | Tests |
|-------|------|-------|
| 0 | Minimal orchestrator (tools, hooks, subagents, config) | 43 |
| A | Extract Runtime interface from Orchestrator | 43 |
| B | Subscription OAuth as primary auth | 52 |
| C | LocalRuntime for open-source models | 69 |
| D-1 | Harden failure paths (error handling) | 77 |
| D-2 | convergence.yaml multi-runtime routing | 94 |
| D-3 | Integration test report | 94 |
| E-1 | Token propagation + secret filtering | 101 |
| E-2 | Coverage analysis + pipeline assessment | 101 |
| F-1 | Live self-orchestration test (sandbox-limited) | 101 |
| F-2 | `__main__.py` test coverage (98%) | 112 |
| F-3 | §5 hook `/dev/null` device path fix | 116 |
| F-4 | Self-orchestration readiness assessment | 116 |
| G | **Fix OAuth auth_token= bug. First live run confirmed.** | 116 |
