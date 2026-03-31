from backend.services.weather import weather_service
from backend.services.news import news_service
from backend.services.calendar_service import calendar_service
from backend.services.notifications import notification_service
from backend.services.memory import memory_service
from backend.services.llm import llm_router


async def generate_and_send_briefing():
    sections = []

    # Weather
    try:
        weather = await weather_service.get()
        if weather:
            sections.append(f"Weather: {weather_service.format(weather)}")
    except Exception:
        pass

    # Calendar
    try:
        events = await calendar_service.get_todays_events()
        if events:
            event_lines = "\n".join(f"  - {e['start']}: {e['title']}" for e in events)
            sections.append(f"Calendar ({len(events)} events today):\n{event_lines}")
        else:
            sections.append("Calendar: No events today")
    except Exception:
        pass

    # News
    try:
        headlines = await news_service.get_digest()
        if headlines:
            headline_lines = "\n".join(f"  - {h}" for h in headlines)
            sections.append(f"News highlights:\n{headline_lines}")
    except Exception:
        pass

    # Reminders
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

    if not sections:
        return

    data_block = "\n\n".join(sections)
    prompt = f"""You are delivering a friendly morning briefing. Be warm, concise, and conversational — write it as a natural paragraph, not a list.

Data:
{data_block}

Write the morning briefing:"""

    briefing_text = await llm_router.complete([
        {"role": "system", "content": "You deliver friendly, concise morning briefings."},
        {"role": "user", "content": prompt},
    ])

    memory_service.save_briefing(briefing_text)

    await notification_service.send(
        title="Good morning!",
        body=briefing_text,
    )
