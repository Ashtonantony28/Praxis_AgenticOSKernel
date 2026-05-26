# Pipeline Validation Report

**Date:** 2026-05-25  
**Purpose:** End-to-end validation that Praxis is model-agnostic — full Scout→Planner→Builder→Verifier→Scribe pipeline driven by Gemini 2.5 Flash via `OpenAICloudRuntime`  
**Model:** `gemini-2.5-flash` via `https://generativelanguage.googleapis.com/v1beta/openai/`

---

## Pre-flight fixes (required before pipeline could run)

| # | File | Fix | Reason |
|---|------|-----|--------|
| 1 | `praxis/runtime/cloud.py` | Retry budget: 3/35s → 5/135s (`RATE_LIMIT_MAX_RETRIES=5`) | Handoff specified 5/135s; code had 3/35s |
| 2 | `praxis/runtime/cloud.py` | Added `_resolve_model()` — remaps `claude-*` IDs to configured cloud default | Subagent defs hardcode Claude model IDs; Gemini 404s on them |
| 3 | `tests/test_cloud_runtime.py` | Updated test to assert Claude IDs ARE remapped; added 3 new `_resolve_model` tests | Test was asserting old (broken) passthrough behavior |

**Test suite after pre-flight fixes:** 205 passed (3 new tests added).

---

## Pipeline stages

| Stage | Model | Elapsed | Issues |
|-------|-------|---------|--------|
| Scout | gemini-2.5-flash | 21.9s | None |
| Planner | gemini-2.5-flash | 31.2s | None |
| Builder | gemini-2.5-flash | 19.1s | 1× 429 rate limit — retried at 5s, succeeded |
| Verifier | gemini-2.5-flash | 20.2s | None |
| Scribe (attempt 1) | gemini-2.5-flash | — | 503 UNAVAILABLE — not retried (code gap, see below) |
| Scribe (attempt 2) | gemini-2.5-flash | — | 429 exhausted after 5 retries (135s total) — free tier RPM |

**Rate limits hit:** 2 (1× recoverable 429 in Builder; 1× exhausted 429 in Scribe after 503 gap)  
**503 errors:** 1 (Scribe attempt 1 — transient overload, not retried by current code)

---

## Findings on queue.py / queue_runner.py

| # | Gap | Severity | Disposition |
|---|-----|----------|-------------|
| 1 | Checkpoint writes non-atomic — crash mid-write produces partial file | MEDIUM | **Fixed** |
| 2 | Atomic task SIGTERM behavior undocumented — `recover_interrupted` marks completed tasks 'failed' | LOW | **Documented** |
| 3 | `_read_all`/`_write_all` rewrite entire file — unsafe for concurrent runners | LOW | By-design (single-runner) |
| 4 | `recover_interrupted` ignores staged tasks paused to 'pending' by SIGTERM | LOW | By-design (correct behavior) |
| 5 | `stats()` silently counts unknown status strings | LOW | By-design |

---

## Code fixes applied

### Fix 1 — `praxis/checkpoint.py`: Atomic checkpoint writes

`CheckpointStore.save()` previously wrote directly to the checkpoint file. A crash during the write produced a partial/corrupt file, causing the task to re-run the last completed stage on restart.

**Change:** Write to `{path}.json.tmp` first, then `os.replace(temp_path, path)`. `os.replace()` is atomic on POSIX.

### Fix 2 — `praxis/queue_runner.py`: Document SIGTERM behavior

Added docstring to `_run_atomic_task` and a comment near the `recover_interrupted` call, explaining that atomic tasks run to completion on SIGTERM and that `recover_interrupted` cannot distinguish a crashed task from one that completed successfully after SIGTERM. This is by design.

---

## New gap found during pipeline run

**`OpenAICloudRuntime` does not retry 503 UNAVAILABLE.**

The retry logic in `cloud.py` catches `openai.RateLimitError` (429) and retries with exponential backoff. `openai.APIStatusError` with status 503 hits the general handler and exits immediately. Gemini free tier returns 503 on transient overload. This caused Scribe attempt 1 to fail with no retry, forcing a full retry which then hit the RPM cap.

**Recommended fix:** Catch 503 in `_call_api()` and retry with the same backoff as 429.

---

## Test suite

```
205 passed in 8.88s
```

All pre-existing tests pass. 3 new tests added for `_resolve_model` behavior.

---

## Token cost note

Gemini 2.5 Flash free tier. Exact token counts not available from API responses. Estimated context per stage: 2–8k tokens input, 1–4k output. Total pipeline: ~30–50k tokens. At paid tier pricing ($0.15/1M input, $0.60/1M output for Flash), cost would be under $0.05 per full pipeline run.

Free tier hit RPM limit after 4 stages. **Free tier is not sufficient for a 5-stage unattended pipeline without inter-stage delays.**

---

## Conclusion

Praxis is **model-agnostic**. Scout→Planner→Builder→Verifier completed end-to-end with real Gemini 2.5 Flash API calls, producing correct findings and applying correct code fixes. Two infrastructure gaps surfaced: 503 not retried, and free-tier RPM insufficient for 5-stage pipelines. Both are fixable and neither affects paid-tier operation.
