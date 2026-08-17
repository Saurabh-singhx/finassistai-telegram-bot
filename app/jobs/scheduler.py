import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.jobs.custom_alerts_job import last_alerts_run_metrics, run_custom_alerts
from app.jobs.daily_briefing_job import last_briefing_run_metrics, run_due_briefings

logger = logging.getLogger("finassist.jobs.scheduler")

_scheduler: AsyncIOScheduler | None = None


def _job_listener(event: JobExecutionEvent) -> None:
    """APScheduler event listener for monitoring job execution and failures."""
    if event.exception:
        logger.error(
            "Scheduler job '%s' raised an unhandled exception: %s",
            event.job_id,
            event.exception,
            exc_info=event.traceback,
        )
    elif event.code == EVENT_JOB_MISSED:
        logger.warning(
            "Scheduler job '%s' was missed at scheduled run time %s",
            event.job_id,
            event.scheduled_run_time,
        )
    elif event.code == EVENT_JOB_EXECUTED:
        logger.debug(
            "Scheduler job '%s' executed successfully at %s",
            event.job_id,
            event.scheduled_run_time,
        )


def start_scheduler(event_loop: asyncio.AbstractEventLoop | None = None) -> AsyncIOScheduler | None:
    """
    Configure, register jobs, and start the AsyncIO scheduler.
    """
    global _scheduler

    if not settings.SCHEDULER_ENABLED:
        logger.info("Background job scheduler is disabled via configuration.")
        return None

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler is already running.")
        return _scheduler

    try:
        loop = event_loop or asyncio.get_running_loop()
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

    job_defaults = {
        "misfire_grace_time": 300,  # 5 minutes grace time for delayed executions
        "coalesce": True,           # Combine overdue executions into a single run
        "max_instances": 1,          # Prevent overlapping runs of the same job
    }

    _scheduler = AsyncIOScheduler(event_loop=loop, job_defaults=job_defaults)


    # 1. Daily briefing job
    _scheduler.add_job(
        run_due_briefings,
        trigger=IntervalTrigger(minutes=settings.BRIEFING_JOB_INTERVAL_MINUTES),
        id="daily_briefings",
        name="Daily Briefing Poller",
        replace_existing=True,
    )
    logger.info(
        "Registered job 'daily_briefings' to run every %d minute(s).",
        settings.BRIEFING_JOB_INTERVAL_MINUTES,
    )

    # 2. Custom alerts job
    if settings.ALERTS_JOB_ENABLED:
        _scheduler.add_job(
            run_custom_alerts,
            trigger=IntervalTrigger(minutes=settings.ALERTS_JOB_INTERVAL_MINUTES),
            id="custom_alerts",
            name="Custom Price Alerts Checker",
            replace_existing=True,
        )
        logger.info(
            "Registered job 'custom_alerts' to run every %d minute(s).",
            settings.ALERTS_JOB_INTERVAL_MINUTES,
        )

    # Attach event listeners
    _scheduler.add_listener(
        _job_listener,
        EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_EXECUTED,
    )

    _scheduler.start()
    logger.info("Background job scheduler started successfully.")
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shutdown the scheduler if running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.info("Shutting down background job scheduler...")
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Background job scheduler stopped.")


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the active scheduler instance."""
    return _scheduler


def trigger_job(job_id: str) -> bool:
    """Manually trigger an immediate execution of a registered job."""
    if _scheduler is None or not _scheduler.running:
        logger.warning("Cannot trigger job '%s': scheduler is not running", job_id)
        return False

    job = _scheduler.get_job(job_id)
    if job is None:
        logger.warning("Job '%s' not found in scheduler", job_id)
        return False

    job.modify(next_run_time=datetime.now(timezone.utc))
    logger.info("Manually triggered execution for job '%s'", job_id)
    return True


def get_scheduler_status() -> dict[str, Any]:
    """Return health and status information for background jobs."""
    is_running = _scheduler is not None and _scheduler.running
    jobs_info = []

    if _scheduler and is_running:
        for job in _scheduler.get_jobs():
            jobs_info.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "pending": job.pending,
                }
            )

    return {
        "enabled": settings.SCHEDULER_ENABLED,
        "running": is_running,
        "jobs": jobs_info,
        "last_briefing_metrics": (
            {
                "start_time": last_briefing_run_metrics.start_time.isoformat(),
                "end_time": (
                    last_briefing_run_metrics.end_time.isoformat() if last_briefing_run_metrics.end_time else None
                ),
                "total_due": last_briefing_run_metrics.total_due,
                "success_count": last_briefing_run_metrics.success_count,
                "failure_count": last_briefing_run_metrics.failure_count,
                "duration_seconds": last_briefing_run_metrics.duration_seconds,
            }
            if last_briefing_run_metrics
            else None
        ),
        "last_alerts_metrics": (
            {
                "start_time": last_alerts_run_metrics.start_time.isoformat(),
                "end_time": (
                    last_alerts_run_metrics.end_time.isoformat() if last_alerts_run_metrics.end_time else None
                ),
                "total_active_alerts": last_alerts_run_metrics.total_active_alerts,
                "triggered_count": last_alerts_run_metrics.triggered_count,
                "failure_count": last_alerts_run_metrics.failure_count,
                "duration_seconds": last_alerts_run_metrics.duration_seconds,
            }
            if last_alerts_run_metrics
            else None
        ),
    }
