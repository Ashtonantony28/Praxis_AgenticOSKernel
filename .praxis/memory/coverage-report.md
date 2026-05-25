# Praxis Test Coverage Report

**Date:** 2026-05-25
**Method:** Manual analysis — tests per module, untested code paths identified by reading source.
**Test count:** 101 tests (94 pre-E-1 + 7 new)

---

## Module-level summary

| Module | Lines | Dedicated tests | Coverage quality |
|--------|-------|-----------------|-----------------|
| `praxis/__main__.py` | 69 | 0 | **Critical gap** |
| `praxis/runtime/base.py` | 93 | 0 | N/A (pure ABC) |
| `praxis/runtime/claude_code.py` | 169 | 9 | Partial — auth+errors covered, loop untested |
| `praxis/orchestrator.py` | 88 | 8 | Good |
| `praxis/convergence.py` | 92 | 16 | Excellent |
| `praxis/tools.py` | 231 | 20 | Good (improved in E-1) |
| `praxis/runtime/local.py` | 247 | 21 | Good |
| `praxis/subagents.py` | 72 | 8 | Good |
| `praxis/hooks.py` | 53 | 13 | Excellent |
| `praxis/config.py` | 35 | 6 | Good |

---

## Worst coverage: `praxis/__main__.py`

### Untested code paths

1. **`_create_runtimes(conv)`** — creates Claude/Local runtimes based on convergence config, builds override dict. No test exercises this function despite it containing the core wiring logic.

2. **`main()` arg parsing** — `sys.argv[1:]` vs `sys.stdin.read()` branch. Neither path tested.

3. **`main()` error handling:**
   - `KeyboardInterrupt` → stderr message + exit 1
   - `SystemExit` → re-raised (passthrough)
   - Generic `Exception` → `[praxis] fatal: {exc}` + exit

4. **stderr logging** — runtime auth method and local model URL are logged. Not tested.

### Why it matters

`__main__.py` is the integration glue — if `_create_runtimes()` breaks, the entire orchestrator fails to start. The error handling paths are the user's last line of defense against crashes.

### Recommended test approach

- Mock `ClaudeCodeRuntime.from_env()` and `LocalRuntime.from_env()`
- Test `_create_runtimes()` with various ConvergenceConfig inputs
- Test `main()` with mocked argv and verify it wires correctly
- Test each error handler path

---

## Second worst: `praxis/runtime/claude_code.py` multi-turn loop

### Tested (9 tests in `test_runtime.py`)
- `from_env()` — OAuth priority, API key fallback, scrubbing, missing auth
- `run_loop()` error paths — AuthenticationError, APIConnectionError, RateLimitError

### Untested
- `run_loop()` multi-turn tool calling (call → tool result → call → end_turn)
- `execute_tool()` — parsing tool_use blocks, invoking executor
- `manage_context()` — append behavior
- `_extract_text()` — text block extraction
- `spawn_subagent()` — delegation to run_loop

Note: Some of these are tested *indirectly* via `test_orchestrator.py`, but no
direct unit tests exercise the ClaudeCodeRuntime methods in isolation.

---

## Well-covered modules

- **`hooks.py`** (13 tests / 53 lines) — every path exercised including timeouts, space-in-path
- **`convergence.py`** (16 tests / 92 lines) — YAML parsing, env override, validation, routing
- **`local.py`** (21 tests / 247 lines) — from_env, run_loop, tool dispatch, all error paths
