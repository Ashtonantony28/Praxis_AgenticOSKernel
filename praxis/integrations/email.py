"""Email integration — IMAP inbox read + local draft staging.

Read operations (list, search, read) are autonomous.
Draft operation stages locally for human review — NEVER sends email.
"""

from __future__ import annotations

import email as email_mod
import email.utils
import imaplib
import os
import ssl
from datetime import datetime
from typing import Any, Callable

from ..config import Config
from ..tools import _redact_secrets

SCHEMAS: dict[str, dict[str, Any]] = {
    "Email": {
        "name": "Email",
        "description": (
            "Email integration for reading and searching inbox. "
            "Read operations are autonomous; drafts are staged for human review "
            "(never sent automatically). "
            "Actions: list_emails, search_emails, read_email, draft_email."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "list_emails",
                        "search_emails",
                        "read_email",
                        "draft_email",
                    ],
                    "description": "The email operation to perform",
                },
                "folder": {
                    "type": "string",
                    "description": "IMAP folder (default: INBOX)",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of emails to list (default: 10, max: 50)",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Search query for search_emails — plain text searches "
                        "subject and sender, or use raw IMAP syntax "
                        "(e.g., SINCE 01-Jan-2026)"
                    ),
                },
                "message_id": {
                    "type": "string",
                    "description": "Message sequence number for read_email",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient for draft_email",
                },
                "subject": {
                    "type": "string",
                    "description": "Subject for draft_email",
                },
                "body": {
                    "type": "string",
                    "description": "Body text for draft_email",
                },
            },
            "required": ["action"],
        },
    },
}


# ---------- IMAP connection ----------


def _connect_imap(config: Config) -> tuple[imaplib.IMAP4_SSL | None, str | None]:
    """Connect to IMAP server using env var credentials.

    Returns (connection, error). If error is not None, connection is None.
    """
    host = os.environ.get("PRAXIS_EMAIL_IMAP_HOST", "")
    user = os.environ.get("PRAXIS_EMAIL_USER", "")
    password = os.environ.get("PRAXIS_EMAIL_PASSWORD", "")

    if not host:
        return None, (
            "Error: PRAXIS_EMAIL_IMAP_HOST not set. "
            "Set it to your IMAP server (e.g., imap.gmail.com for Gmail, "
            "outlook.office365.com for Outlook)."
        )
    if not user:
        return None, "Error: PRAXIS_EMAIL_USER not set."
    if not password:
        return None, (
            "Error: PRAXIS_EMAIL_PASSWORD not set. "
            "Use an app password (not your account password). "
            "For Gmail: myaccount.google.com > Security > App passwords."
        )

    try:
        ctx = ssl.create_default_context()
        conn = imaplib.IMAP4_SSL(host, port=993, ssl_context=ctx)
        conn.login(user, password)
        return conn, None
    except imaplib.IMAP4.error as exc:
        return None, f"Error: IMAP authentication failed: {exc}"
    except (OSError, TimeoutError) as exc:
        return None, f"Error: could not connect to {host}: {exc}"


# ---------- Email parsing ----------


def _parse_headers(raw: bytes) -> dict[str, str]:
    """Parse raw email bytes into a header dict."""
    msg = email_mod.message_from_bytes(raw)
    date_str = msg.get("Date", "")
    try:
        parsed_date = email.utils.parsedate_to_datetime(date_str) if date_str else None
    except (ValueError, TypeError):
        parsed_date = None
    return {
        "from": msg.get("From", "(unknown)"),
        "to": msg.get("To", "(unknown)"),
        "subject": msg.get("Subject", "(no subject)"),
        "date": parsed_date.isoformat() if parsed_date else date_str,
    }


def _extract_body(raw: bytes) -> str:
    """Extract plain text body from raw email."""
    msg = email_mod.message_from_bytes(raw)
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        # Fallback: note HTML presence
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return f"[HTML content, {len(payload)} bytes]"
        return "[No text content found]"

    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode("utf-8", errors="replace")
    return "[Empty message]"


# ---------- List ----------


