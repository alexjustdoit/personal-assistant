import asyncio
import httpx
from datetime import date, datetime, time, timedelta
from backend.config import config


class CalendarService:
    def __init__(self):
        cfg = config.get("calendar", {})
        self.enabled = cfg.get("enabled", False)
        # Support ical_urls list (new) and ical_url singular (backward compat)
        urls = cfg.get("ical_urls") or []
        if not urls and cfg.get("ical_url"):
            urls = [cfg["ical_url"]]
        self.ical_urls: list[str] = [u for u in urls if u]

    async def _fetch_ical(self, client: httpx.AsyncClient, url: str) -> str | None:
        try:
            res = await client.get(url, timeout=10)
            res.raise_for_status()
            return res.text
        except Exception:
            return None

    async def get_events(self) -> list[dict]:
        """
        Returns events for the current viewing window:
        - Today: events whose end time is within the past hour or later
        - Tomorrow until noon: only shown after 6 PM today
        Each event includes status: past | current | upcoming | tomorrow
        Multiple iCal URLs are fetched in parallel and merged.
        """
        if not self.enabled or not self.ical_urls:
            return []

        import recurring_ical_events
        from icalendar import Calendar

        async with httpx.AsyncClient() as client:
            fetched = await asyncio.gather(*[self._fetch_ical(client, u) for u in self.ical_urls])

        # Parse all calendars
        calendars = []
        for ical_data in fetched:
            if ical_data:
                try:
                    calendars.append(Calendar.from_ical(ical_data))
                except Exception:
                    pass

        if not calendars:
            return []

        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        one_hour_ago = now - timedelta(hours=1)
        show_tomorrow = now.hour >= 18
        noon_tomorrow = datetime.combine(tomorrow, time(12, 0, 0))

        dates_to_fetch = [today] + ([tomorrow] if show_tomorrow else [])
        raw_events = []
        for cal in calendars:
            for fetch_date in dates_to_fetch:
                for event in recurring_ical_events.of(cal).at(fetch_date):
                    raw_events.append((fetch_date, event))

        result = []
        for fetch_date, event in raw_events:
            summary = str(event.get("SUMMARY", "Untitled"))
            dtstart = event.get("DTSTART").dt
            dtend_raw = event.get("DTEND", event.get("DTSTART")).dt
            is_allday = isinstance(dtstart, date) and not isinstance(dtstart, datetime)

            # Normalise to naive local datetimes for comparison
            if is_allday:
                start_dt = datetime.combine(dtstart, time(0, 0, 0))
                end_dt = datetime.combine(dtend_raw, time(0, 0, 0)) if isinstance(dtend_raw, date) and not isinstance(dtend_raw, datetime) else dtend_raw.astimezone().replace(tzinfo=None)
                start_str = "All day"
            else:
                start_dt = dtstart.astimezone().replace(tzinfo=None) if dtstart.tzinfo else dtstart
                end_dt = dtend_raw.astimezone().replace(tzinfo=None) if getattr(dtend_raw, "tzinfo", None) else dtend_raw
                start_str = start_dt.strftime("%I:%M %p").lstrip("0")

            is_tomorrow_event = fetch_date == tomorrow

            # Don't show events that ended more than 1 hour ago
            if end_dt < one_hour_ago:
                continue
            # Tomorrow events only up to noon
            if is_tomorrow_event and start_dt >= noon_tomorrow:
                continue

            if end_dt <= now:
                status = "past"
            elif start_dt <= now < end_dt:
                status = "current"
            elif is_tomorrow_event:
                status = "tomorrow"
            else:
                status = "upcoming"

            result.append({
                "title": summary,
                "start": start_str,
                "status": status,
                "is_allday": is_allday,
                "_sort": start_dt,
            })

        # Deduplicate by (title, start) in case same event appears in multiple calendars
        seen = set()
        deduped = []
        for e in result:
            key = (e["title"], e["start"])
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        result = deduped

        result.sort(key=lambda e: e["_sort"])
        for e in result:
            del e["_sort"]

        return result

    async def get_todays_events(self) -> list[dict]:
        return await self.get_events()


calendar_service = CalendarService()
