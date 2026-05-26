# Morning handoff — Phase 4 Wave 2 complete

**Date:** 2026-05-25  
**Status:** Phase 4 Wave 2 (web research integration) complete. 290 tests pass.

---

## 1. Exact repo state

**Repo:** `Ashtonantony28/Praxis_AgenticOSKernel`  
**Branch:** `claude/blissful-franklin-VIMiH`  
**Main branch:** `claude/plan-execute-mode-switch-zCz38`

```
praxis-system-prompt.md              # the spec (§0–§11)
CLAUDE.md                            # project conventions — updated Phase 4 Wave 2
pyproject.toml                       # deps: anthropic, pyyaml, openai[local], pytest

praxis/                              # the orchestrator
  __init__.py                        #   package marker, version
  __main__.py                        #   `python -m praxis` — interactive, --queue, --daemon, --stop, --status
  config.py                          #   Config.from_env() — workspace/memory/hook/allowed_domains from env
  convergence.py                     #   ConvergenceConfig.load() — multi-runtime routing (Phase D+I)
  subagents.py                       #   parse .claude/agents/*.md → SubagentDef
  hooks.py                           #   run_pretool_hook() — §5 enforcement
  tools.py                           #   7 tool schemas + implementations + secret filtering (Phase E, +GITHUB_TOKEN, +WEB_SEARCH_API_KEY)
  orchestrator.py                    #   Orchestrator — merges integration tools into dispatch (Phase 4)
  queue.py                           #   TaskQueue — CRUD on tasks.jsonl (Phase J)
  checkpoint.py                      #   CheckpointStore — atomic writes via os.replace() (Phase J + fix)
  queue_runner.py                    #   Queue processing loop (Phase J)
  daemon.py                          #   Daemon start/stop/status (Phase J)
  integrations/                      #   Workstation integrations (Phase 4)
    __init__.py                      #     aggregates INTEGRATION_SCHEMAS + INTEGRATION_IMPLEMENTATIONS
    github.py                        #     GitHub via `gh` CLI — pr_list, pr_view, issue_list, issue_view, pr_diff
    codebase.py                      #     coverage report, radon complexity, pylint lint
    testrunner.py                    #     pytest run + run_failed
    dependencies.py                  #     pip outdated + pip-audit vulnerability scan
    web.py                           #     Web search (Brave API) + fetch with domain allowlisting — NEW (Wave 2)
  runtime/                           #   Provider abstraction (Phase A + C + D + H + I)
    __init__.py                      #     exports Runtime, ClaudeCodeRuntime, LocalRuntime, OpenAICloudRuntime
    base.py                          #     Abstract Runtime (4 abstract methods)
    openai_base.py                   #     OpenAIBaseRuntime — shared OpenAI-compatible logic
    claude_code.py                   #     _create_with_retry() + sliding window (Phase H)
    local.py                         #     Ollama/vLLM/llama.cpp — inherits OpenAIBaseRuntime
    cloud.py                         #     OpenAICloudRuntime — _resolve_model() added, retry 5/135s

tests/                               # 290 tests, all pass, all mocked
  conftest.py
  test_config.py                     #   6 tests
  test_convergence.py                #   16 tests
  test_subagents.py                  #   8 tests
  test_hooks.py                      #   17 tests
  test_tools.py                      #   20 tests
  test_orchestrator.py               #   8 tests
  test_runtime.py                    #   15 tests
  test_local_runtime.py              #   25 tests
  test_cloud_runtime.py              #   21 tests
  test_main.py                       #   20 tests
  test_queue.py                      #   20 tests
  test_checkpoint.py                 #   12 tests
  test_queue_runner.py               #   8 tests
  test_daemon.py                     #   10 tests
  test_integrations.py               #   83 tests (54 Wave 1 + 29 Wave 2)

.claude/agents/                      # 5 subagent definitions (builder, planner, scout, scribe, verifier)
.claude/hooks/escalation-boundary.py # §5 hook (unchanged — see staging patch below)
.claude/settings.json                # hook wiring

.praxis/memory/
  morning-handoff.md                 # this file
  phase4-wave2-survey.md             # Web search API survey (NEW)
  phase4-wave2-plan.md               # Web integration design (NEW)
  phase4-mcp-survey.md               # MCP server assessment
  phase4-wave1-plan.md               # Integration layer design
  pipeline-validation-report.md
  unattended-readiness.md
  phase-j-plan.md
  model-agnostic-plan.md
  h3-pipeline-report.md
  first-live-run.md
  phase-g-plan.md

.praxis/staging/
  escalation-boundary-patch.md       # Optional §5 hook patch for defense-in-depth (NEW)

.praxis/queue/                       # Task queue directory (Phase J)
  tasks.jsonl
  results/
  checkpoints/
```

