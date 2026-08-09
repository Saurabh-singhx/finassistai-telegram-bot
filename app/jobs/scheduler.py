from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.jobs.daily_briefing_job import run_due_briefings

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(run_due_briefings, IntervalTrigger(minutes=1), id="daily_briefings", replace_existing=True)
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
