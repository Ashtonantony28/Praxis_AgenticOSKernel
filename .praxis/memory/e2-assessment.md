# E-2 Assessment: Pipeline on a Real Task

**Date:** 2026-05-25
**Task:** Identify worst test coverage module, write report.
**Pipeline:** Scout → Planner → Builder → Verifier → Scribe

---

## How the pipeline performed

### What worked

1. **Scout phase** delivered a clear inventory — read all source files, counted tests
   per module, identified untested code paths. The structured approach (lines vs tests
   vs untested paths) made the gap obvious immediately.

2. **The fix in E-1 was clean.** Explicit env propagation + secret filtering is a
   small, testable change that solves the stated problem. 7 new tests all passed
   first try.

3. **§5 hook fired correctly** — blocked a `wc -l ... 2>/dev/null` command because
   the redirect pattern was interpreted as writing outside workspace. This is the
   hook being conservative (correct behavior).

### Friction points

1. **No real API calls were made.** The E-2 task was supposed to exercise "real API
   calls throughout" but the pipeline ran entirely within the Claude Code session
   that's already running — not via `python -m praxis`. The orchestrator wasn't
   actually invoked as a separate process. This means we haven't truly validated
   end-to-end auth propagation in production.

2. **The "pipeline" is still manual sequencing in a single session.** There's no
   mechanism for Praxis to orchestrate itself — the subagents (scout, planner,
   builder, verifier, scribe) are defined but the orchestrator that chains them
   hasn't been tested with real API calls. The pipeline discipline is enforced by
   the human's instructions, not by the system.

3. **`__main__.py` has zero integration tests** partly because testing it requires
   either real credentials or complex mocking of the full startup path. This is
   a structural gap — the most critical code (startup wiring) is the hardest to test.

4. **§5 hook over-triggers on stderr redirects.** The `2>/dev/null` pattern is safe
   (writing to a device, not a file outside workspace) but the hook's regex blocks it.
   This is a minor usability friction that will accumulate.

---

## Next gaps to close (in priority order)

1. **Live end-to-end test.** Run `python -m praxis "describe this repo"` with real
   OAuth creds and confirm the full loop works: auth → API call → tool use → §5
   hook fires → result returned. This is still unvalidated.

2. **`__main__.py` test coverage.** Add integration tests for `_create_runtimes()`
   and the `main()` error paths. This is the highest-risk untested code.

3. **§5 hook: relax device writes.** `/dev/null`, `/dev/stdout`, `/dev/stderr` should
   be allowed. Currently the path-based regex blocks them.

4. **Self-orchestration.** The pipeline works when a human sequences the steps.
   The next real milestone is Praxis orchestrating its own pipeline — invoking
   scout, waiting for results, feeding them to planner, etc. This requires the
   multi-turn loop to actually work with real API calls.

5. **Context management.** `manage_context()` is append-only. A real multi-turn
   conversation will hit context limits. Summarization/pruning is needed before
   any non-trivial real task can complete.
