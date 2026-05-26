# Phase 4 Wave 4 — Email & Calendar MCP/API Survey

**Date:** 2026-05-26
**Scout:** Claude

---

## 1. MCP server landscape

**Gmail MCP:** No stable, maintained MCP server exists. Anthropic's official MCP servers (`@modelcontextprotocol/server-*`) cover GitHub, memory, SQLite — not email. Community attempts exist on GitHub but are experimental, poorly maintained, and require full OAuth app registration.

**Google Calendar MCP:** Same situation. No official or stable community MCP server.

**Microsoft 365 MCP:** No unified MCP server covering both email and calendar. Microsoft Graph API exists but requires Azure AD app registration — heavy setup for a local CLI tool.

**Conclusion:** MCP adds unnecessary indirection (consistent with Phase 4 Wave 2 survey finding). Direct API via integration module is simpler, testable, and follows the established pattern.

## 2. Direct API options

| Approach | Auth complexity | Dependencies | Coverage |
|----------|----------------|--------------|----------|
| **IMAP (email read)** | App password only | `imaplib` (stdlib) | Read, search, list — universal |
| **SMTP (email send)** | App password | `smtplib` (stdlib) | Send — but we MUST NOT send autonomously |
| **iCal feed (calendar read)** | URL with embedded auth token | `urllib` (stdlib) | Read events — universal |
| **Gmail API** | OAuth2 consent screen + client ID | `google-api-python-client` | Full read/write — Google only |
| **Google Calendar API** | OAuth2 consent screen + client ID | `google-api-python-client` | Full read/write — Google only |
| **CalDAV** | Varies | `caldav` (external) | Read/write — universal |

## 3. Recommendation

**Email: IMAP via stdlib `imaplib`**
- Zero new dependencies
- Works with Gmail (app passwords), Outlook, any IMAP-compatible server
- Read and search are the only autonomous operations needed
- Drafts are composed locally and staged for human review (never sent)

**Calendar: iCal feed via stdlib `urllib`**
- Zero new dependencies
- Google Calendar, Outlook, Apple Calendar all expose private iCal feed URLs
- Read-only by nature — perfectly aligned with read-safe constraint
- Event proposals composed locally as `.ics` files for human import

**Why not Gmail/Calendar API:** Requires OAuth app registration (Google Cloud Console, consent screen, client ID, redirect URI). Excessive setup burden for a local CLI tool. The IMAP + iCal approach provides equivalent read capability with zero OAuth friction.

## 4. Auth setup burden

| Approach | User steps |
|----------|-----------|
| **IMAP + app password** | Enable 2FA → generate app password → set 3 env vars |
| **iCal feed URL** | Calendar settings → copy private iCal URL → set 1 env var |
| **OAuth2 (Google)** | Create GCP project → OAuth consent screen → client ID → download JSON → first-run auth flow |

IMAP + iCal is the path of least resistance.
