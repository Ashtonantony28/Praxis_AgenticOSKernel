# Phase G Plan — Fix OAuth token passing to unblock live API calls

**Date:** 2026-05-25
**Branch:** claude/blissful-franklin-VIMiH
**Goal:** Complete one successful live API round-trip through `python -m praxis`

---

## Root Cause (identified by Scout)

`ClaudeCodeRuntime.from_env()` in `praxis/runtime/claude_code.py` line 48:
```python
client = anthropic.Anthropic(api_key=oauth_token)
```

The OAuth token (`sk-ant-oat01-...`) is passed as `api_key`, which sends it in the
`x-api-key` HTTP header. The Anthropic API rejects this with HTTP 401:
`invalid x-api-key`.

The correct parameter is `auth_token`, which sends it as a Bearer token in the
`Authorization` header. Verified empirically: `auth_token=token` returns a valid
response from `claude-haiku-4-5-20251001`.

## The Fix (minimum change)

**File:** `praxis/runtime/claude_code.py`, line 48
**Change:** `anthropic.Anthropic(api_key=oauth_token)` → `anthropic.Anthropic(auth_token=oauth_token)`

That's it. One parameter name change.

## Why F-1 missed this

F-1 concluded "auth tokens are sandboxed from child processes." This was wrong —
the token IS available in `os.environ` for child processes. The actual failure was
the 401 from using the wrong header, misdiagnosed as "token not available."

## Verification

After the fix, run:
```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)
python -m praxis "Use the Glob tool to list the files in praxis/ directory"
```

Expected: Sonnet uses the Glob tool, §5 hook allows it, result returned.

## Risk

None. This changes how an existing token is passed to the SDK. All tests use
`FakeClient` and don't hit `from_env()`, so no tests break.
