import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from backend.config import config


class SchedulerService:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()

    def start(self):
        cfg = config.get("briefing", {})
        tz_str = cfg.get("timezone", "UTC")
        tz = pytz.timezone(tz_str)

        # Morning briefing
        if cfg.get("enabled", False):
            time_str = cfg.get("time", "07:00")
            hour, minute = map(int, time_str.split(":"))
            self._scheduler.add_job(
                self._run_briefing,
                CronTrigger(hour=hour, minute=minute, timezone=tz),
                id="morning_briefing",
                replace_existing=True,
            )

        # Reminder check — every minute
        self._scheduler.add_job(
            self._check_reminders,
            IntervalTrigger(minutes=1),
            id="reminder_check",
            replace_existing=True,
        )

        self._scheduler.start()

    def stop(self):
        self._scheduler.shutdown(wait=False)

    async def _run_briefing(self):
        from backend.services.briefing import generate_and_send_briefing
        try:
            await generate_and_send_briefing()
        except Exception as e:
            print(f"[Briefing] Error: {e}")

    async def _check_reminders(self):
        from backend.services.memory import memory_service
        from backend.services.notifications import notification_service
        try:
            due = memory_service.get_due_reminders()
            for reminder in due:
                await notification_service.send(
                    title="Reminder",
                    body=reminder["text"],
                    priority="high",
                )
                memory_service.complete_reminder(reminder["id"])
        except Exception as e:
            print(f"[Reminders] Error: {e}")


scheduler_service = SchedulerService()
