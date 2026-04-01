"""Tests for notification_queue push/pop semantics."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import backend.services.notification_queue as nq


def setup_function():
    """Clear the queue before each test."""
    nq._queue.clear()


def test_push_adds_item():
    nq.push("Title", "Body")
    assert len(nq._queue) == 1


def test_pop_all_returns_all_items():
    nq.push("T1", "B1")
    nq.push("T2", "B2")
    items = nq.pop_all()
    assert len(items) == 2
    assert items[0] == {"title": "T1", "body": "B1"}
    assert items[1] == {"title": "T2", "body": "B2"}


def test_pop_all_clears_queue():
    nq.push("T", "B")
    nq.pop_all()
    assert len(nq._queue) == 0


def test_pop_all_empty_returns_empty_list():
    assert nq.pop_all() == []


def test_maxlen_evicts_oldest():
    for i in range(55):
        nq.push(f"T{i}", "B")
    items = nq.pop_all()
    # maxlen=50, oldest 5 evicted
    assert len(items) == 50
    assert items[0]["title"] == "T5"
    assert items[-1]["title"] == "T54"
