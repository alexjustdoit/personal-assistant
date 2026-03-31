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
                self._run_morning_briefing,
                CronTrigger(hour=hour, minute=minute, timezone=tz),
                id="morning_briefing",
                replace_existing=True,
            )

        # Evening briefing
        if cfg.get("evening_enabled", False):
            time_str = cfg.get("evening_time", "18:00")
            hour, minute = map(int, time_str.split(":"))
            self._scheduler.add_job(
                self._run_evening_briefing,
                CronTrigger(hour=hour, minute=minute, timezone=tz),
                id="evening_briefing",
                replace_existing=True,
            )

        # Reminder check — every minute
        self._scheduler.add_job(
            self._check_reminders,
            IntervalTrigger(minutes=1),
            id="reminder_check",
            replace_existing=True,
        )

        # Activity tracking
        act_cfg = config.get("activity_tracking", {})
        if act_cfg.get("enabled") and act_cfg.get("log_folder"):
            interval = int(act_cfg.get("poll_interval_minutes", 30))
            self._scheduler.add_job(
                self._poll_activity,
                IntervalTrigger(minutes=interval),
                id="activity_poll",
                replace_existing=True,
            )
            eod_time = act_cfg.get("eod_summary_time", "22:00")
            eod_hour, eod_minute = map(int, eod_time.split(":"))
            self._scheduler.add_job(
                self._run_eod_summary,
                CronTrigger(hour=eod_hour, minute=eod_minute, timezone=tz),
                id="eod_summary",
                replace_existing=True,
            )

        self._scheduler.start()

    def stop(self):
        self._scheduler.shutdown(wait=False)

    async def _run_morning_briefing(self):
        from backend.services.briefing import generate_and_send_briefing
        try:
            await generate_and_send_briefing(period="morning")
        except Exception as e:
            print(f"[Briefing] Morning error: {e}")

    async def _run_evening_briefing(self):
        from backend.services.briefing import generate_and_send_briefing
        try:
            await generate_and_send_briefing(period="evening")
        except Exception as e:
            print(f"[Briefing] Evening error: {e}")

    async def _poll_activity(self):
        import asyncio
        from backend.services.activity_tracker import write_activity_log
        act_cfg = config.get("activity_tracking", {})
        interval = int(act_cfg.get("poll_interval_minutes", 30))
        try:
            await asyncio.to_thread(write_activity_log, act_cfg["log_folder"], interval)
        except Exception as e:
            print(f"[ActivityTracker] Poll error: {e}")

    async def _run_eod_summary(self):
        from backend.services.activity_tracker import synthesize_day
        act_cfg = config.get("activity_tracking", {})
        try:
            summary = await synthesize_day(act_cfg["log_folder"])
            if summary:
                from backend.services.notifications import notification_service
                await notification_service.send(
                    title="Day Summary ready",
                    body="Your daily activity summary has been saved.",
                )
        except Exception as e:
            print(f"[ActivityTracker] EOD summary error: {e}")

    async def _check_reminders(self):
        import asyncio
        from backend.services.memory import memory_service
        from backend.services.notifications import notification_service
        try:
            due = await asyncio.to_thread(memory_service.get_due_reminders)
            for reminder in due:
                await notification_service.send(
                    title="Reminder",
                    body=reminder["text"],
                    priority="high",
                )
                await asyncio.to_thread(memory_service.complete_reminder, reminder["id"])
        except Exception as e:
            print(f"[Reminders] Error: {e}")


scheduler_service = SchedulerService()
