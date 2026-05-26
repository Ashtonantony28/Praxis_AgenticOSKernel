# Morning handoff — Phase 4 Wave 4 complete

**Date:** 2026-05-26  
**Status:** Phase 4 Wave 4 (email and calendar integration) complete. 388 tests pass.

---

## 1. Exact repo state

**Repo:** `Ashtonantony28/Praxis_AgenticOSKernel`  
**Branch:** `claude/blissful-franklin-VIMiH`  
**Main branch:** `claude/plan-execute-mode-switch-zCz38`

```
praxis-system-prompt.md              # the spec (§0–§11)
CLAUDE.md                            # project conventions — updated Phase 4 Wave 4
pyproject.toml                       # deps: anthropic, pyyaml, openai[local], pytest

praxis/                              # the orchestrator
  __init__.py                        #   package marker, version
  __main__.py                        #   `python -m praxis` — interactive, --queue, --daemon, --stop, --status
  config.py                          #   Config.from_env() — workspace/memory/hook/allowed_domains from env
  convergence.py                     #   ConvergenceConfig.load() — multi-runtime routing (Phase D+I)
  subagents.py                       #   parse .claude/agents/*.md → SubagentDef
  hooks.py                           #   run_pretool_hook() — §5 enforcement
  tools.py                           #   7 tool schemas + implementations + secret filtering (Phase E, +email/calendar secrets)
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
    web.py                           #     Web search (Brave API) + fetch with domain allowlisting (Wave 2)
    files.py                         #     File management — search, summarize, git_status, disk_usage (Wave 3)
    email.py                         #     Email — IMAP read + local draft staging (Wave 4) — NEW
    calendar.py                      #     Calendar — iCal feed read + event proposal staging (Wave 4) — NEW
  runtime/                           #   Provider abstraction (Phase A + C + D + H + I)
    __init__.py                      #     exports Runtime, ClaudeCodeRuntime, LocalRuntime, OpenAICloudRuntime
    base.py                          #     Abstract Runtime (4 abstract methods)
    openai_base.py                   #     OpenAIBaseRuntime — shared OpenAI-compatible logic
    claude_code.py                   #     _create_with_retry() + sliding window (Phase H)
    local.py                         #     Ollama/vLLM/llama.cpp — inherits OpenAIBaseRuntime
    cloud.py                         #     OpenAICloudRuntime — _resolve_model() added, retry 5/135s

tests/                               # 388 tests, all pass, all mocked
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
  test_integrations.py               #   182 tests (54 Wave 1 + 29 Wave 2 + 36 Wave 3 + 63 Wave 4)

.claude/agents/                      # 5 subagent definitions (builder, planner, scout, scribe, verifier)
.claude/hooks/escalation-boundary.py # §5 hook (unchanged)
.claude/settings.json                # hook wiring

.praxis/memory/
  morning-handoff.md                 # this file
  phase4-wave4-survey.md             # MCP/API survey — no stable MCP, IMAP+iCal chosen (NEW)
  phase4-wave4-plan.md               # Read-safe/write-escalate design (NEW)
  phase4-wave3-plan.md               # File management scope decision
  phase4-wave2-survey.md             # Web search API survey
  phase4-wave2-plan.md               # Web integration design
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
  escalation-boundary-patch.md       # Optional §5 hook patch for defense-in-depth
  drafts/                            # Email drafts staged for human review (NEW)
  events/                            # Calendar event proposals staged for human review (NEW)

.praxis/queue/                       # Task queue directory (Phase J)
  tasks.jsonl
  results/
  checkpoints/
```

---

## 2. What Phase 4 Wave 4 built

### Email integration (`email.py`)

Single tool `Email` with four actions, following the **read-safe / write-escalate** pattern:

- **`list_emails(folder?, n?)`** — IMAP FETCH headers, readonly=True. Lists recent N emails (default 10, max 50). Newest first.
- **`search_emails(query, folder?)`** — IMAP SEARCH. Bare text searches subject+sender; raw IMAP syntax (SINCE, FROM, UNSEEN, etc.) passes through unchanged.
- **`read_email(message_id)`** — IMAP FETCH full message. Multipart-aware: prefers text/plain, notes text/html. Body truncated to 4000 chars.
- **`draft_email(to, subject, body)`** — Composes `.eml` file, saves to `.praxis/staging/drafts/`. **NEVER sends.** User reviews and sends from their email client.

