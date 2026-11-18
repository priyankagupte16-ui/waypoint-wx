from datetime import date, timedelta

from app.errors import AppError
from app.settings import settings

ARCHIVE_LAG = 5
EARLIEST = date(1940, 1, 1)


def parse_iso(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AppError(422, f"{field} must be YYYY-MM-DD")


def check_range(start: date, end: date):
    if start > end:
        raise AppError(422, "start_date has to be on or before end_date")
    span = (end - start).days + 1
    if span > settings.max_range_days:
        raise AppError(422, f"date range is too long (max {settings.max_range_days} days)")
    if start < EARLIEST:
        raise AppError(422, "archive data only goes back to 1940")
    cap = date.today() + timedelta(days=settings.forecast_horizon_days)
    if end > cap:
        raise AppError(
            422,
            f"end_date cannot be more than {settings.forecast_horizon_days} days from today",
        )
    return span


def split_sources(start: date, end: date):
    archive_cut = date.today() - timedelta(days=ARCHIVE_LAG)
    hist = None
    fc = None
    if start <= archive_cut:
        hist = (start, min(end, archive_cut))
    if end > archive_cut:
        fc = (max(start, archive_cut + timedelta(days=1)), end)
    return hist, fc