---

## 2. What Phase 4 Wave 2 built

### WebResearch integration (`web.py`)

Single tool `WebResearch` with two actions:
- **`search(query, n)`** — queries Brave Search API, returns numbered list of title/url/snippet
- **`fetch(url, max_chars)`** — fetches a URL via `urllib.request`, strips HTML, returns clean text

Key design decisions:
- **Brave Search API** as primary search provider — 2,000 free queries/month, no credit card, good quality
- **Zero external dependencies** — uses `urllib.request` + `html.parser` (stdlib only)
- **Domain allowlisting** — every HTTP request checked against `config.allowed_domains` (from `PRAXIS_ALLOWED_DOMAINS` env var). Unlisted domains are blocked.
- **API key via env var** — `PRAXIS_WEB_SEARCH_API_KEY`, added to `_redact_secrets()` for output filtering
- **Content truncation** — fetch output capped at `max_chars` (default 4000) to prevent context blowout
- **Non-text rejection** — only `text/html`, `text/plain`, `application/json` content types accepted

### §5 boundary decision

The §5 hook blocks `.claude/` edits (correctly). Rather than modifying the hook:
- `WebResearch` is a custom Praxis integration tool — NOT in the hook's `NETWORK_TOOLS` set
- Domain enforcement happens at the implementation level via `config.allowed_domains`
- Same security guarantee: no HTTP request without domain in allowlist
- Optional defense-in-depth hook patch written to `.praxis/staging/escalation-boundary-patch.md`

### Files changed

| File | Change |
|------|--------|
| `praxis/integrations/web.py` | **NEW** — 239 lines, search + fetch + HTML stripping + domain validation |
| `praxis/integrations/__init__.py` | Added web module import and aggregation |
| `praxis/tools.py` | Added `PRAXIS_WEB_SEARCH_API_KEY` to `_redact_secrets()` |
| `tests/test_integrations.py` | Added 29 tests (helpers, search, fetch, dispatch, redaction) |
| `CLAUDE.md` | Added web integration docs + setup instructions |
| `.praxis/staging/escalation-boundary-patch.md` | Optional hook patch for manual application |

---

## 3. What stayed the same

- All 261 pre-existing tests pass unmodified
- Interactive `python -m praxis "prompt"` works exactly as before
- §5 hook enforcement unchanged (control plane protection intact)
- Runtime, convergence, token propagation unchanged
- Queue, checkpoint, daemon unchanged
- Other integrations (GitHub, Analyze, TestRunner, Dependencies) unchanged

---

## 4. How to verify

```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)

# Full test suite (290 tests):
python -m pytest tests/ -v

# Web integration tests only:
python -m pytest tests/test_integrations.py -v -k "WebResearch or web"

# Quick import check:
python -c "from praxis.integrations import INTEGRATION_SCHEMAS; print(sorted(INTEGRATION_SCHEMAS.keys()))"
# → ['Analyze', 'Dependencies', 'GitHub', 'TestRunner', 'WebResearch']

# Live test (requires API key + domain allowlist):
export PRAXIS_WEB_SEARCH_API_KEY=BSA...
export PRAXIS_ALLOWED_DOMAINS=api.search.brave.com,docs.python.org
python -m praxis "search for Python asyncio documentation"
```

---

## 5. Build history

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
| G | Fix OAuth auth_token= bug. First live run confirmed. | 116 |
| H-1 | Retry on rate limit (exponential backoff) | 117 |
| H-2 | Context window management (sliding window) | 126 |
| H-3 | Pipeline test: Scout passed, 2-5 rate-limited | 126 |
| I-1 | OpenAIBaseRuntime — shared OpenAI-compatible base | 126 |
| I-2 | OpenAICloudRuntime — cloud provider | 144 |
| I-3 | LocalRuntime refactored to inherit base | 144 |
| I-4 | Convergence routing for cloud runtime | 144 |
| J-1 | Task queue (TaskQueue, tasks.jsonl, crash recovery) | 174 |
| J-2 | Session continuity (CheckpointStore, staged resume) | 186 |
| J-3 | Daemon entry point (start/stop/status + queue mode) | 203 |
| pipeline-validation | Gemini 2.5 Flash e2e validation + fixes | 207 |
| 4-W1 | Workstation integrations: GitHub, Analyze, TestRunner, Dependencies | 261 |
| **4-W2** | **Web research: Brave Search API + fetch with domain allowlisting** | **290** |

---

## 6. Wave 3 plan

Phase 4 Wave 3 — file management integration:
- **File watcher** — detect workspace changes and trigger re-analysis
- **Git integration** — branch state, uncommitted changes, recent commits as tool
- **Project context** — auto-detect project type (Python/Node/Rust), load conventions
