"""Calendar integration — iCal feed read + local event proposal staging.

Read operations (list, today, availability) are autonomous.
Propose operation stages locally for human review — NEVER creates events.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Callable

from ..config import Config
from ..tools import _redact_secrets

SCHEMAS: dict[str, dict[str, Any]] = {
    "Calendar": {
        "name": "Calendar",
        "description": (
            "Calendar integration for reading events and checking availability. "
            "Read operations are autonomous; event proposals are staged for "
            "human review (never created automatically). "
            "Actions: list_events, today, check_availability, propose_event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "list_events",
                        "today",
                        "check_availability",
                        "propose_event",
                    ],
                    "description": "The calendar operation to perform",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days ahead to list events (default: 7, max: 30)",
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format",
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in HH:MM format",
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in HH:MM format",
                },
                "title": {
                    "type": "string",
                    "description": "Event title for propose_event",
                },
                "description": {
                    "type": "string",
                    "description": "Event description for propose_event (optional)",
                },
            },
            "required": ["action"],
        },
    },
}


# ---------- iCal parsing ----------


class _ICalEvent:
    """Minimal parsed iCal VEVENT."""

    __slots__ = ("summary", "dtstart", "dtend", "location", "description")

    def __init__(self) -> None:
        self.summary: str = ""
        self.dtstart: datetime | None = None
        self.dtend: datetime | None = None
        self.location: str = ""
        self.description: str = ""


def _parse_ical_datetime(value: str) -> datetime | None:
    """Parse an iCal datetime value (DTSTART/DTEND).

    Handles: 20260525T100000Z (UTC), 20260525T100000 (local),
    20260525 (all-day), and ;TZID=...:20260525T100000 (with tz param).
    """
    clean = value.strip()

    # Strip VALUE=DATE parameter
    if "VALUE=DATE:" in clean:
        clean = clean.split("VALUE=DATE:")[-1].strip()
    elif ":" in clean:
        clean = clean.split(":")[-1].strip()

    for fmt in (
        "%Y%m%dT%H%M%SZ",
        "%Y%m%dT%H%M%S",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def _parse_ical(text: str) -> list[_ICalEvent]:
    """Parse iCal text into a sorted list of events."""
    events: list[_ICalEvent] = []
    current: _ICalEvent | None = None

    for line in text.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT":
            current = _ICalEvent()
        elif line == "END:VEVENT":
            if current and current.dtstart:
                events.append(current)
            current = None
        elif current is not None:
            if line.startswith("SUMMARY:"):
                current.summary = line[8:]
            elif line.startswith("SUMMARY;"):
                current.summary = line.split(":", 1)[-1] if ":" in line else ""
            elif line.split(":")[0].split(";")[0] == "DTSTART":
                current.dtstart = _parse_ical_datetime(line)
            elif line.split(":")[0].split(";")[0] == "DTEND":
                current.dtend = _parse_ical_datetime(line)
            elif line.startswith("LOCATION:"):
                current.location = line[9:]
            elif line.startswith("DESCRIPTION:"):
                current.description = line[12:]

    return sorted(events, key=lambda e: e.dtstart or datetime.min)


# ---------- Feed fetching ----------


def _fetch_calendar(config: Config) -> tuple[list[_ICalEvent] | None, str | None]:
    """Fetch and parse the iCal feed.

    Returns (events, error). If error is not None, events is None.
    """
    url = os.environ.get("PRAXIS_CALENDAR_URL", "")
    if not url:
        return None, (
            "Error: PRAXIS_CALENDAR_URL not set. "
            "Set it to your calendar's iCal feed URL. "
            "For Google Calendar: Settings > calendar > "
            "Secret address in iCal format."
        )

    if not url.startswith(("http://", "https://")):
        return None, "Error: PRAXIS_CALENDAR_URL must start with http:// or https://"

    # Domain check — consistent with WebResearch pattern
    parsed = urllib.parse.urlparse(url)
    domain = parsed.hostname or ""
    if domain and domain not in config.allowed_domains:
        return None, (
            f"Error: calendar domain '{domain}' not in PRAXIS_ALLOWED_DOMAINS. "
            f"Add it to allow calendar feed access."
        )

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Praxis/1.0 (calendar agent)")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return None, f"Error: calendar feed returned HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"Error: could not fetch calendar feed: {exc.reason}"
    except TimeoutError:
        return None, "Error: calendar feed timed out after 15s"

    return _parse_ical(raw), None


# ---------- List events ----------


def _list_events(days: int, config: Config) -> str:
    """List events for the next N days."""
    events, err = _fetch_calendar(config)
    if err:
        return err

    days = max(1, min(days, 30))
    now = datetime.now()
    cutoff = now + timedelta(days=days)

    upcoming = [e for e in events if e.dtstart and now <= e.dtstart <= cutoff]

    if not upcoming:
        return f"No events in the next {days} day(s)"

    lines = [f"Events for the next {days} day(s) ({len(upcoming)} total):\n"]
    for e in upcoming:
        start = e.dtstart.strftime("%Y-%m-%d %H:%M") if e.dtstart else "?"
        end = e.dtend.strftime("%H:%M") if e.dtend else "?"
        line = f"  {start} - {end}  {e.summary}"
        if e.location:
            line += f"  @ {e.location}"
        lines.append(line)

    return _redact_secrets("\n".join(lines))


# ---------- Today ----------


def _today(config: Config) -> str:
    """Show today's agenda."""
    events, err = _fetch_calendar(config)
    if err:
        return err

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    todays = [e for e in events if e.dtstart and today_start <= e.dtstart < today_end]

    if not todays:
        return f"No events today ({now.strftime('%A, %B %d, %Y')})"

    lines = [
        f"Today's agenda ({now.strftime('%A, %B %d, %Y')}) "
        f"-- {len(todays)} event(s):\n"
    ]
    for e in todays:
        start = e.dtstart.strftime("%H:%M") if e.dtstart else "?"
        end = e.dtend.strftime("%H:%M") if e.dtend else "?"
        line = f"  {start} - {end}  {e.summary}"
        if e.location:
            line += f"  @ {e.location}"
        lines.append(line)

    return _redact_secrets("\n".join(lines))


