# Unattended Overnight Readiness Assessment

**Date:** 2026-05-25  
**Verdict: CONDITIONALLY READY**

---

## What is working

| Capability | Status |
|-----------|--------|
| Retry on 429 rate limit | 5 retries / 135s backoff (5+10+20+40+60s) |
| Crash recovery | `recover_interrupted()` marks `running` → `failed` on startup |
| Staged task SIGTERM | Saves checkpoint, reverts to `pending`, resumes on restart |
| Checkpoint atomicity | `os.replace()` — writes are now atomic, no partial files on crash |
| Daemon mode | `--daemon` / `--stop` / `--status` working |
| Auth | OAuth primary, API key fallback; secrets never leak into tool results |
| §5 hook | Escalation boundary enforced on every tool call |
| Test suite | 205 tests pass |

---

## Risks requiring operator attention

| Risk | Impact | Workaround |
|------|--------|------------|
| **Atomic task SIGTERM** — `recover_interrupted` marks completed tasks `failed` if they finished after SIGTERM but before exit | False failure status in queue | Use staged tasks for important long-running work; check `.praxis/queue/results/` for actual output |
| **503 UNAVAILABLE not retried** — transient cloud overload exits immediately | Task fails on Gemini free tier spikes | Fix pending: retry 503 same as 429 in `OpenAICloudRuntime._call_api()` |
| **No log rotation** | `.praxis/logs/praxis.log` grows unbounded overnight | Monitor file size manually; rotate before each run |
| **No queue size cap** | Runaway task injection could fill disk | Keep queue < 20 tasks until cap is implemented |
| **No per-task token tracking** | No spend visibility, no budget enforcement | Monitor API dashboard manually |
| **Free-tier RPM** | 5-stage pipeline exhausts Gemini free tier RPM | Use paid tier, or add inter-stage sleep |

---

## Minimum conditions for safe overnight operation

1. **Use staged tasks** (`stages` list) for any work that must be resumable — not atomic tasks.
2. **Use a paid-tier API key** — free tier RPM is insufficient for multi-stage pipelines without pacing.
3. **Pre-flight check**: confirm `.praxis/logs/praxis.log` is empty/rotated before starting the daemon.
4. **Keep the task queue small** (< 20 tasks) until a queue size cap is implemented.
5. **After each run**: manually check `.praxis/queue/results/` for atomic task output — do not rely solely on queue status for atomic tasks.
6. **Ensure API key** has sufficient quota for the planned task count.

---

## Open work items before full unattended readiness

| Item | Priority | File |
|------|----------|------|
| Retry 503 UNAVAILABLE with same backoff as 429 | HIGH | `praxis/runtime/cloud.py` |
| Log rotation for `.praxis/logs/praxis.log` | MEDIUM | `praxis/daemon.py` |
| Queue size cap (configurable, default 50) | MEDIUM | `praxis/queue.py` |
| Per-task token tracking (log `usage` from API response) | LOW | `praxis/runtime/cloud.py`, `openai_base.py` |
| Inter-stage delay option for free-tier pacing | LOW | `praxis/queue_runner.py` |
