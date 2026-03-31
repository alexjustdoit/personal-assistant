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


def _parse_summary(response: str) -> str:
    """Extract the SUMMARY line from the combined LLM response."""
    for line in response.splitlines():
        if line.strip().upper().startswith("SUMMARY:"):
            return line.strip()[8:].strip()
    return ""


async def _curate_and_summarize(data: dict, period: str) -> tuple[list[dict], str]:
    """
    Single Ollama call that:
    1. Picks the best news article per topic and writes a one-sentence insight
    2. Writes a one-sentence overall briefing summary

    Returns (curated_articles, summary_string).
    """
    articles = data.get("news", [])

    by_topic: dict[str, list[dict]] = {}
    for a in articles:
        by_topic.setdefault(a["topic"], []).append(a)

    # News blocks
    topic_blocks = []
    for topic, topic_articles in by_topic.items():
        lines = [f"TOPIC: {topic}"]
        for i, a in enumerate(topic_articles, 1):
            content_preview = a.get("content", "")[:400].strip()
            lines.append(f"  [{i}] {a['title']}")
            if content_preview:
                lines.append(f"      {content_preview}")
        topic_blocks.append("\n".join(lines))

    # Context for the summary sentence
    context_lines = []
    if data.get("weather"):
        w = data["weather"]
        context_lines.append(f"Weather: {w['description']}, {w['temp']}{w['unit']} in {w['city']}")
    if data.get("events"):
        titles = ", ".join(e["title"] for e in data["events"][:3])
        context_lines.append(f"Calendar: {titles}")
    if data.get("reminders"):
        context_lines.append(f"Reminders: {len(data['reminders'])} pending")

    tone = {"morning": "energizing", "afternoon": "practical", "evening": "reflective", "night": "calm"}.get(period, "friendly")

    prompt = (
        "Complete two tasks:\n\n"
        "TASK 1 — For each news topic, pick the single most newsworthy article and write one sentence "
        "explaining why it matters. Be specific — reference the actual story.\n\n"
        "TASK 2 — Write one short, " + tone + " sentence summarizing the most notable thing "
        "across the full briefing (news, weather, and calendar combined).\n\n"
        "Reply in exactly this format:\n"
        "TOPIC: <name>\n"
        "PICK: <number>\n"
        "INSIGHT: <one sentence>\n\n"
        "(repeat for each topic)\n\n"
        "SUMMARY: <one sentence overall highlight>\n\n"
        "---\n\n"
    )

    if topic_blocks:
        prompt += "NEWS ARTICLES:\n\n" + "\n\n".join(topic_blocks)

    if context_lines:
        prompt += "\n\nOTHER CONTEXT:\n" + "\n".join(f"- {l}" for l in context_lines)

    try:
        response = await llm_router.complete([
            {"role": "system", "content": "You are a news editor and briefing assistant. Follow the output format exactly."},
            {"role": "user", "content": prompt},
        ])
        curated = _parse_curation(response, by_topic) if by_topic else []
        summary = _parse_summary(response)
        return curated, summary
    except Exception:
        fallback = [dict(a_list[0]) for a_list in by_topic.values() if a_list]
        return fallback, ""


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
    data["news"], data["summary"] = await _curate_and_summarize(data, period)
    memory_service.save_briefing(json.dumps(data))
    return data


async def generate_and_send_briefing():
    """Scheduled morning briefing: generates structured data, narrates via LLM, sends ntfy."""
    data = await collect_briefing_data("morning")
    data["news"], _ = await _curate_and_summarize(data, "morning")

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
