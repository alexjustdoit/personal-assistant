"""
sessions_reader.py — Read ~/.claude/sessions/*.md to answer questions about past work sessions.
"""

import re
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"

_SESSION_QUERY = re.compile(
    r"\b(session|sessions|last week|this week|what did (i|we) (work on|do|build|implement|fix|add)|"
    r"what (have i|was i|were we) (working on|doing)|recent work|"
    r"what('?s| is) (new|done|changed|finished)|"
    r"(tam copilot|discovery assistant|personal assistant) (progress|update|changes|status)|"
    r"what did (claude|you) (do|help)|recap|summary of (work|session))\b",
    re.I,
)


def is_session_query(message: str) -> bool:
    return bool(_SESSION_QUERY.search(message))


def search_sessions(query: str, n: int = 3) -> list[dict]:
    """Return the n most relevant session file excerpts for the query."""
    if not SESSIONS_DIR.exists():
        return []

    query_lower = query.lower()
    query_words = set(re.findall(r"\w+", query_lower)) - {
        "the", "a", "an", "i", "me", "my", "did", "do", "was", "is", "are",
        "what", "how", "when", "why", "on", "in", "at", "to", "for", "of",
        "and", "or", "it", "this", "that", "with", "about",
    }

    results = []
    for path in sorted(SESSIONS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue

            text_lower = text.lower()
            score = sum(1 for w in query_words if w in text_lower)

            # Always include the most recent file even if score is 0
            if score > 0 or not results:
                results.append({"path": path, "text": text, "score": score, "mtime": path.stat().st_mtime})
        except Exception:
            continue

    # Sort: score desc, then recency desc
    results.sort(key=lambda r: (r["score"], r["mtime"]), reverse=True)

    out = []
    for r in results[:n]:
        # Extract just the key sections to avoid enormous context injection
        text = r["text"]
        excerpt = _extract_sections(text, ["What was done", "Key decisions", "Next steps"])
        out.append({
            "source": r["path"].stem,  # e.g. "personal-assistant"
            "excerpt": excerpt[:1500],
        })
    return out


def _extract_sections(text: str, sections: list[str]) -> str:
    parts = []
    for section in sections:
        pattern = rf"##\s+{re.escape(section)}\s*\n(.*?)(?=\n##|\Z)"
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            content = m.group(1).strip()
            if content:
                parts.append(f"**{section}:**\n{content}")
    # Also grab the date/project header
    header_lines = []
    for line in text.splitlines()[:6]:
        if line.strip():
            header_lines.append(line)
    header = "\n".join(header_lines)
    return header + "\n\n" + "\n\n".join(parts) if parts else text[:800]
