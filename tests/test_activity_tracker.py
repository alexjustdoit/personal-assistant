"""Tests for pure helper functions in activity_tracker."""
import sys
import os
from unittest.mock import MagicMock
from datetime import datetime, timezone

# Stub heavy deps before import
sys.modules.setdefault('backend.config', MagicMock(config={}))

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.services.activity_tracker import _webkit_to_dt, _summarise_history


# ── _webkit_to_dt ─────────────────────────────────────────────────────────────

def test_webkit_epoch_zero_is_1601():
    # WebKit ts=0 → 1601-01-01 00:00:00 UTC
    dt = _webkit_to_dt(0)
    assert dt.year == 1601
    assert dt.tzinfo == timezone.utc


def test_webkit_known_timestamp():
    # 13_000_000_000_000_000 µs → a known modern date
    # unix = 13e15 / 1e6 - 11_644_473_600 = 13_000_000 - 11_644_473_600 → negative, use smaller value
    # unix epoch (1970-01-01) = _WEBKIT_EPOCH_OFFSET * 1_000_000 µs
    _WEBKIT_EPOCH_OFFSET = 11_644_473_600
    ts_unix_epoch = int(_WEBKIT_EPOCH_OFFSET * 1_000_000)
    dt = _webkit_to_dt(ts_unix_epoch)
    assert dt.year == 1970
    assert dt.month == 1
    assert dt.day == 1
    assert dt.hour == 0


def test_webkit_2024_timestamp():
    # 2024-01-01 00:00:00 UTC = unix 1704067200
    _WEBKIT_EPOCH_OFFSET = 11_644_473_600
    unix_2024 = 1704067200
    ts = int((unix_2024 + _WEBKIT_EPOCH_OFFSET) * 1_000_000)
    dt = _webkit_to_dt(ts)
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 1
    assert dt.tzinfo == timezone.utc


# ── _summarise_history ────────────────────────────────────────────────────────

def test_summarise_empty_returns_empty():
    assert _summarise_history([]) == []


def test_summarise_single_entry():
    entries = [{"domain": "github.com", "title": "GitHub"}]
    lines = _summarise_history(entries)
    assert len(lines) == 1
    assert "github.com" in lines[0]
    assert "1 visit)" in lines[0]
    assert "GitHub" in lines[0]


def test_summarise_pluralises_multiple_visits():
    entries = [
        {"domain": "github.com", "title": "GitHub"},
        {"domain": "github.com", "title": "My Repo"},
    ]
    lines = _summarise_history(entries)
    assert "2 visits)" in lines[0]


def test_summarise_sorts_by_frequency_descending():
    entries = [
        {"domain": "a.com", "title": "A"},
        {"domain": "b.com", "title": "B1"},
        {"domain": "b.com", "title": "B2"},
        {"domain": "b.com", "title": "B3"},
    ]
    lines = _summarise_history(entries)
    assert lines[0].startswith("- b.com")
    assert lines[1].startswith("- a.com")


def test_summarise_picks_longest_unique_title():
    entries = [
        {"domain": "news.com", "title": "Short"},
        {"domain": "news.com", "title": "Much longer title here"},
        {"domain": "news.com", "title": "Short"},
    ]
    lines = _summarise_history(entries)
    assert "Much longer title here" in lines[0]


def test_summarise_deduplicates_domains():
    entries = [{"domain": "x.com", "title": f"T{i}"} for i in range(5)]
    lines = _summarise_history(entries)
    assert len(lines) == 1
    assert "5 visits)" in lines[0]
