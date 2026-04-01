"""
Email service — IMAP-based inbox fetching with spam filtering.

Supports multiple accounts. Uses Python's built-in imaplib (no extra deps).
Connects with SSL on port 993.

Gmail:   Enable IMAP in Gmail settings → use an App Password (myaccount.google.com/apppasswords)
Outlook: imap.outlook.com or outlook.office365.com, port 993, regular password or app password

Config (config.yaml):
  email:
    accounts:
      - name: "Gmail"
        imap_host: imap.gmail.com
        imap_port: 993
        username: you@gmail.com
        password: "your-app-password"
      - name: "Outlook"
        imap_host: outlook.office365.com
        imap_port: 993
        username: you@outlook.com
        password: "your-password"
    fetch_hours: 24        # how far back to look
    max_per_account: 20    # max emails fetched per account (most recent)
"""

import asyncio
import email
import imaplib
import re
import time
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

from backend.config import config

# ----- Spam detection -----

_BULK_HEADERS = {"list-unsubscribe", "list-id", "list-post", "x-mailchimp", "x-campaign"}
_BULK_PRECEDENCE = {"bulk", "list", "junk"}

_PROMO_RE = re.compile(
    r"\b(unsubscribe|newsletter|% off|\bsale\b|promo|discount|coupon|marketing|digest"
    r"|no.reply|noreply|do.not.reply|donotreply|auto.?reply)\b",
    re.I,
)

# ----- In-memory cache -----

_cache: dict = {"emails": None, "ts": 0.0}
_CACHE_TTL = 900  # 15 minutes


def _cache_get() -> list[dict] | None:
    if _cache["emails"] is not None and time.time() - _cache["ts"] < _CACHE_TTL:
        return _cache["emails"]
    return None


def _cache_set(emails: list[dict]):
    _cache["emails"] = emails
    _cache["ts"] = time.time()


def _cache_clear():
    _cache["emails"] = None
    _cache["ts"] = 0.0


# ----- Helpers -----

def _decode(value: str) -> str:
    parts = decode_header(value or "")
    out = []
    for part, charset in parts:
        if isinstance(part, bytes):
            out.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(str(part))
    return " ".join(out).strip()


def _is_spam(msg) -> bool:
    headers_lc = {k.lower() for k in msg.keys()}
    if headers_lc & _BULK_HEADERS:
        return True
    if msg.get("Precedence", "").lower().strip() in _BULK_PRECEDENCE:
        return True
    _, addr = parseaddr(msg.get("From", ""))
    if _PROMO_RE.search(addr):
        return True
    if _PROMO_RE.search(_decode(msg.get("Subject", ""))):
        return True
    return False


def _body(msg) -> str:
    LIMIT = 400
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                    raw = part.get_payload(decode=True)
                    if raw:
                        return raw.decode(part.get_content_charset() or "utf-8", errors="replace")[:LIMIT].strip()
        else:
            raw = msg.get_payload(decode=True)
            if raw:
                return raw.decode(msg.get_content_charset() or "utf-8", errors="replace")[:LIMIT].strip()
    except Exception:
        pass
    return ""


# ----- IMAP fetching -----

def _fetch_account(account: dict, fetch_hours: int, max_count: int) -> list[dict]:
    host = account.get("imap_host", "")
    port = int(account.get("imap_port", 993))
    username = account.get("username", "")
    password = account.get("password", "")
    name = account.get("name") or username

    if not all([host, username, password]):
        return []

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(username, password)
        conn.select("INBOX", readonly=True)

        since = (datetime.now() - timedelta(hours=fetch_hours)).strftime("%d-%b-%Y")
        _, data = conn.search(None, f'SINCE "{since}"')
        uids = data[0].split() if data[0] else []
        uids = uids[-max_count:][::-1]  # most recent first, capped

        results = []
        for uid in uids:
            try:
                _, msg_data = conn.fetch(uid, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                if isinstance(raw, str):
                    raw = raw.encode()
                msg = email.message_from_bytes(raw)

                if _is_spam(msg):
                    continue

                subject = _decode(msg.get("Subject", "(no subject)"))
                from_name, from_addr = parseaddr(msg.get("From", ""))
                sender = _decode(from_name) if from_name else from_addr

                try:
                    date_str = parsedate_to_datetime(msg.get("Date", "")).strftime("%-I:%M %p")
                except Exception:
                    date_str = ""

                results.append({
                    "account": name,
                    "from": sender,
                    "from_addr": from_addr,
                    "subject": subject,
                    "date": date_str,
                    "body": _body(msg),
                })
            except Exception:
                continue

        conn.logout()
        return results

    except Exception as e:
        print(f"[Email] {name}: {e}")
        return []


# ----- Public API -----

def email_enabled() -> bool:
    return bool(config.get("email", {}).get("accounts"))


async def fetch_emails(force: bool = False) -> list[dict]:
    """Fetch emails from all configured accounts. Cached for 15 min."""
    if not force:
        cached = _cache_get()
        if cached is not None:
            return cached

    cfg = config.get("email", {})
    accounts = cfg.get("accounts", [])
    if not accounts:
        return []

    fetch_hours = int(cfg.get("fetch_hours", 24))
    max_per = int(cfg.get("max_per_account", 20))

    results = await asyncio.gather(*[
        asyncio.to_thread(_fetch_account, acc, fetch_hours, max_per)
        for acc in accounts
    ], return_exceptions=True)

    combined = []
    for r in results:
        if isinstance(r, list):
            combined.extend(r)

    _cache_set(combined)
    return combined


async def summarize_emails(emails: list[dict], query: str | None = None, provider: str | None = None) -> str:
    """LLM summary of fetched emails. If query is given, answers that specific question."""
    if not emails:
        return "No emails in the last 24 hours."

    from backend.services.llm import llm_router

    lines = []
    for e in emails[:20]:
        line = f"From: {e['from']} | Subject: {e['subject']}"
        if e.get("date"):
            line += f" | {e['date']}"
        if e.get("body"):
            line += f"\n  {e['body'][:200]}"
        lines.append(line)
    block = "\n\n".join(lines)

    if query:
        prompt = f'Emails:\n\n{block}\n\nQuestion: {query}\n\nAnswer concisely.'
        system = "You answer questions about the user's emails. Be specific and direct."
    else:
        prompt = (
            "Summarize these emails in 2-3 sentences. Focus on anything actionable, "
            "time-sensitive, or important. Ignore routine automated messages.\n\n" + block
        )
        system = "You summarize email inboxes concisely."

    try:
        return await llm_router.complete_briefing(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            provider=provider,
        )
    except Exception as e:
        print(f"[Email] Summary error: {e}")
        return f"{len(emails)} email{'s' if len(emails) != 1 else ''} (summary unavailable)"
