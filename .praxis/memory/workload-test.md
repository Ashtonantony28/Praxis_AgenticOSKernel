# Workload Test Report — 2026-05-25

Baseline: `python -m pytest tests/ -v --tb=short` — **69 passed in 3.57s**. All mocked tests green. This report covers real-path (live network/auth) workload testing across all three runtime paths.

---

## 1. What worked

**Runtime selection and startup logging** — all three paths correctly identified and announced themselves to stderr:

- `PRAXIS_RUNTIME=claude` + `CLAUDE_CODE_OAUTH_TOKEN` set: logged `[praxis] auth: oauth`
- `PRAXIS_RUNTIME=claude` + `ANTHROPIC_API_KEY` set: logged `[praxis] auth: api_key`
- `PRAXIS_RUNTIME=local`: logged `[praxis] runtime: local (http://localhost:11434, model: llama3.1:8b)`

**OAuth env scrubbing** — when both `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY` are set, the API key is correctly removed from `os.environ` before the Anthropic client is constructed. This prevents silent SDK override.

**No-auth error path** — when neither token is set, `ClaudeCodeRuntime.from_env()` raises `SystemExit` with a clean, actionable message. No raw traceback.

**Invalid runtime selection** — `PRAXIS_RUNTIME=badvalue` exits cleanly with the valid-values list.

**LocalRuntime missing-dependency path** — when `openai` is not installed, `LocalRuntime.from_env()` raises `SystemExit` with an install hint, not a raw `ModuleNotFoundError`.

**Code path wiring** — Scout confirmed all three runtime paths are structurally connected: `__main__._create_runtime()` → `Orchestrator` → `runtime.run_loop()` → `tool_executor` → `_execute_with_hook()` → hook. No dead ends.

---

## 2. What broke

**Auth errors produce raw SDK tracebacks.** Both `ClaudeCodeRuntime` auth paths failed at `client.messages.create()` with `anthropic.AuthenticationError: 401`. The exception propagates unhandled through `run_loop()` and `Orchestrator.run()` all the way to the terminal — 20+ lines of Anthropic SDK internals. There is no `try/except` around the API call in `run_loop()`.

**Connection failures produce massive httpx tracebacks.** `LocalRuntime.run_loop()` failed at `client.chat.completions.create()` with `httpx.ConnectError: [Errno 111] Connection refused`. This produced 50+ lines of httpx/httpcore internals because `run_loop()` has no error handling around the network call.

**§5 hook not exercised in any workload run.** All three paths crashed before reaching a tool-dispatching turn. The hook is wired correctly in code but has zero real-path test coverage from these workloads. This is a gap in confidence, not a code defect — but it means the first time the hook path fires in production, there is no empirical baseline.

---

## 3. Where runtime differences caused friction

**Asymmetric error handling in `from_env()`.** `LocalRuntime.from_env()` wraps `import openai` in `try/except ImportError` and raises a clean `SystemExit`. `ClaudeCodeRuntime.from_env()` does `import anthropic` with no guard. If `anthropic` is not installed, the user gets a raw `ModuleNotFoundError` traceback, not an actionable message. This is a direct inconsistency: the two runtimes do not follow the same safety convention at the import boundary.

**Error surface area scales with protocol complexity.** `ClaudeCodeRuntime` has a shallower failure surface (one API call per turn). `LocalRuntime` has a deeper one: the httpx/httpcore stack beneath the OpenAI SDK adds layers that, when they fail, produce significantly longer tracebacks. Neither runtime wraps its inner loop call. The LocalRuntime's traceback volume is substantially worse for operators reading a log.

**Model resolution is runtime-specific and invisible on failure.** `LocalRuntime._resolve_model()` silently substitutes Claude model IDs with `PRAXIS_LOCAL_MODEL`. If that env var is wrong or the model is not pulled in Ollama, the error will arrive as a cryptic API-level rejection rather than a startup-time validation message. `ClaudeCodeRuntime` passes model IDs directly to the Anthropic API, where bad IDs produce SDK errors with no praxis-level context.

---

## 4. What Phase D should actually prioritize

Evidence-based, ordered by operational risk:

**First: Wrap the inner loop in both runtimes.**
`ClaudeCodeRuntime.run_loop()` and `LocalRuntime.run_loop()` need `try/except` around the provider API call. Catch `anthropic.APIError` (and subclasses) in the Claude path; catch `openai.OpenAIError` and `httpx.ConnectError` in the local path. Translate to a short `[praxis] error: ...` message and a non-zero exit. This is the highest-priority gap: it affects every real invocation and makes the system appear broken to operators even when the failure is expected (bad key, server down).

**Second: Guard the `import anthropic` in `ClaudeCodeRuntime.from_env()`.**
`LocalRuntime.from_env()` already does this correctly. `ClaudeCodeRuntime.from_env()` should match: wrap `import anthropic` in `try/except ImportError` and raise `SystemExit` with an install hint. One-line fix, full parity.

**Third: Get §5 hook exercised on at least one real tool call.**
The hook has 12 unit tests (all mocked), but no real-path coverage in workloads. A single integration test with a live `bash echo` against the real hook script would give a meaningful baseline. This does not block Phase D, but the confidence gap is real.

**Then: convergence.yaml routing (original Phase D plan).**
The routing layer is still the correct architectural next step. The agent-capability routing problem is valid and worth solving. But it should land on top of a runtime that fails gracefully — otherwise, routing to a broken path will surface as an opaque crash rather than a meaningful routing error. Harden failure paths first, then add routing.

**Summary:** The codebase is structurally sound and the test suite is clean. The gap is exclusively at system boundaries — the seam between praxis code and external services (Anthropic API, Ollama, the `anthropic`/`openai` packages). Phase D should treat boundary hardening as a prerequisite to, or concurrent with, convergence routing.
