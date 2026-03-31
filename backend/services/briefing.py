import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
from backend.services.weather import weather_service
from backend.services.rss_news import get_rss_articles
from backend.services.calendar_service import calendar_service
from backend.services.notifications import notification_service
from backend.services.memory import memory_service
from backend.services.llm import llm_router
from backend.config import config

PERIOD_SYSTEM = {
    "morning": "You deliver friendly, energizing morning briefings.",
    "afternoon": "You deliver concise, practical midday check-ins.",
    "evening": "You deliver warm, reflective evening briefings.",
    "night": "You deliver brief, calm late-night overviews.",
}

PERIOD_INSTRUCTION = {
    "morning": "You are delivering a friendly morning briefing. Be warm and energizing.",
    "afternoon": "You are delivering a midday check-in. Be concise and practical.",
    "evening": "You are delivering an evening briefing. Be warm and reflective.",
    "night": "You are delivering a late-night overview. Be brief and calm.",
}


async def collect_briefing_data(period: str = "morning") -> dict:
    """Gather all briefing data and return as a structured dict. No LLM involved."""
    data = {"period": period, "generated_at": datetime.utcnow().isoformat()}

    try:
        weather = await weather_service.get()
        data["weather"] = weather
    except Exception:
        data["weather"] = None

    try:
        events = await calendar_service.get_todays_events()
        data["events"] = events or []
    except Exception:
        data["events"] = []

    try:
        data["reminders"] = memory_service.get_pending_reminders()
    except Exception:
        data["reminders"] = []

    return data


def _format_article_for_prompt(article: dict) -> str:
    """Format a single article as a text block for the LLM prompt."""
    lines = [f"• {article['title']} ({article['source']})"]
    body = article.get("full_text") or article.get("description") or ""
    if body:
        lines.append(f"  {body.strip()}")
    return "\n".join(lines)


async def _synthesize_topic(topic: str, articles: list[dict], today: str) -> str:
    """
    Single LLM call for one topic. Instructs the model to identify the
    lead story first (chain-of-thought), then produce the summary.
    Returns the summary text, or empty string on failure.
    """
    article_block = "\n\n".join(_format_article_for_prompt(a) for a in articles)

    prompt = (
        f"Today is {today}.\n\n"
        f"Topic: {topic}\n\n"
        f"Recent articles:\n{article_block}\n\n"
        "Step 1 — Identify which story above is the most significant and why (one sentence).\n"
        "Step 2 — Write a 2-3 sentence briefing summary focused on that story. "
        "Be specific: reference actual events, people, numbers, or decisions mentioned. "
        "Do not invent facts.\n\n"
        "LEAD: <one sentence identifying the most important story>\n"
        "SUMMARY: <2-3 sentence briefing>"
    )

    try:
        response = await llm_router.complete([
            {"role": "system", "content": "You are a news briefing editor. Follow the output format exactly."},
            {"role": "user", "content": prompt},
        ])
        logger.info("[briefing] %s raw response: %s", topic, response[:300])
        # Extract SUMMARY from response
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
    except Exception as e:
        logger.error("[briefing] %s synthesis failed: %s", topic, e)
        return ""


async def _synthesize_rss_news(topics: list[str]) -> list[dict]:
    """
    Fetch RSS articles for all topics, enrich with full text, then run
    per-topic LLM synthesis calls in parallel.
    Returns list of news tile dicts ready for the frontend.
    """
    raw_articles = await get_rss_articles(topics)
    if not raw_articles:
        return []

    # Group by topic, preserving config order
    by_topic: dict[str, list[dict]] = {}
    for topic in topics:
        by_topic[topic] = []
    for a in raw_articles:
        if a["topic"] in by_topic:
            by_topic[a["topic"]].append(a)

    # Drop topics that got no articles
    by_topic = {t: arts for t, arts in by_topic.items() if arts}
    if not by_topic:
        return []

    today = datetime.utcnow().strftime("%A, %B %d, %Y").replace(" 0", " ")  # e.g. "Monday, March 30, 2026"

    # Sequential LLM calls — avoids per-minute rate limits on free tier APIs
    summaries = []
    for topic, articles in by_topic.items():
        summary = await _synthesize_topic(topic, articles, today)
        summaries.append(summary)

    result = []
    for (topic, articles), summary in zip(by_topic.items(), summaries):
        sources = list(dict.fromkeys(a["source"] for a in articles))[:3]
        result.append({
            "topic": topic,
            "summary": summary,
            "sources": sources,
        })

    return result


def _build_summary(data: dict, news_tiles: list[dict]) -> str:
    """Compose the summary card from weather + first sentence of top news summaries."""
    parts = []
    if data.get("weather"):
        w = data["weather"]
        parts.append(f"{w['description']} in {w['city']}, {w['temp']}{w['unit']}")
    for tile in news_tiles[:2]:
        first = (tile.get("summary") or "").split(".")[0].strip()
        if first:
            parts.append(first)
    return "  ·  ".join(parts)


async def generate_on_demand_briefing(period: str, force: bool = False) -> dict:
    """Return a structured briefing dict. Uses cached version if < 6 hours old."""
    if not force:
        cached = memory_service.get_recent_briefing(max_age_hours=6)
        if cached:
            try:
                parsed = json.loads(cached["content"])
                if "events" in parsed and "period" in parsed:
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass

    data = await collect_briefing_data(period)

    topics = config.get("news", {}).get("topics", [])
    data["news"] = await _synthesize_rss_news(topics) if topics else []
    data["summary"] = _build_summary(data, data["news"])

    memory_service.save_briefing(json.dumps(data))
    return data


async def generate_and_send_briefing():
    """Scheduled morning briefing: generates structured data, narrates via LLM, sends ntfy."""
    data = await collect_briefing_data("morning")

    topics = config.get("news", {}).get("topics", [])
    data["news"] = await _synthesize_rss_news(topics) if topics else []

    sections = []
    if data.get("weather"):
        w = data["weather"]
        sections.append(
            f"Weather: {w['description']}, {w['temp']}{w['unit']} "
            f"(feels like {w['feels_like']}{w['unit']}) in {w['city']}"
        )

    if data.get("events"):
        lines = "\n".join(f"  - {e['start']}: {e['title']}" for e in data["events"])
        sections.append(f"Calendar ({len(data['events'])} events today):\n{lines}")
    else:
        sections.append("Calendar: No events today")

    if data.get("news"):
        lines = "\n".join(
            f"  - {tile['topic']}: {tile.get('summary', '')}"
            for tile in data["news"]
        )
        sections.append(f"News highlights:\n{lines}")

    if data.get("reminders"):
        lines = "\n".join(
            f"  - {r['text']}" + (f" (due: {r['due_time']})" if r.get("due_time") else "")
            for r in data["reminders"]
        )
        sections.append(f"Reminders:\n{lines}")

    if not sections:
        return

    data_block = "\n\n".join(sections)
    today = datetime.utcnow().strftime("%A, %B %d, %Y").replace(" 0", " ")
    prompt = (
        f"Today is {today}. {PERIOD_INSTRUCTION['morning']} "
        "Write a concise, conversational paragraph — not a list.\n\n"
        f"Data:\n{data_block}\n\nWrite the morning briefing:"
    )

    briefing_text = await llm_router.complete([
        {"role": "system", "content": PERIOD_SYSTEM["morning"]},
        {"role": "user", "content": prompt},
    ])

    memory_service.save_briefing(json.dumps(data))
    await notification_service.send(title="Good morning!", body=briefing_text)
