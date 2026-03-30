import httpx
from datetime import date, datetime, timezone
from backend.config import config


class CalendarService:
    def __init__(self):
        cfg = config.get("calendar", {})
        self.enabled = cfg.get("enabled", False)
        self.ical_url = cfg.get("ical_url", "")

    async def get_todays_events(self) -> list[dict]:
        if not self.enabled or not self.ical_url:
            return []
        async with httpx.AsyncClient() as client:
            res = await client.get(self.ical_url, timeout=10)
            res.raise_for_status()
            ical_data = res.text

        import recurring_ical_events
        from icalendar import Calendar

        cal = Calendar.from_ical(ical_data)
        today = date.today()
        events = recurring_ical_events.of(cal).at(today)

        result = []
        for event in events:
            summary = str(event.get("SUMMARY", "Untitled"))
            dtstart = event.get("DTSTART").dt
            dtend = event.get("DTEND", event.get("DTSTART")).dt

            # Normalize to datetime for consistent formatting
            if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
                start_str = "All day"
            else:
                if dtstart.tzinfo:
                    dtstart = dtstart.astimezone().replace(tzinfo=None)
                start_str = dtstart.strftime("%I:%M %p").lstrip("0")

            result.append({"title": summary, "start": start_str})

        result.sort(key=lambda e: e["start"])
        return result


calendar_service = CalendarService()