def _list_emails(folder: str, n: int, config: Config) -> str:
    """List recent emails from a folder."""
    conn, err = _connect_imap(config)
    if err:
        return err

    try:
        n = max(1, min(n, 50))
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            return f"Error: could not open folder '{folder}'"

        status, data = conn.search(None, "ALL")
        if status != "OK":
            return "Error: IMAP search failed"

        ids = data[0].split()
        if not ids:
            return f"No emails in {folder}"

        # Get last n emails (newest first)
        recent = ids[-n:]
        recent.reverse()

        lines: list[str] = []
        for mid in recent:
            status, msg_data = conn.fetch(mid, "(RFC822.HEADER)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else b""
            hdrs = _parse_headers(raw)
            lines.append(
                f"[{mid.decode()}] {hdrs['date']}  "
                f"From: {hdrs['from']}  "
                f"Subject: {hdrs['subject']}"
            )

        result = f"Folder: {folder} ({len(ids)} total)\n\n" + "\n".join(lines)
        return _redact_secrets(result)
    finally:
        try:
            conn.logout()
        except Exception:
            pass


# ---------- Search ----------


def _search_emails(query: str, folder: str, config: Config) -> str:
    """Search emails using IMAP search."""
    conn, err = _connect_imap(config)
    if err:
        return err

    try:
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            return f"Error: could not open folder '{folder}'"

        # Smart syntax: raw IMAP keywords pass through, bare text
        # searches subject and sender
        imap_keywords = (
            "FROM", "TO", "SUBJECT", "BODY", "OR", "NOT",
            "SINCE", "BEFORE", "ON", "SEEN", "UNSEEN",
            "FLAGGED", "UNFLAGGED", "ALL",
        )
        if query.split()[0].upper() in imap_keywords:
            search_criteria = query
        else:
            search_criteria = f'(OR (SUBJECT "{query}") (FROM "{query}"))'

        status, data = conn.search(None, search_criteria)
        if status != "OK":
            return f"Error: IMAP search failed for: {query}"

        ids = data[0].split()
        if not ids:
            return f"No emails matching: {query}"

        # Return up to 20 results, newest first
        results = ids[-20:]
        results.reverse()

        lines = [f"Found {len(ids)} email(s) matching: {query}\n"]
        for mid in results:
            status, msg_data = conn.fetch(mid, "(RFC822.HEADER)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else b""
            hdrs = _parse_headers(raw)
            lines.append(
                f"[{mid.decode()}] {hdrs['date']}  "
                f"From: {hdrs['from']}  "
                f"Subject: {hdrs['subject']}"
            )

        if len(ids) > 20:
            lines.append(f"\n... ({len(ids) - 20} more results)")

        return _redact_secrets("\n".join(lines))
    finally:
        try:
            conn.logout()
        except Exception:
            pass


# ---------- Read ----------


def _read_email(message_id: str, config: Config) -> str:
    """Read a specific email by sequence number."""
    conn, err = _connect_imap(config)
    if err:
        return err

    try:
        conn.select("INBOX", readonly=True)
        status, msg_data = conn.fetch(message_id.encode(), "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            return f"Error: could not fetch message {message_id}"

        raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else b""
        hdrs = _parse_headers(raw)
        body = _extract_body(raw)

        # Truncate long bodies
        if len(body) > 4000:
            body = body[:4000] + f"\n\n... ({len(body) - 4000} more characters)"

        result = (
            f"From: {hdrs['from']}\n"
            f"To: {hdrs['to']}\n"
            f"Subject: {hdrs['subject']}\n"
            f"Date: {hdrs['date']}\n"
            f"\n{body}"
        )
        return _redact_secrets(result)
    finally:
        try:
            conn.logout()
        except Exception:
            pass


# ---------- Draft ----------


def _draft_email(to: str, subject: str, body: str, config: Config) -> str:
    """Compose a draft email and save to staging directory for human review.

    NEVER sends email autonomously. Drafts are staged locally.
    """
    staging_dir = config.workspace_root / ".praxis" / "staging" / "drafts"
    staging_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_subj = "".join(
        c if c.isalnum() or c in " -_" else "" for c in subject
    )[:50].strip()
    filename = f"{timestamp}_{safe_subj}.eml"
    draft_path = staging_dir / filename

    from_addr = os.environ.get("PRAXIS_EMAIL_USER", "user@example.com")

    draft_content = (
        f"From: {from_addr}\n"
        f"To: {to}\n"
        f"Subject: {subject}\n"
        f"Date: {datetime.now().isoformat()}\n"
        f"\n"
        f"{body}\n"
    )

    draft_path.write_text(draft_content, encoding="utf-8")

    rel_path = draft_path.relative_to(config.workspace_root)
    return _redact_secrets(
        f"Draft saved to {rel_path}\n\n"
        f"To: {to}\n"
        f"Subject: {subject}\n"
        f"Body preview: {body[:200]}\n\n"
        f"WARNING: This draft has NOT been sent. "
        f"Review and send manually from your email client."
    )


# ---------- Dispatch ----------


def execute_email(args: dict[str, Any], config: Config) -> str:
    action = args.get("action", "")

    if action == "list_emails":
        folder = args.get("folder", "INBOX")
        n = args.get("n", 10)
        return _list_emails(folder, n, config)

    elif action == "search_emails":
        query = args.get("query", "")
        if not query:
            return "Error: 'query' is required for search_emails action"
        folder = args.get("folder", "INBOX")
        return _search_emails(query, folder, config)

    elif action == "read_email":
        message_id = args.get("message_id", "")
        if not message_id:
            return "Error: 'message_id' is required for read_email action"
        return _read_email(message_id, config)

    elif action == "draft_email":
        to = args.get("to", "")
        subject = args.get("subject", "")
        body = args.get("body", "")
        if not to:
            return "Error: 'to' is required for draft_email action"
        if not subject:
            return "Error: 'subject' is required for draft_email action"
        if not body:
            return "Error: 'body' is required for draft_email action"
        return _draft_email(to, subject, body, config)

    else:
        return f"Error: unknown Email action '{action}'"


IMPLEMENTATIONS: dict[str, Callable[[dict[str, Any], Config], str]] = {
    "Email": execute_email,
}
