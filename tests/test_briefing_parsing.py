"""Tests for pure parsing helpers in briefing.py."""
import sys
import os
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_STUB_MODS = [
    'backend.config', 'backend.services.weather', 'backend.services.rss_news',
    'backend.services.calendar_service', 'backend.services.notifications',
    'backend.services.memory', 'backend.services.llm',
]


@pytest.fixture(autouse=True, scope="module")
def _stub_heavy_imports():
    prior = {k: sys.modules.get(k) for k in _STUB_MODS}
    for mod in _STUB_MODS:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()
    sys.modules.pop('backend.services.briefing', None)
    yield
    for mod, val in prior.items():
        if val is None:
            sys.modules.pop(mod, None)
        else:
            sys.modules[mod] = val
    sys.modules.pop('backend.services.briefing', None)


def _fmt():
    from backend.services.briefing import _format_article_for_prompt
    return _format_article_for_prompt


# ── _format_article_for_prompt ────────────────────────────────────────────────

def test_format_uses_full_text_when_present():
    fn = _fmt()
    article = {"title": "Big Story", "source": "BBC", "full_text": "Full body text.", "description": "Short desc."}
    result = fn(article)
    assert "Full body text." in result
    assert "Short desc." not in result


def test_format_falls_back_to_description():
    fn = _fmt()
    article = {"title": "Story", "source": "CNN", "full_text": "", "description": "Fallback desc."}
    result = fn(article)
    assert "Fallback desc." in result


def test_format_no_body_omits_body_line():
    fn = _fmt()
    article = {"title": "Quiet Story", "source": "Reuters"}
    result = fn(article)
    lines = result.strip().splitlines()
    assert len(lines) == 1
    assert "Quiet Story" in lines[0]
    assert "Reuters" in lines[0]


def test_format_includes_bullet_and_source():
    fn = _fmt()
    article = {"title": "My Title", "source": "AP"}
    result = fn(article)
    assert result.startswith("• ")
    assert "AP" in result


def test_format_strips_whitespace_from_body():
    fn = _fmt()
    article = {"title": "T", "source": "S", "full_text": "  padded  "}
    result = fn(article)
    assert "padded" in result
    assert result.split("\n")[1].strip() == "padded"


# ── SUMMARY extraction logic (mirrors _synthesize_topic's parsing) ────────────

def _extract_summary(response: str) -> str:
    """Mirrors the SUMMARY: extraction logic from _synthesize_topic."""
    summary_lines = []
    in_summary = False
    for line in response.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("SUMMARY:"):
            in_summary = True
            rest = stripped[8:].strip()
            if rest:
                summary_lines.append(rest)
        elif in_summary and stripped:
            summary_lines.append(stripped)
    return " ".join(summary_lines).strip()


def test_summary_extraction_single_line():
    response = "LEAD: Story X is important.\nSUMMARY: This is the summary."
    assert _extract_summary(response) == "This is the summary."


def test_summary_extraction_multiline():
    response = "LEAD: Something.\nSUMMARY: First sentence.\nSecond sentence."
    result = _extract_summary(response)
    assert "First sentence." in result
    assert "Second sentence." in result


def test_summary_extraction_case_insensitive():
    response = "summary: lowercase label works"
    assert _extract_summary(response) == "lowercase label works"


def test_summary_extraction_missing_returns_empty():
    response = "LEAD: Only a lead here, no summary section."
    assert _extract_summary(response) == ""


def test_summary_extraction_skips_blank_lines_continues_collecting():
    # Blank lines are skipped; non-blank lines after them are still collected
    response = "SUMMARY: First.\n\nSecond after blank."
    result = _extract_summary(response)
    assert "First." in result
    assert "Second after blank." in result
