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
        data["weather"] = weather  # already a clean dict or None
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
        lines.append(f"Top story: {data['news'][0]['title']}")
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
            # old format (missing structured fields) — fall through and regenerate
        except (json.JSONDecodeError, TypeError):
            pass  # plain text briefing — regenerate

    data = await collect_briefing_data(period)
    data["summary"] = await _generate_summary(data, period)
    memory_service.save_briefing(json.dumps(data))
    return data


async def generate_and_send_briefing():
    """Scheduled morning briefing: generates structured data, narrates via LLM, sends ntfy."""
    data = await collect_briefing_data("morning")

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
        lines = "\n".join(f"  - {a['title']} ({a['source']})" for a in data["news"])
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

    # Save structured data to DB (home page will use this)
    memory_service.save_briefing(json.dumps(data))

    await notification_service.send(
        title="Good morning!",
        body=briefing_text,
    )