Key design decisions:
- **IMAP via stdlib** — `imaplib` + `email` modules. Zero external dependencies. Works with Gmail (app passwords), Outlook, any IMAP-compatible server.
- **App passwords** — `PRAXIS_EMAIL_PASSWORD` is an app-specific password, not the account password. Setup guidance in error messages.
- **Credential protection** — `PRAXIS_EMAIL_PASSWORD` added to `_redact_secrets()`. Password never appears in tool output.
- **No send action** — The tool API has no `send_email` action. Escalation is structural, not a runtime check.

### Calendar integration (`calendar.py`)

Single tool `Calendar` with four actions, same read-safe / write-escalate pattern:

- **`list_events(days?)`** — Fetches iCal feed, filters to next N days (default 7, max 30). Shows time, title, location.
- **`today()`** — Today's agenda — events filtered to current date.
- **`check_availability(date, start_time, end_time)`** — Overlap check against calendar events. Reports conflicts.
- **`propose_event(title, date, start_time, end_time, description?)`** — Composes `.ics` file, saves to `.praxis/staging/events/`. **NEVER creates events.** User imports into their calendar manually.

Key design decisions:
- **iCal feed via stdlib** — `urllib.request` for fetch, custom `_parse_ical()` for parsing. Zero external dependencies. Works with Google Calendar, Outlook, Apple Calendar — any provider exposing iCal feeds.
- **Domain enforcement** — Feed URL domain checked against `PRAXIS_ALLOWED_DOMAINS`, consistent with WebResearch pattern.
- **Private feed URL** — `PRAXIS_CALENDAR_URL` contains an embedded auth token (e.g., Google's "Secret address in iCal format"). URL added to `_redact_secrets()`.
- **No create action** — The tool API has no `create_event` action. Escalation is structural.
- **iCal datetime handling** — Supports UTC (`Z` suffix), local time, all-day (`VALUE=DATE`), and timezone parameters (`TZID=...`).

### Read-safe / write-escalate rule

| Operation | Safety | Implementation |
|-----------|--------|---------------|
| list_emails, search_emails, read_email | Read-safe | IMAP readonly=True |
| list_events, today, check_availability | Read-safe | HTTP GET + parse |
| draft_email | Write-escalate | Local file → `.praxis/staging/drafts/` |
| propose_event | Write-escalate | Local file → `.praxis/staging/events/` |

No changes to `escalation-boundary.py` — the escalation is baked into the API surface. There is no code path that sends email or creates calendar events.

### Files changed

| File | Change |
|------|--------|
| `praxis/integrations/email.py` | **NEW** — ~250 lines, IMAP read + draft staging |
| `praxis/integrations/calendar.py` | **NEW** — ~270 lines, iCal feed + event proposal |
| `praxis/integrations/__init__.py` | Added email + calendar imports and aggregation |
| `praxis/tools.py` | Added `PRAXIS_EMAIL_PASSWORD` + `PRAXIS_CALENDAR_URL` to `_redact_secrets()` |
| `tests/test_integrations.py` | Added 62 tests (email: 31, calendar: 31) |
| `CLAUDE.md` | Added Email + Calendar docs, read-safe/write-escalate pattern, updated test count |

---

## 3. What stayed the same

- All 326 pre-existing tests pass unmodified
- Interactive `python -m praxis "prompt"` works exactly as before
- §5 hook enforcement unchanged (control plane protection intact)
- Runtime, convergence, token propagation unchanged
- Queue, checkpoint, daemon unchanged
- Other integrations (GitHub, Analyze, TestRunner, Dependencies, WebResearch, FileManager) unchanged

---

## 4. How to verify

```bash
export PRAXIS_WORKSPACE_ROOT=$(pwd)

# Full test suite (388 tests):
python -m pytest tests/ -v

# Email tests only:
python -m pytest tests/test_integrations.py -v -k "Email"

# Calendar tests only:
python -m pytest tests/test_integrations.py -v -k "Calendar"

# Quick import check:
python -c "from praxis.integrations import INTEGRATION_SCHEMAS; print(sorted(INTEGRATION_SCHEMAS.keys()))"
# → ['Analyze', 'Calendar', 'Dependencies', 'Email', 'FileManager', 'GitHub', 'TestRunner', 'WebResearch']
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
| 4-W2 | Web research: Brave Search API + fetch with domain allowlisting | 290 |
| 4-W3 | File management: search, summarize, git_status, disk_usage | 326 |
| **4-W4** | **Email + Calendar: IMAP read, iCal feed, draft/propose staging** | **388** |

---

## 6. What's next

Phase 4 complete. All eight workstation integrations are built:
- GitHub, Analyze, TestRunner, Dependencies (Wave 1)
- WebResearch (Wave 2)
- FileManager (Wave 3)
- Email, Calendar (Wave 4)

Next milestone: open-source preparation — documentation, packaging, CI setup.
