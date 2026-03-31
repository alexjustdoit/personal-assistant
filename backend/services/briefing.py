from backend.services.weather import weather_service
from backend.services.news import news_service
from backend.services.calendar_service import calendar_service
from backend.services.notifications import notification_service
from backend.services.memory import memory_service
from backend.services.llm import llm_router

PERIOD_PROMPTS = {
    "morning": (
        "You are delivering a friendly morning briefing. Be warm, energizing, and conversational — "
        "write it as a natural paragraph, not a list."
    ),
    "afternoon": (
        "You are delivering a midday check-in. Be concise, practical, and upbeat — "
        "write it as a natural paragraph, not a list."
    ),
    "evening": (
        "You are delivering an evening briefing. Be warm and reflective in tone — "
        "write it as a natural paragraph, not a list."
    ),
    "night": (
        "You are delivering a late-night overview. Be brief and calm — "
        "write it as a natural paragraph, not a list."
    ),
}

PERIOD_SYSTEM = {
    "morning": "You deliver friendly, energizing morning briefings.",
    "afternoon": "You deliver concise, practical midday check-ins.",
    "evening": "You deliver warm, reflective evening briefings.",
    "night": "You deliver brief, calm late-night overviews.",
}


async def _collect_sections() -> list[str]:
    """Gather data sections shared by both briefing functions."""
    sections = []

    try:
        weather = await weather_service.get()
        if weather:
            sections.append(f"Weather: {weather_service.format(weather)}")
    except Exception:
        pass

    try:
        events = await calendar_service.get_todays_events()
        if events:
            event_lines = "\n".join(f"  - {e['start']}: {e['title']}" for e in events)
            sections.append(f"Calendar ({len(events)} events today):\n{event_lines}")
        else:
            sections.append("Calendar: No events today")
    except Exception:
        pass

    try:
        headlines = await news_service.get_digest()
        if headlines:
            headline_lines = "\n".join(f"  - {h}" for h in headlines)
            sections.append(f"News highlights:\n{headline_lines}")
    except Exception:
        pass

    try:
        reminders = memory_service.get_pending_reminders()
        if reminders:
            reminder_lines = "\n".join(
                f"  - {r['text']}" + (f" (due: {r['due_time']})" if r.get("due_time") else "")
                for r in reminders
            )
            sections.append(f"Reminders:\n{reminder_lines}")
    except Exception:
        pass

    return sections


async def generate_on_demand_briefing(period: str) -> str:
    """Generate a time-of-day-aware briefing. Returns cached if < 6 hours old."""
    cached = memory_service.get_recent_briefing(max_age_hours=6)
    if cached:
        return cached["content"]

    sections = await _collect_sections()
    if not sections:
        return ""

    instruction = PERIOD_PROMPTS.get(period, PERIOD_PROMPTS["morning"])
    system = PERIOD_SYSTEM.get(period, PERIOD_SYSTEM["morning"])
    data_block = "\n\n".join(sections)

    prompt = f"""{instruction}

Data:
{data_block}

Write the briefing:"""

    briefing_text = await llm_router.complete([
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ])

    memory_service.save_briefing(briefing_text)
    return briefing_text


async def generate_and_send_briefing():
    sections = await _collect_sections()
    if not sections:
        return

    data_block = "\n\n".join(sections)
    prompt = f"""{PERIOD_PROMPTS["morning"]}

Data:
{data_block}

Write the morning briefing:"""

    briefing_text = await llm_router.complete([
        {"role": "system", "content": PERIOD_SYSTEM["morning"]},
        {"role": "user", "content": prompt},
    ])

    memory_service.save_briefing(briefing_text)

    await notification_service.send(
        title="Good morning!",
        body=briefing_text,
    )
