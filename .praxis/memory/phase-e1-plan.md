# Phase E-1 Plan: OAuth Token Propagation to Subprocesses

## Problem

`execute_bash()` and `execute_grep()` in `tools.py` use implicit env inheritance
for subprocess spawning. The OAuth token propagates only by accident. If any
intermediate code clears the env (or the user's shell didn't export the variable),
subprocesses lose access silently. Additionally, no secret filtering exists on
tool output — if a subprocess prints the token, it leaks.

`hooks.py` already uses explicit `env={**os.environ}` — correct pattern.

## Design

### 1. Explicit env construction (`tools.py`)

Both `execute_bash()` and `execute_grep()` will construct an explicit `env` dict
that mirrors the hooks.py pattern:

```python
env = {**os.environ}
# Ensure PRAXIS_WORKSPACE_ROOT is set for child processes
env["PRAXIS_WORKSPACE_ROOT"] = str(config.workspace_root)
env["PRAXIS_MEMORY_ROOT"] = str(config.memory_root)
```

Pass `env=env` to `subprocess.run()`. This makes propagation explicit and
consistent with hooks.py.

### 2. Secret filtering on tool output

Add `_redact_secrets(text: str) -> str` in `tools.py`:
- Reads `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY` from `os.environ`
- If either value appears in the text, replaces with `[REDACTED]`
- Applied to all subprocess output before returning to the model

This satisfies §5.8 secret filtering — tokens never surface in tool results.

### 3. No logging of token values

The token value is never logged, printed, or included in error messages.
Only the auth *method* ("oauth" or "api_key") is logged (already done in __main__.py).

## Files changed

- `praxis/tools.py` — add `_redact_secrets()`, pass explicit `env=` in
  `execute_bash()` and `execute_grep()`, filter output through redaction.

## §5 compliance

- No new network egress — subprocesses still constrained by escalation-boundary hook
- Token only exists in memory and env vars, never in files or output
- Consistent with existing hooks.py pattern

## Test plan

- Existing 94 tests still pass (no behavior change for well-behaved subprocesses)
- New tests: verify `_redact_secrets()` strips tokens from output
- New test: verify explicit env is passed to subprocess calls
