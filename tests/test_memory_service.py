"""Tests for MemoryService SQLite logic using a temp DB."""
import sys
import os
import tempfile
from unittest.mock import MagicMock

# Stub chromadb before import
sys.modules.setdefault('chromadb', MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

# Redirect DB to a temp file before the service initialises
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import backend.services.memory as mem_module
mem_module.DB_PATH = mem_module.Path(_tmp_db.name)

from backend.services.memory import MemoryService


@pytest.fixture
def svc():
    return MemoryService()


# ── Messages ──────────────────────────────────────────────────────────────────

def test_save_and_retrieve_message(svc):
    svc.save_message("s1", "user", "hello")
    history = svc.get_history("s1")
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"


def test_get_history_excludes_summary_role(svc):
    svc.save_message("s2", "user", "hi")
    svc.save_message("s2", "summary", "a summary")
    svc.save_message("s2", "assistant", "hello back")
    history = svc.get_history("s2")
    assert all(m["role"] != "summary" for m in history)
    assert len(history) == 2


def test_delete_last_messages(svc):
    svc.save_message("s-del", "user", "msg1")
    svc.save_message("s-del", "assistant", "msg2")
    svc.save_message("s-del", "user", "msg3")
    svc.delete_last_messages("s-del", 2)
    history = svc.get_history("s-del")
    assert len(history) == 1
    assert history[0]["content"] == "msg1"


# ── Reminders ─────────────────────────────────────────────────────────────────

def test_create_and_get_reminder(svc):
    svc.create_reminder("buy milk", recurrence="daily")
    reminders = svc.get_pending_reminders()
    r = next((r for r in reminders if r["text"] == "buy milk"), None)
    assert r is not None
    assert r["recurrence"] == "daily"


def test_complete_reminder_removes_from_pending(svc):
    svc.create_reminder("call doctor")
    pending = svc.get_pending_reminders()
    r = next(r for r in pending if r["text"] == "call doctor")
    svc.complete_reminder(r["id"])
    after = svc.get_pending_reminders()
    assert all(x["text"] != "call doctor" for x in after)


def test_delete_reminder(svc):
    svc.create_reminder("take out trash")
    pending = svc.get_pending_reminders()
    r = next(r for r in pending if r["text"] == "take out trash")
    svc.delete_reminder(r["id"])
    after = svc.get_pending_reminders()
    assert all(x["text"] != "take out trash" for x in after)


def test_update_reminder_due(svc):
    svc.create_reminder("water plants")
    pending = svc.get_pending_reminders()
    r = next(r for r in pending if r["text"] == "water plants")
    svc.update_reminder_due(r["id"], "2026-04-10T09:00:00")
    after = svc.get_pending_reminders()
    updated = next(x for x in after if x["id"] == r["id"])
    assert updated["due_time"] == "2026-04-10T09:00:00"


# ── Chat names ────────────────────────────────────────────────────────────────

def test_rename_and_get_chats(svc):
    svc.save_message("sess-abc", "user", "first message")
    svc.rename_chat("sess-abc", "My Chat")
    chats = svc.get_chats()
    match = next((c for c in chats if c["id"] == "sess-abc"), None)
    assert match is not None
    assert match["name"] == "My Chat"


def test_archive_and_unarchive_chat(svc):
    svc.save_message("sess-arch", "user", "hi")
    svc.archive_chat("sess-arch")
    active = svc.get_chats(include_archived=False)
    assert all(c["id"] != "sess-arch" for c in active)
    svc.unarchive_chat("sess-arch")
    active2 = svc.get_chats(include_archived=False)
    assert any(c["id"] == "sess-arch" for c in active2)


def test_pin_sorts_chat_to_top(svc):
    import time
    svc.save_message("sess-old", "user", "old message")
    time.sleep(0.02)  # ensure distinct timestamps
    svc.save_message("sess-new", "user", "new message")
    svc.pin_chat("sess-old")
    chats = svc.get_chats()
    active = [c for c in chats if not c["archived"]]
    assert active[0]["id"] == "sess-old"
    assert active[0]["pinned"] is True


def test_unpin_chat(svc):
    svc.save_message("sess-unpin", "user", "hi")
    svc.pin_chat("sess-unpin")
    svc.unpin_chat("sess-unpin")
    chats = svc.get_chats()
    match = next(c for c in chats if c["id"] == "sess-unpin")
    assert match["pinned"] is False


# ── System prompt ─────────────────────────────────────────────────────────────

def test_build_system_prompt_includes_memories(svc):
    prompt = svc.build_system_prompt(["user likes coffee", "user is a TAM"])
    assert "coffee" in prompt
    assert "TAM" in prompt


def test_build_system_prompt_includes_reminders(svc):
    reminders = [{"text": "dentist appointment", "due_time": None, "recurrence": None}]
    prompt = svc.build_system_prompt([], reminders)
    assert "dentist appointment" in prompt


def test_build_system_prompt_includes_conv_summary(svc):
    prompt = svc.build_system_prompt([], conv_summary="Earlier we discussed Python.")
    assert "Python" in prompt


def test_build_system_prompt_empty_memories_no_section(svc):
    prompt = svc.build_system_prompt([])
    assert "Things you know" not in prompt
