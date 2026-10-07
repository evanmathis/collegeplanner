"""Turn planner items into an iCalendar (.ics) file for Apple Calendar, Google, Outlook."""
from datetime import datetime, timedelta, timezone

PRODID = "-//College Planner//EN"


def escape(text):
    return (str(text or "").replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n"))


def fold(line):
    """RFC 5545: lines over 75 octets continue on the next line after a space."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts, start, limit = [], 0, 75
    while start < len(data):
        end = min(start + limit, len(data))
        while end < len(data) and (data[end] & 0xC0) == 0x80:  # don't split a UTF-8 char
            end -= 1
        parts.append(data[start:end].decode("utf-8"))
        start, limit = end, 74  # continuation lines lose one octet to the leading space
    return "\r\n ".join(parts)


def build_calendar(items, planner_url, name="College Planner"):
    """items: dicts from views.timeline_items(). Each becomes an all-day event.

    UIDs come from the record type and id, so when a date or title changes the
    calendar app updates the existing event instead of adding a second one.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{escape(name)}",
             "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
    for item in items:
        obj = item["obj"]
        school = item["school"].name if item.get("school") else ""
        summary = f"{school}: {item['title']}" if school else item["title"]
        details = [item["label"]]
        if getattr(obj, "notes", ""):
            details.append(obj.notes)
        details.append(f"Open the planner: {planner_url}")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{item['kind']}-{obj.id}@college-planner",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{item['date']:%Y%m%d}",
            f"DTEND;VALUE=DATE:{item['date'] + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{escape(summary)}",
            f"DESCRIPTION:{escape(chr(10).join(details))}",
            f"URL:{planner_url}",
            f"CATEGORIES:{escape(item['label'])}",
            "TRANSP:TRANSPARENT",
            # Reminder at 9am the day before (all-day events start at midnight).
            "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{escape(summary)}",
            "TRIGGER:-PT15H", "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
