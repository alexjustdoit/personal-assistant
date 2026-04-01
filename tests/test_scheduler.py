"""Tests for reminder recurrence logic (_next_occurrence)."""
import sys
import os
from unittest.mock import MagicMock
from datetime import datetime, timedelta

# Stub out heavy deps before importing the module
sys.modules.setdefault('apscheduler', MagicMock())
sys.modules.setdefault('apscheduler.schedulers', MagicMock())
sys.modules.setdefault('apscheduler.schedulers.asyncio', MagicMock())
sys.modules.setdefault('apscheduler.triggers', MagicMock())
sys.modules.setdefault('apscheduler.triggers.cron', MagicMock())
sys.modules.setdefault('apscheduler.triggers.interval', MagicMock())
sys.modules.setdefault('pytz', MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.services.scheduler import _next_occurrence


def test_daily_advances_one_day():
    due = datetime(2026, 4, 1, 9, 0, 0).isoformat()
    assert _next_occurrence(due, "daily") == datetime(2026, 4, 2, 9, 0, 0).isoformat()


def test_weekly_advances_seven_days():
    due = datetime(2026, 4, 1, 9, 0, 0).isoformat()
    assert _next_occurrence(due, "weekly") == datetime(2026, 4, 8, 9, 0, 0).isoformat()


def test_weekdays_skips_weekend_from_friday():
    # April 3 2026 = Friday → should advance to Monday April 6
    friday = datetime(2026, 4, 3, 9, 0, 0)
    result = _next_occurrence(friday.isoformat(), "weekdays")
    assert result == datetime(2026, 4, 6, 9, 0, 0).isoformat()


def test_weekdays_skips_saturday_to_monday():
    saturday = datetime(2026, 4, 4, 9, 0, 0)
    result = _next_occurrence(saturday.isoformat(), "weekdays")
    dt = datetime.fromisoformat(result)
    assert dt.weekday() == 0  # Monday


def test_weekdays_advances_one_day_from_monday():
    monday = datetime(2026, 4, 6, 9, 0, 0)
    result = _next_occurrence(monday.isoformat(), "weekdays")
    assert result == datetime(2026, 4, 7, 9, 0, 0).isoformat()


def test_monthly_advances_one_month():
    due = datetime(2026, 4, 1, 9, 0, 0).isoformat()
    assert _next_occurrence(due, "monthly") == datetime(2026, 5, 1, 9, 0, 0).isoformat()


def test_monthly_wraps_december_to_january():
    due = datetime(2026, 12, 15, 9, 0, 0).isoformat()
    result = _next_occurrence(due, "monthly")
    dt = datetime.fromisoformat(result)
    assert dt.year == 2027
    assert dt.month == 1
    assert dt.day == 15


def test_monthly_end_of_month_clamps_to_feb():
    # Jan 31 → Feb 28 (2026 is not a leap year)
    due = datetime(2026, 1, 31, 9, 0, 0).isoformat()
    result = _next_occurrence(due, "monthly")
    dt = datetime.fromisoformat(result)
    assert dt.month == 2
    assert dt.day == 28


def test_hourly_advances_one_hour():
    due = datetime(2026, 4, 1, 9, 0, 0).isoformat()
    assert _next_occurrence(due, "hourly") == datetime(2026, 4, 1, 10, 0, 0).isoformat()


def test_unknown_recurrence_returns_none():
    due = datetime(2026, 4, 1, 9, 0, 0).isoformat()
    assert _next_occurrence(due, "biweekly") is None


def test_invalid_iso_returns_none():
    assert _next_occurrence("not-a-date", "daily") is None


def test_none_due_returns_none():
    assert _next_occurrence(None, "daily") is None
