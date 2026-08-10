from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _stamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def events_to_ics(events: Iterable[dict[str, object]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HealthVault Local//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    now = _stamp(datetime.now(timezone.utc))
    for event in events:
        starts_at = event["starts_at"]
        assert isinstance(starts_at, datetime)
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{event['id']}@healthvault.local",
            f"DTSTAMP:{now}",
            f"DTSTART:{_stamp(starts_at)}",
            f"SUMMARY:{_escape(str(event.get('title') or 'Health reminder'))}",
            f"DESCRIPTION:{_escape(str(event.get('description') or 'Created from HealthVault Local. Verify medical information.'))}",
        ])
        if event.get("location"):
            lines.append(f"LOCATION:{_escape(str(event['location']))}")
        lines.extend(["END:VEVENT"])
    lines.extend(["END:VCALENDAR", ""])
    return "\r\n".join(lines)
