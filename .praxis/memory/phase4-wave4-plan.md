# Phase 4 Wave 4 — Email & Calendar Integration Plan

**Date:** 2026-05-26
**Planner:** Claude
**Survey:** phase4-wave4-survey.md

---

## 1. Architecture decision

**No MCP servers.** Direct integration modules following the established pattern in `praxis/integrations/`. IMAP for email (stdlib), iCal feeds for calendar (stdlib). Zero new dependencies.

## 2. Read-safe / write-escalate rule

This is the non-negotiable constraint from §5:

| Operation | Safety | Implementation |
|-----------|--------|---------------|
| `list_emails` | Read-safe | IMAP FETCH headers, readonly=True |
| `search_emails` | Read-safe | IMAP SEARCH, readonly=True |
| `read_email` | Read-safe | IMAP FETCH body, readonly=True |
| `draft_email` | Write-escalate | Compose locally → save to `.praxis/staging/drafts/*.eml` |
| `list_events` | Read-safe | Fetch iCal feed, parse, filter |
| `today` | Read-safe | Fetch iCal feed, filter to today |
| `check_availability` | Read-safe | Fetch iCal feed, check overlap |
| `propose_event` | Write-escalate | Compose locally → save to `.praxis/staging/events/*.ics` |

**Key design:** There is no `send_email` or `create_event` action. The tool literally cannot send or create — it stages locally for human review. The escalation is baked into the API surface, not enforced by a runtime check.

## 3. Credential handling (§5.8)

| Env var | Purpose | Redacted |
|---------|---------|----------|
| `PRAXIS_EMAIL_IMAP_HOST` | IMAP server hostname | No (not secret) |
| `PRAXIS_EMAIL_USER` | Email address | No (not secret) |
| `PRAXIS_EMAIL_PASSWORD` | App password | **Yes** — added to `_redact_secrets()` |
| `PRAXIS_CALENDAR_URL` | iCal feed URL (contains embedded auth) | **Yes** — added to `_redact_secrets()` |

## 4. File plan

### New files
- `praxis/integrations/email.py` — ~200 lines
- `praxis/integrations/calendar.py` — ~220 lines

### Modified files
- `praxis/integrations/__init__.py` — add email + calendar imports
- `praxis/tools.py` — add `PRAXIS_EMAIL_PASSWORD` + `PRAXIS_CALENDAR_URL` to `_redact_secrets()`
- `tests/test_integrations.py` — ~42 new tests (all mocked)
- `CLAUDE.md` — document new integrations + read-safe/write-escalate pattern

## 5. Email integration design (`email.py`)

Uses `imaplib` (stdlib) + `email` (stdlib) for parsing.

**Connection:** `_connect_imap()` → `IMAP4_SSL` with env var credentials. Returns `(connection, error)` tuple. SSL by default (port 993).

**Actions:**
- `list_emails(folder="INBOX", n=10)` — select folder readonly, search ALL, fetch last N headers
- `search_emails(query, folder="INBOX")` — IMAP SEARCH with smart syntax (bare string → SUBJECT/FROM search, raw IMAP syntax passed through)
- `read_email(message_id)` — fetch full message, extract text body (multipart-aware), truncate to 4000 chars
- `draft_email(to, subject, body)` — compose `.eml` file, save to staging dir

**Output:** All output passes through `_redact_secrets()`.

## 6. Calendar integration design (`calendar.py`)

Uses `urllib.request` for feed fetch, custom `_parse_ical()` for parsing.

**iCal parsing:** Minimal parser handles VEVENT blocks — extracts SUMMARY, DTSTART, DTEND, LOCATION, DESCRIPTION. Handles UTC (Z suffix), local time, all-day (VALUE=DATE), and TZID parameters.

**Domain enforcement:** Calendar feed URL domain checked against `config.allowed_domains` — consistent with WebResearch pattern.

**Actions:**
- `list_events(days=7)` — fetch feed, filter to next N days, display sorted
- `today()` — fetch feed, filter to today only
- `check_availability(date, start_time, end_time)` — fetch feed, check for overlapping events
- `propose_event(title, date, start_time, end_time, description?)` — compose `.ics` file, save to staging dir

## 7. Escalation boundary impact

No changes needed to `escalation-boundary.py`:
- IMAP uses Python's `imaplib` (direct socket), not Bash network commands
- Calendar uses `urllib.request`, same as existing WebResearch
- Neither tool has send/create actions — escalation is structural

## 8. Test strategy

All tests mocked — no real IMAP connections or HTTP requests.
- IMAP: mock `imaplib.IMAP4_SSL` class
- Calendar HTTP: mock `urllib.request.urlopen` (same pattern as WebResearch tests)
- Draft/propose: use `tmp_path` fixture, verify file contents
- Credential errors: test all missing env var paths
- Secret redaction: verify passwords never appear in output
