from datetime import date, timedelta

import pytest

from app.dates import check_range, parse_iso, split_sources
from app.errors import AppError


def test_parse_iso_bad():
    with pytest.raises(AppError):
        parse_iso("03-14-2024", "start_date")


def test_range_backwards():
    with pytest.raises(AppError):
        check_range(date(2024, 6, 10), date(2024, 6, 1))


def test_range_ok():
    assert check_range(date(2024, 1, 1), date(2024, 1, 8)) == 8


def test_split_puts_old_days_in_archive():
    start = date.today() - timedelta(days=40)
    end = date.today() - timedelta(days=20)
    hist, fc = split_sources(start, end)
    assert hist is not None
    assert fc is None