# ---------- Check availability ----------


def _check_availability(
    date_str: str, start_time: str, end_time: str, config: Config
) -> str:
    """Check if a time slot is free."""
    events, err = _fetch_calendar(config)
    if err:
        return err

    try:
        slot_start = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
        slot_end = datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "Error: use date format YYYY-MM-DD and time format HH:MM"

    if slot_end <= slot_start:
        return "Error: end_time must be after start_time"

    conflicts = []
    for e in events:
        if not e.dtstart or not e.dtend:
            continue
        # Overlap: event starts before slot ends AND event ends after slot starts
        if e.dtstart < slot_end and e.dtend > slot_start:
            conflicts.append(e)

    if not conflicts:
        return f"Available: {date_str} {start_time}-{end_time} is free"

    lines = [
        f"Conflict: {date_str} {start_time}-{end_time} "
        f"overlaps with {len(conflicts)} event(s):\n"
    ]
    for e in conflicts:
        start = e.dtstart.strftime("%H:%M") if e.dtstart else "?"
        end = e.dtend.strftime("%H:%M") if e.dtend else "?"
        lines.append(f"  {start}-{end}  {e.summary}")

    return _redact_secrets("\n".join(lines))


# ---------- Propose event ----------


def _propose_event(
    title: str,
    date_str: str,
    start_time: str,
    end_time: str,
    description: str,
    config: Config,
) -> str:
    """Compose an event proposal and save to staging directory for human review.

    NEVER creates calendar events autonomously. Proposals are staged locally.
    """
    staging_dir = config.workspace_root / ".praxis" / "staging" / "events"
    staging_dir.mkdir(parents=True, exist_ok=True)

    try:
        dt_start = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
        dt_end = datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "Error: use date format YYYY-MM-DD and time format HH:MM"

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_title = "".join(
        c if c.isalnum() or c in " -_" else "" for c in title
    )[:50].strip()
    filename = f"{timestamp}_{safe_title}.ics"
    proposal_path = staging_dir / filename

    ical = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Praxis//Calendar//EN\n"
        "BEGIN:VEVENT\n"
        f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}\n"
        f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}\n"
        f"SUMMARY:{title}\n"
    )
    if description:
        ical += f"DESCRIPTION:{description}\n"
    ical += "END:VEVENT\nEND:VCALENDAR\n"

    proposal_path.write_text(ical, encoding="utf-8")

    rel_path = proposal_path.relative_to(config.workspace_root)
    result = (
        f"Event proposal saved to {rel_path}\n\n"
        f"Title: {title}\n"
        f"Date: {date_str}\n"
        f"Time: {start_time} - {end_time}\n"
    )
    if description:
        result += f"Description: {description}\n"
    result += (
        "\nWARNING: This event has NOT been created. "
        "Review and import the .ics file into your calendar manually."
    )
    return _redact_secrets(result)


# ---------- Dispatch ----------


def execute_calendar(args: dict[str, Any], config: Config) -> str:
    action = args.get("action", "")

    if action == "list_events":
        days = args.get("days", 7)
        return _list_events(days, config)

    elif action == "today":
        return _today(config)

    elif action == "check_availability":
        date_str = args.get("date", "")
        start_time = args.get("start_time", "")
        end_time = args.get("end_time", "")
        if not all([date_str, start_time, end_time]):
            return (
                "Error: 'date', 'start_time', and 'end_time' are required "
                "for check_availability"
            )
        return _check_availability(date_str, start_time, end_time, config)

    elif action == "propose_event":
        title = args.get("title", "")
        date_str = args.get("date", "")
        start_time = args.get("start_time", "")
        end_time = args.get("end_time", "")
        if not all([title, date_str, start_time, end_time]):
            return (
                "Error: 'title', 'date', 'start_time', and 'end_time' "
                "are required for propose_event"
            )
        description = args.get("description", "")
        return _propose_event(title, date_str, start_time, end_time, description, config)

    else:
        return f"Error: unknown Calendar action '{action}'"


IMPLEMENTATIONS: dict[str, Callable[[dict[str, Any], Config], str]] = {
    "Calendar": execute_calendar,
}
