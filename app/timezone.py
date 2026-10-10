from datetime import datetime, timedelta, timezone


NEPAL_TIMEZONE = timezone(timedelta(hours=5, minutes=45), name="NPT")


def to_nepal_time(value: datetime) -> datetime:
    """Treat naive database timestamps as UTC and convert them to Nepal time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(NEPAL_TIMEZONE)
