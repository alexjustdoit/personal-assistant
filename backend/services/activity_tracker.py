"""
Passive activity tracker — Windows only.

Polls browser history (Chrome/Edge) and samples the active window every
`poll_interval_minutes`. Writes markdown activity logs to a configured
folder (which should also be in notes_folders so it's ingested by
NotesWatcherService). At the configured end-of-day time, synthesizes all
today's logs into a single summary note.

Config (config.yaml):
    activity_tracking:
      enabled: true
      log_folder: "C:\\Users\\you\\Notes\\activity"   # must also be in notes_folders
      poll_interval_minutes: 30                         # default 30
      eod_summary_time: "22:00"                         # default 22:00
"""

import platform
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from backend.config import config

# Chrome/Edge timestamps: microseconds since 1601-01-01
_WEBKIT_EPOCH_OFFSET = 11_644_473_600  # seconds between 1601 and 1970

# Built-in noise domains always ignored
_BASE_IGNORE_DOMAINS = {
    "newtab", "localhost", "127.0.0.1", "extensions", "chrome", "edge",
    "about", "blank",
}


_SHARED_IGNORE_FILE = "ignored_domains.txt"


def _ignore_domains() -> set[str]:
    """Base set + config ignored_domains + shared ignored_domains.txt in log folder."""
    custom = config.get("activity_tracking", {}).get("ignored_domains", [])
    domains = _BASE_IGNORE_DOMAINS | {d.lower().removeprefix("www.").strip("/") for d in custom}
    log_folder = config.get("activity_tracking", {}).get("log_folder", "")
    if log_folder:
        shared = Path(log_folder) / _SHARED_IGNORE_FILE
        if shared.exists():
            for line in shared.read_text(encoding="utf-8").splitlines():
                line = line.strip().lower().removeprefix("www.").strip("/")
                if line and not line.startswith("#"):
                    domains.add(line)
    return domains


def _write_shared_ignore_file():
    """Write all ignored domains to ignored_domains.txt in the log folder (syncs to mac-agent via iCloud)."""
    log_folder = config.get("activity_tracking", {}).get("log_folder", "")
    if not log_folder:
        return
    all_domains = sorted(
        d for d in config.get("activity_tracking", {}).get("ignored_domains", []) if d
    )
    path = Path(log_folder) / _SHARED_IGNORE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(all_domains) + "\n", encoding="utf-8")


def add_ignored_domain(domain: str) -> bool:
    """
    Add a domain to activity_tracking.ignored_domains in config.yaml.
    Updates in-memory config too. Returns True if newly added, False if already present.
    """
    import yaml
    from backend.config import CONFIG_PATH

    domain = domain.lower().removeprefix("www.").strip("/").strip()
    current = [d.lower() for d in config.get("activity_tracking", {}).get("ignored_domains", [])]
    if domain in current:
        return False

    # Update in-memory
    config.setdefault("activity_tracking", {}).setdefault("ignored_domains", []).append(domain)

    # Persist to config.yaml
    with open(CONFIG_PATH) as f:
        raw = yaml.safe_load(f) or {}
    raw.setdefault("activity_tracking", {}).setdefault("ignored_domains", [])
    if domain not in [d.lower() for d in raw["activity_tracking"]["ignored_domains"]]:
        raw["activity_tracking"]["ignored_domains"].append(domain)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False)

    print(f"[ActivityTracker] Ignoring domain: {domain}")

    # Retroactively purge from existing log files
    log_folder = config.get("activity_tracking", {}).get("log_folder", "")
    if log_folder:
        purge_domain_from_logs(domain, log_folder)

    # Sync to mac-agent via shared file in iCloud log folder
    _write_shared_ignore_file()

    return True


def purge_domain_from_logs(domain: str, log_folder: str) -> int:
    """
    Remove all browser log lines mentioning `domain` from activity log files.
    Deletes the file entirely if nothing remains after the browser section.
    Returns the number of files modified.
    """
    folder = Path(log_folder)
    if not folder.exists():
        return 0

    modified = 0
    for log_file in folder.glob("activity_*.md"):
        try:
            original = log_file.read_text(encoding="utf-8")
            filtered = "\n".join(
                line for line in original.splitlines()
                if domain not in line.lower()
            ).strip()

            # If the file is now empty or only has a heading, remove it
            non_empty_lines = [l for l in filtered.splitlines() if l.strip() and not l.startswith("#")]
            if not non_empty_lines:
                log_file.unlink()
                print(f"[ActivityTracker] Deleted (now empty): {log_file.name}")
            elif filtered != original.strip():
                log_file.write_text(filtered + "\n", encoding="utf-8")
                print(f"[ActivityTracker] Purged {domain} from {log_file.name}")
            modified += 1
        except Exception as e:
            print(f"[ActivityTracker] Purge error on {log_file.name}: {e}")

    return modified


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _webkit_to_dt(ts: int) -> datetime:
    unix = (ts / 1_000_000) - _WEBKIT_EPOCH_OFFSET
    return datetime.fromtimestamp(unix, tz=timezone.utc)


