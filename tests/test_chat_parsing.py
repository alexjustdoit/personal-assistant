"""Tests for JSON parsing helpers and _parse_datetime from the chat router."""
import sys
import os
import json
import re
from unittest.mock import MagicMock

# Stub out all FastAPI and heavy deps before importing
for mod in [
    'fastapi', 'backend.services.llm', 'backend.services.memory',
    'backend.services.search', 'backend.services.todoist',
    'backend.services.govee', 'backend.services.calendar_service',
    'backend.services.activity_tracker', 'backend.services.email_service',
    'backend.services.sessions_reader', 'backend.services.notes_watcher',
    'backend.services.claude_memory', 'backend.config',
    'dateparser',
]:
    sys.modules.setdefault(mod, MagicMock())

# dateparser.parse needs to return a real datetime for our test
import dateparser as _dp_mock
from datetime import datetime as _dt
_dp_mock.parse = lambda s, **kw: _dt(2026, 4, 15, 14, 0, 0) if "2026-04-15" in (s or "") else None

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def extract_json(text: str):
    """Mirrors the re.search logic used in all _detect_* functions."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group())
    return None


# ── Reminder JSON ─────────────────────────────────────────────────────────────

def test_reminder_with_due():
    raw = '{"task": "call dentist", "due": "tomorrow at 9am", "recurrence": null}'
    data = extract_json(raw)
    assert data["task"] == "call dentist"
    assert data["due"] == "tomorrow at 9am"
    assert data["recurrence"] is None


def test_reminder_with_recurrence():
    raw = '{"task": "take vitamins", "due": null, "recurrence": "daily"}'
    data = extract_json(raw)
    assert data["recurrence"] == "daily"


def test_reminder_null_action():
    data = extract_json('{"action": null}')
    assert data.get("action") is None


# ── Todoist detection ─────────────────────────────────────────────────────────

def test_todoist_add_single():
    raw = '{"action": "add", "task": "buy groceries", "due": null, "project": null}'
    data = extract_json(raw)
    assert data["action"] == "add"
    assert data["task"] == "buy groceries"


def test_todoist_add_many():
    raw = '{"action": "add_many", "tasks": [{"task": "buy milk", "due": null, "project": null}, {"task": "call doctor", "due": "friday", "project": null}]}'
    data = extract_json(raw)
    assert data["action"] == "add_many"
    assert len(data["tasks"]) == 2
    assert data["tasks"][1]["due"] == "friday"


def test_todoist_complete():
    raw = '{"action": "complete", "task_name": "buy groceries"}'
    data = extract_json(raw)
    assert data["action"] == "complete"
    assert data["task_name"] == "buy groceries"


def test_todoist_list():
    data = extract_json('{"action": "list"}')
    assert data["action"] == "list"


# ── Calendar detection ────────────────────────────────────────────────────────

def test_calendar_create():
    raw = '{"action": "create", "title": "Team standup", "start": "tomorrow at 10am", "duration_minutes": 30}'
    data = extract_json(raw)
    assert data["action"] == "create"
    assert data["title"] == "Team standup"
    assert data["duration_minutes"] == 30


def test_calendar_null():
    data = extract_json('{"action": null}')
    assert data.get("action") is None


# ── Govee detection ───────────────────────────────────────────────────────────

def test_govee_on():
    raw = '{"action": "on", "device": "bedroom light", "brightness": null, "color": null, "color_temp": null}'
    data = extract_json(raw)
    assert data["action"] == "on"
    assert data["device"] == "bedroom light"


def test_govee_brightness():
    raw = '{"action": "brightness", "device": "all", "brightness": 40, "color": null, "color_temp": null}'
    data = extract_json(raw)
    assert data["brightness"] == 40


# ── _parse_datetime ───────────────────────────────────────────────────────────

def test_parse_datetime_empty_returns_none():
    from backend.routers.chat import _parse_datetime
    assert _parse_datetime("") is None


def test_parse_datetime_none_returns_none():
    from backend.routers.chat import _parse_datetime
    assert _parse_datetime(None) is None


def test_parse_datetime_valid_iso():
    from backend.routers.chat import _parse_datetime
    result = _parse_datetime("2026-04-15 14:00")
    assert result is not None
    assert result.year == 2026
    assert result.hour == 14
