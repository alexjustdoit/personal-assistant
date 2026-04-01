"""
notification_queue.py — In-process queue for browser push notifications.

The scheduler pushes reminder alerts here; the frontend polls /api/notifications/pending
every 30s and fires the Web Notifications API.
"""

from collections import deque

_queue: deque = deque(maxlen=50)


def push(title: str, body: str):
    _queue.append({"title": title, "body": body})


def pop_all() -> list:
    items = list(_queue)
    _queue.clear()
    return items