def _browser_history_paths() -> list[tuple[str, Path]]:
    if not _is_windows():
        return []
    local = Path.home() / "AppData" / "Local"
    candidates = [
        ("Chrome", local / "Google" / "Chrome" / "User Data" / "Default" / "History"),
        ("Edge",   local / "Microsoft" / "Edge"   / "User Data" / "Default" / "History"),
    ]
    return [(name, p) for name, p in candidates if p.exists()]


def poll_browser_history(minutes_back: int = 30) -> list[dict]:
    """Return recent browser visits grouped by domain. Safe to call while browser is open."""
    if not _is_windows():
        return []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_back)
    cutoff_webkit = int((cutoff.timestamp() + _WEBKIT_EPOCH_OFFSET) * 1_000_000)
    entries = []
    for browser, history_path in _browser_history_paths():
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp_path = tmp.name
            shutil.copy2(str(history_path), tmp_path)
            with sqlite3.connect(f"file:{tmp_path}?mode=ro&immutable=1", uri=True) as conn:
                rows = conn.execute(
                    "SELECT url, title, last_visit_time FROM urls "
                    "WHERE last_visit_time > ? ORDER BY last_visit_time DESC",
                    (cutoff_webkit,),
                ).fetchall()
            ignore = _ignore_domains()
            for url, title, ts in rows:
                try:
                    domain = urlparse(url).netloc.removeprefix("www.")
                except Exception:
                    domain = url
                if any(domain.startswith(ign) for ign in ignore):
                    continue
                entries.append({
                    "browser": browser,
                    "url": url,
                    "title": (title or "").strip() or domain,
                    "domain": domain,
                    "visited_at": _webkit_to_dt(ts),
                })
        except Exception as e:
            print(f"[ActivityTracker] History error ({browser}): {e}")
        finally:
            if tmp_path:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass
    return entries


def get_active_window() -> str | None:
    """Return the foreground window title on Windows, or None."""
    if not _is_windows():
        return None
    try:
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or None
    except Exception:
        return None


def _summarise_history(entries: list[dict]) -> list[str]:
    """Group visits by domain and return readable summary lines."""
    domain_visits: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        domain_visits[e["domain"]].append(e["title"])
    lines = []
    for domain, titles in sorted(domain_visits.items(), key=lambda x: -len(x[1])):
        count = len(titles)
        # Pick the most representative title (longest unique)
        sample = max(set(titles), key=len)
        lines.append(f"- {domain} ({count} visit{'s' if count > 1 else ''}) — {sample}")
    return lines


def write_activity_log(log_folder: str, minutes_back: int = 30) -> Path | None:
    """
    Poll history + active window and write a markdown log file.
    Returns the path written, or None if nothing to log.
    """
    folder = Path(log_folder)
    folder.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    entries = poll_browser_history(minutes_back=minutes_back)
    window = get_active_window()

    if not entries and not window:
        return None

    lines = [f"# Activity — {now.strftime('%Y-%m-%d %H:%M')}\n"]

    if entries:
        lines.append("## Browser")
        lines.extend(_summarise_history(entries))

    if window:
        lines.append("\n## Active window")
        lines.append(f"- {window}")

    content = "\n".join(lines) + "\n"
    filename = f"activity_{now.strftime('%Y-%m-%d_%H%M')}.md"
    path = folder / filename
    path.write_text(content, encoding="utf-8")
    print(f"[ActivityTracker] Wrote {filename}")
    return path


async def synthesize_day(log_folder: str, date: datetime | None = None) -> str | None:
    """
    Read all activity logs for `date` (default today), synthesize with LLM,
    write a summary note, return the summary text.
    """
    from backend.services.llm import llm_router

    folder = Path(log_folder)
    target = (date or datetime.now()).strftime("%Y-%m-%d")
    logs = sorted(folder.glob(f"activity_{target}_*.md"))
    if not logs:
        return None

    combined = "\n\n---\n\n".join(p.read_text(encoding="utf-8") for p in logs)
    prompt = (
        f"The following are activity logs for {target}. "
        "Write a concise daily summary (3-6 bullets) covering what the user worked on, "
        "browsed, and did. Group related activities. Be specific about sites and tasks. "
        "Do not add commentary or advice.\n\n"
        f"{combined}"
    )
    try:
        summary = await llm_router.complete([
            {"role": "system", "content": "You summarize daily activity logs. Reply with bullet points only."},
            {"role": "user", "content": prompt},
        ])
    except Exception as e:
        print(f"[ActivityTracker] Synthesis error: {e}")
        return None

    out_path = folder / f"summary_{target}.md"
    out_path.write_text(
        f"# Day Summary — {target}\n\n{summary}\n",
        encoding="utf-8",
    )
    print(f"[ActivityTracker] Wrote summary_{target}.md")
    return summary
