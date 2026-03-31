#!/usr/bin/env python3
"""
Personal Assistant — Mac Activity Agent

Polls Safari + Chrome/Edge browser history and the active application,
then writes a markdown activity log to an iCloud Drive folder. The
Windows PA picks this up automatically via notes_watcher.

Designed to be run on a schedule via launchd (see install.sh).
Run manually: python3 agent.py

Requirements:
  pip3 install pyyaml

macOS permissions:
  Safari history requires Full Disk Access for your terminal / Python binary.
  System Preferences → Privacy & Security → Full Disk Access → add Terminal
  (or whichever app runs this script).
  Chrome/Edge history does not require FDA.
"""

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).parent
_CONFIG_PATH = _SCRIPT_DIR / "config.yaml"

def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        print(f"[MacAgent] No config.yaml found at {_CONFIG_PATH}")
        print("[MacAgent] Copy config.yaml.example to config.yaml and edit it.")
        sys.exit(1)
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Apple CoreData epoch: seconds between 2001-01-01 and 1970-01-01
_APPLE_EPOCH_OFFSET = 978_307_200

# Chrome/Edge: microseconds since 1601-01-01
_WEBKIT_EPOCH_OFFSET = 11_644_473_600

_IGNORE_DOMAINS = {
    "newtab", "localhost", "127.0.0.1", "extensions", "chrome",
    "edge", "about", "blank", "apple",
}

# ---------------------------------------------------------------------------
# Browser history
# ---------------------------------------------------------------------------

def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.removeprefix("www.")
    except Exception:
        return url


def _read_safari(minutes_back: int) -> list[dict]:
    history_db = Path.home() / "Library" / "Safari" / "History.db"
    if not history_db.exists():
        return []
    cutoff_apple = (
        datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_back)
    ).timestamp() - _APPLE_EPOCH_OFFSET
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        shutil.copy2(str(history_db), tmp_path)
        with sqlite3.connect(f"file:{tmp_path}?mode=ro&immutable=1", uri=True) as conn:
            rows = conn.execute(
                """
                SELECT i.url, v.title, v.visit_time
                FROM history_visits v
                JOIN history_items i ON v.history_item = i.id
                WHERE v.visit_time > ?
                ORDER BY v.visit_time DESC
                """,
                (cutoff_apple,),
            ).fetchall()
        entries = []
        for url, title, ts in rows:
            d = _domain(url)
            if any(d.startswith(ign) for ign in _IGNORE_DOMAINS):
                continue
            entries.append({"browser": "Safari", "url": url, "title": (title or "").strip() or d, "domain": d})
        return entries
    except PermissionError:
        print("[MacAgent] Safari: permission denied — grant Full Disk Access to Python/Terminal")
        return []
    except Exception as e:
        print(f"[MacAgent] Safari error: {e}")
        return []
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


def _read_chromium(browser: str, history_path: Path, minutes_back: int) -> list[dict]:
    if not history_path.exists():
        return []
    cutoff_webkit = int(
        (datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_back)).timestamp()
        + _WEBKIT_EPOCH_OFFSET
    ) * 1_000_000
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        shutil.copy2(str(history_path), tmp_path)
        with sqlite3.connect(f"file:{tmp_path}?mode=ro&immutable=1", uri=True) as conn:
            rows = conn.execute(
                "SELECT url, title, last_visit_time FROM urls WHERE last_visit_time > ? ORDER BY last_visit_time DESC",
                (cutoff_webkit,),
            ).fetchall()
        entries = []
        for url, title, _ in rows:
            d = _domain(url)
            if any(d.startswith(ign) for ign in _IGNORE_DOMAINS):
                continue
            entries.append({"browser": browser, "url": url, "title": (title or "").strip() or d, "domain": d})
        return entries
    except Exception as e:
        print(f"[MacAgent] {browser} error: {e}")
        return []
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


def poll_browser_history(minutes_back: int) -> list[dict]:
    app_support = Path.home() / "Library" / "Application Support"
    entries = _read_safari(minutes_back)
    entries += _read_chromium(
        "Chrome",
        app_support / "Google" / "Chrome" / "Default" / "History",
        minutes_back,
    )
    entries += _read_chromium(
        "Edge",
        app_support / "Microsoft Edge" / "Default" / "History",
        minutes_back,
    )
    return entries

# ---------------------------------------------------------------------------
# Active application
# ---------------------------------------------------------------------------

def get_active_app() -> str | None:
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=3,
        )
        name = result.stdout.strip()
        return name or None
    except Exception as e:
        print(f"[MacAgent] Active app error: {e}")
        return None

# ---------------------------------------------------------------------------
# Log writing (same format as Windows activity_tracker.py)
# ---------------------------------------------------------------------------

def _summarise_history(entries: list[dict]) -> list[str]:
    domain_visits: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        domain_visits[e["domain"]].append(e["title"])
    lines = []
    for domain, titles in sorted(domain_visits.items(), key=lambda x: -len(x[1])):
        count = len(titles)
        sample = max(set(titles), key=len)
        lines.append(f"- {domain} ({count} visit{'s' if count > 1 else ''}) — {sample}")
    return lines


def write_log(log_folder: str, minutes_back: int) -> Path | None:
    folder = Path(log_folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    entries = poll_browser_history(minutes_back)
    app = get_active_app()

    if not entries and not app:
        print("[MacAgent] Nothing to log.")
        return None

    lines = [f"# Activity — {now.strftime('%Y-%m-%d %H:%M')} (Mac)\n"]

    if entries:
        lines.append("## Browser")
        lines.extend(_summarise_history(entries))

    if app:
        lines.append("\n## Active app")
        lines.append(f"- {app}")

    content = "\n".join(lines) + "\n"
    filename = f"activity_{now.strftime('%Y-%m-%d_%H%M')}_mac.md"
    path = folder / filename
    path.write_text(content, encoding="utf-8")
    print(f"[MacAgent] Wrote {filename}")
    return path

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cfg = load_config()
    log_folder = cfg.get("log_folder", "")
    if not log_folder:
        print("[MacAgent] log_folder not set in config.yaml")
        sys.exit(1)
    minutes_back = int(cfg.get("poll_interval_minutes", 30))
    write_log(log_folder, minutes_back)


if __name__ == "__main__":
    main()
