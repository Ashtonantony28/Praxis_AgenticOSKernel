# First Live API Round-Trip — CONFIRMED

**Date:** 2026-05-25
**Branch:** claude/blissful-franklin-VIMiH
**Phase:** G (first live run)
**Status:** FULL SUBAGENT PATH CONFIRMED

---

## Run 1 — Direct tool call (orchestrator level)

```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)
export PRAXIS_MODEL=claude-haiku-4-5-20251001
python -m praxis "Use the Glob tool to list files matching '*.py' in the praxis/ directory. Return the file listing."
```

**Auth path:** `CLAUDE_CODE_OAUTH_TOKEN` → `ClaudeCodeRuntime(auth_token=...)` → Bearer header → 200 OK
**Model:** `claude-haiku-4-5-20251001`

**Output:**
```
[praxis] runtime claude: auth=oauth
Here are the Python files in the `praxis/` directory:

1. `praxis/__init__.py`
2. `praxis/__main__.py`
3. `praxis/config.py`
4. `praxis/convergence.py`
5. `praxis/hooks.py`
6. `praxis/orchestrator.py`
7. `praxis/subagents.py`
8. `praxis/tools.py`

8 Python files found in total.
```

**What this exercises:** `run_loop` → API call → model uses Glob → §5 hook allows → tool result → second API call → `end_turn` → text extracted → printed.

---

## Run 2 — Full subagent path (Scout spawned)

```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)
export PRAXIS_MODEL=claude-haiku-4-5-20251001
python -m praxis "Use the Agent tool to spawn the scout subagent with the prompt: list the files in the praxis/ directory"
```

**Auth path:** Same OAuth token, same runtime
**Model:** Haiku for orchestrator + Scout subagent

**What this exercises:** `run_loop` → model uses Agent tool → `_execute_with_hook` → `run_subagent("scout", ...)` → `spawn_subagent` → second independent `run_loop` with scout's system prompt → Scout uses Glob → result bubbles back up through orchestrator → final response returned.

**Confirmed:** OAuth → orchestrator → Scout subagent → live API call → result returned.

---

## What Phase G proved

1. **OAuth authentication works end-to-end.** `auth_token=` is the correct SDK parameter for `sk-ant-oat` tokens. `api_key=` causes 401.
2. **Tool dispatch works live.** §5 hook fires and allows workspace-safe operations.
3. **Subagent spawning works live.** `spawn_subagent` completes a full nested `run_loop`.
4. **Secret filtering is active.** Token never appears in output.
5. **The core architectural claim is validated.** Praxis can orchestrate subagents via real API calls.

---

## The fix (one line)

`praxis/runtime/claude_code.py:48`

```python
# Before (broken — 401 "invalid x-api-key"):
client = anthropic.Anthropic(api_key=oauth_token)

# After (correct — Bearer token → 200):
client = anthropic.Anthropic(auth_token=oauth_token)
```

Also added `PRAXIS_MODEL` env var to `orchestrator.py` to allow model selection without code changes. Default remains `claude-sonnet-4-6`.

---

## What F-1 got wrong

F-1 concluded: "Auth tokens are sandboxed from child processes."

Reality: `CLAUDE_CODE_OAUTH_TOKEN` is fully available in child `os.environ`. The actual failure was a 401 from the wrong SDK parameter — the token was there, just sent in the wrong HTTP header.

---

## Known limitations (not blockers)

- **Sonnet rate-limited on this OAuth session.** Haiku works. With a standalone `ANTHROPIC_API_KEY`, Sonnet works without restriction.
- **Context management is still append-only.** Multi-turn tasks will hit the window limit. Next phase should add summarization.
- **No retry logic.** A transient 429 causes a fatal exit. Exponential backoff needed for unattended operation.
