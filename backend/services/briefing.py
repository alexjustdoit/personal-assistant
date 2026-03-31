import json
from datetime import datetime
from backend.services.weather import weather_service
from backend.services.news import news_service
from backend.services.calendar_service import calendar_service
from backend.services.notifications import notification_service
from backend.services.memory import memory_service
from backend.services.llm import llm_router

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
        data["news"] = await news_service.get_articles()
    except Exception:
        data["news"] = []

    try:
        data["reminders"] = memory_service.get_pending_reminders()
    except Exception:
        data["reminders"] = []

    return data


def _parse_curation(response: str, by_topic: dict[str, list[dict]]) -> list[dict]:
    """Parse the LLM's structured curation response into a list of chosen articles."""
    curated = []
    current_topic = None
    current_pick = 1
    current_insight = ""

    for line in response.splitlines():
        line = line.strip()
        if line.upper().startswith("TOPIC:"):
            # Save previous block before starting a new one
            if current_topic and current_topic in by_topic:
                articles = by_topic[current_topic]
                idx = max(0, min(current_pick - 1, len(articles) - 1))
                article = dict(articles[idx])
                article["insight"] = current_insight
                curated.append(article)
            # Look up topic name case-insensitively
            raw = line[6:].strip()
            match = next((t for t in by_topic if t.lower() == raw.lower()), raw)
            current_topic = match
            current_pick = 1
            current_insight = ""
        elif line.upper().startswith("PICK:"):
            try:
                current_pick = int(line[5:].strip())
            except ValueError:
                current_pick = 1
        elif line.upper().startswith("INSIGHT:"):
            current_insight = line[8:].strip()

    # Save the last block
    if current_topic and current_topic in by_topic:
        articles = by_topic[current_topic]
        idx = max(0, min(current_pick - 1, len(articles) - 1))
        article = dict(articles[idx])
        article["insight"] = current_insight
        curated.append(article)

    # Fill in any topics the LLM skipped — use top article, no insight
    covered = {a["topic"] for a in curated}
    for topic, articles in by_topic.items():
        if topic not in covered and articles:
            fallback = dict(articles[0])
            fallback["insight"] = ""
            curated.append(fallback)

    return curated


async def _curate_news(articles: list[dict]) -> list[dict]:
    """
    Feed Tavily articles to Ollama. LLM picks the best story per topic
    and writes a one-sentence insight. Returns curated list with insight field
    and URL grounded in real Tavily results.
    """
    if not articles:
        return []

    # Group by topic
    by_topic: dict[str, list[dict]] = {}
    for a in articles:
        by_topic.setdefault(a["topic"], []).append(a)

    # Build prompt — numbered articles per topic with truncated content
    topic_blocks = []
    for topic, topic_articles in by_topic.items():
        lines = [f"TOPIC: {topic}"]
        for i, a in enumerate(topic_articles, 1):
            content_preview = a.get("content", "")[:400].strip()
            lines.append(f"  [{i}] {a['title']}")
            if content_preview:
                lines.append(f"      {content_preview}")
        topic_blocks.append("\n".join(lines))

    prompt = (
        "You are a news editor. For each topic below, pick the single most newsworthy article "
        "and write one sentence explaining why it matters to a general reader. "
        "Be specific — reference the actual story, not generic statements.\n\n"
        "Reply in exactly this format for each topic:\n"
        "TOPIC: <name>\n"
        "PICK: <number>\n"
        "INSIGHT: <one sentence>\n\n"
        "---\n\n"
        + "\n\n".join(topic_blocks)
    )

    try:
        response = await llm_router.complete([
            {"role": "system", "content": "You are a news editor who picks the most important story per topic and explains its significance in one sentence."},
            {"role": "user", "content": prompt},
        ])
        return _parse_curation(response, by_topic)
    except Exception:
        # Fallback: return top article per topic with no insight
        return [dict(articles[0]) for articles in by_topic.values() if articles]


async def _generate_summary(data: dict, period: str) -> str:
    """Ask Ollama for a single-sentence highlight of the briefing. Returns '' on failure."""
    lines = []
    if data.get("weather"):
        w = data["weather"]
        lines.append(f"Weather: {w['description']}, {w['temp']}{w['unit']} in {w['city']}")
    if data.get("events"):
        titles = ", ".join(e["title"] for e in data["events"][:3])
        lines.append(f"Calendar: {titles}")
    if data.get("news"):
        top = data["news"][0]
        lines.append(f"Top story: {top.get('title', '')}")
    if data.get("reminders"):
        lines.append(f"Reminders: {len(data['reminders'])} pending")

    if not lines:
        return ""

    tone = {"morning": "energizing", "afternoon": "practical", "evening": "reflective", "night": "calm"}.get(period, "friendly")
    bullet_list = "\n".join(f"- {l}" for l in lines)
    prompt = (
        f"Write one short, {tone} sentence that highlights the most notable thing from this briefing. "
        f"Be specific — mention actual details, not generic statements. No filler like 'Here is your briefing'.\n\n"
        f"{bullet_list}"
    )

    try:
        return await llm_router.complete([
            {"role": "system", "content": "You write a single, specific sentence summarizing a briefing highlight."},
            {"role": "user", "content": prompt},
        ])
    except Exception:
        return ""


async def generate_on_demand_briefing(period: str) -> dict:
    """Return a structured briefing dict. Uses cached version if < 6 hours old."""
    cached = memory_service.get_recent_briefing(max_age_hours=6)
    if cached:
        try:
            parsed = json.loads(cached["content"])
            if "events" in parsed and "period" in parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    data = await collect_briefing_data(period)
    if data.get("news"):
        data["news"] = await _curate_news(data["news"])
    data["summary"] = await _generate_summary(data, period)
    memory_service.save_briefing(json.dumps(data))
    return data


async def generate_and_send_briefing():
    """Scheduled morning briefing: generates structured data, narrates via LLM, sends ntfy."""
    data = await collect_briefing_data("morning")
    if data.get("news"):
        data["news"] = await _curate_news(data["news"])

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
            f"  - {a['title']} — {a.get('insight', '')} ({a['source']})"
            for a in data["news"]
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
