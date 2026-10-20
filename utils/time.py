from datetime import datetime, timedelta, timezone


def time_ago(value: datetime | None) -> str:
    """Format a UTC timestamp as a concise relative age."""
    if value is None:
        return "just now"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    elapsed = max(timedelta(0), datetime.now(timezone.utc) - value)
    seconds = int(elapsed.total_seconds())
    if seconds < 60:
        return "just now" if seconds < 2 else f"{seconds} seconds ago"

    minutes = seconds // 60
    if minutes < 60:
        unit, count = "minute", minutes
    else:
        hours = minutes // 60
        if hours < 24:
            unit, count = "hour", hours
        else:
            days = hours // 24
            if days < 30:
                unit, count = "day", days
            elif days < 365:
                unit, count = "month", max(1, days // 30)
            else:
                unit, count = "year", max(1, days // 365)

    suffix = "" if count == 1 else "s"
    return f"{count} {unit}{suffix} ago"
