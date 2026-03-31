import json
from datetime import datetime
from backend.services.weather import weather_service
from backend.services.news import news_service
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


def _parse_synthesis(response: str, topics: list[str]) -> dict[str, str]:
    """Parse TOPIC/SUMMARY format into {topic: summary_text} dict."""
    summaries: dict[str, str] = {}
    current_topic: str | None = None
    current_lines: list[str] = []

    for line in response.splitlines():
        line = line.strip()
        if line.upper().startswith("TOPIC:"):
            if current_topic is not None:
                summaries[current_topic] = " ".join(current_lines).strip()
            raw = line[6:].strip()
            match = next((t for t in topics if t.lower() == raw.lower()), raw)
            current_topic = match
            current_lines = []
        elif line.upper().startswith("SUMMARY:"):
            current_lines = [line[8:].strip()]
        elif current_topic is not None and line:
            # Handle multi-line summaries
            current_lines.append(line)

    if current_topic is not None:
        summaries[current_topic] = " ".join(current_lines).strip()

    return summaries


async def _synthesize_rss_news(topics: list[str], period: str) -> list[dict]:
    """
    Fetch RSS headlines for each topic, then ask the LLM to write a
    2-3 sentence synthesis per topic. Returns list of news tile dicts.
    """
    raw_articles = await get_rss_articles(topics)
    if not raw_articles:
        return []

    # Group by topic, preserving order
    by_topic: dict[str, list[dict]] = {}
    for a in raw_articles:
        by_topic.setdefault(a["topic"], []).append(a)

    topic_blocks = []
    for topic, articles in by_topic.items():
        lines = [f"TOPIC: {topic}"]
        for a in articles:
            if a.get("description"):
                lines.append(f"  - {a['title']} ({a['source']}): {a['description']}")
            else:
                lines.append(f"  - {a['title']} ({a['source']})")
        topic_blocks.append("\n".join(lines))

    prompt = (
        "You are a news briefing writer. For each topic below, write 2-3 sentences "
        "summarizing the most notable recent developments based on the headlines provided. "
        "Be specific — reference actual events, trends, or people mentioned. "
        "Do not invent facts beyond what the headlines imply.\n\n"
        "Reply in exactly this format for each topic (no extra text):\n"
        "TOPIC: <name>\n"
        "SUMMARY: <2-3 sentences>\n\n"
        "---\n\n"
        + "\n\n".join(topic_blocks)
    )

    try:
        response = await llm_router.complete([
            {"role": "system", "content": "You are a news briefing writer. Follow the output format exactly."},
            {"role": "user", "content": prompt},
        ])
        summaries = _parse_synthesis(response, list(by_topic.keys()))
    except Exception:
        summaries = {}

    result = []
    for topic, articles in by_topic.items():
        # Deduplicate sources, keep up to 3
        sources = list(dict.fromkeys(a["source"] for a in articles))[:3]
        result.append({
            "topic": topic,
            "summary": summaries.get(topic, ""),
            "sources": sources,
        })

    return result


def _build_summary(data: dict, news_tiles: list[dict]) -> str:
    """
    Compose the summary card text from weather + first sentence of top news summaries.
    """
    parts = []
    if data.get("weather"):
        w = data["weather"]
        parts.append(f"{w['description']} in {w['city']}, {w['temp']}{w['unit']}")
    for tile in news_tiles[:2]:
        summary = tile.get("summary", "")
        if summary:
            # Take just the first sentence
            first = summary.split(".")[0].strip()
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
    if topics:
        data["news"] = await _synthesize_rss_news(topics, period)
    else:
        data["news"] = []

    data["summary"] = _build_summary(data, data["news"])
    memory_service.save_briefing(json.dumps(data))
    return data


async def generate_and_send_briefing():
    """Scheduled morning briefing: generates structured data, narrates via LLM, sends ntfy."""
    data = await collect_briefing_data("morning")

    topics = config.get("news", {}).get("topics", [])
    if topics:
        data["news"] = await _synthesize_rss_news(topics, "morning")
    else:
        data["news"] = []

    sections = []
    if data.get("weather"):
        w = data["weather"]
        sections.append(f"Weather: {w['description']}, {w['temp']}{w['unit']} (feels like {w['feels_like']}{w['unit']}) in {w['city']}")

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
    prompt = f"""{PERIOD_INSTRUCTION["morning"]} Write a concise, conversational paragraph — not a list.

Data:
{data_block}

Write the morning briefing:"""

    briefing_text = await llm_router.complete([
        {"role": "system", "content": PERIOD_SYSTEM["morning"]},
        {"role": "user", "content": prompt},
    ])

    memory_service.save_briefing(json.dumps(data))

    await notification_service.send(
        title="Good morning!",
        body=briefing_text,
    )
