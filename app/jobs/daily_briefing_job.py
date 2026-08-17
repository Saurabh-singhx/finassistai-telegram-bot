import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import uuid

from sqlalchemy import select, update

from app.agents.briefing.graph import run_briefing
from app.config import settings
from app.database import AsyncSessionLocal
from app.jobs.utils import is_briefing_due
from app.models.notifications import NotificationPreference
from app.models.preferences import UserPreference
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.services import telegram_service

logger = logging.getLogger("finassist.jobs.briefing")


@dataclass
class BriefingCandidate:
    user_id: uuid.UUID
    telegram_id: int
    today_date_str: str
    sectors: list[str] = field(default_factory=list)
    followed_companies: list[str] = field(default_factory=list)
    followed_markets: list[str] = field(default_factory=list)
    insight_types: list[str] = field(default_factory=list)
    watchlist: list[str] = field(default_factory=list)


@dataclass
class BriefingJobMetrics:
    start_time: datetime
    end_time: datetime | None = None
    total_due: int = 0
    success_count: int = 0
    failure_count: int = 0
    duration_seconds: float = 0.0


# In-memory tracking of the last run metrics for monitoring/health checks
last_briefing_run_metrics: BriefingJobMetrics | None = None


async def fetch_due_briefing_candidates(
    now_utc: datetime | None = None,
    window_minutes: int | None = None,
) -> list[BriefingCandidate]:
    """
    Query the database for users whose daily briefing is due.

    Performs efficient joins, evaluates local timezone due times,
    and batch-loads active watchlists in a single query to eliminate N+1 DB calls.
    The database session is released immediately after candidate extraction.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if window_minutes is None:
        window_minutes = settings.BRIEFING_DISPATCH_WINDOW_MINUTES

    candidates: list[BriefingCandidate] = []

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User, NotificationPreference, UserPreference)
                .join(NotificationPreference, NotificationPreference.user_id == User.id)
                .outerjoin(UserPreference, UserPreference.user_id == User.id)
                .where(NotificationPreference.daily_briefing_enabled.is_(True))
            )
            rows = result.all()

            due_items: list[tuple[User, UserPreference | None, str]] = []
            due_user_ids: list[uuid.UUID] = []

            for user, notif, prefs in rows:
                try:
                    is_due, today_str = is_briefing_due(
                        briefing_time=notif.briefing_time,
                        user_tz_name=notif.timezone,
                        last_briefing_date=getattr(notif, "last_briefing_date", None),
                        now_utc=now_utc,
                        window_minutes=window_minutes,
                    )
                    if is_due:
                        due_items.append((user, prefs, today_str))
                        due_user_ids.append(user.id)
                except Exception:
                    logger.exception("Error evaluating briefing due status for user %s", user.id)

            if not due_items:
                return []

            # Batch load watchlists for all due users in a single query
            watchlists_by_user: dict[uuid.UUID, list[str]] = {uid: [] for uid in due_user_ids}
            watchlist_result = await db.execute(
                select(WatchlistItem.user_id, WatchlistItem.symbol_or_topic).where(
                    WatchlistItem.user_id.in_(due_user_ids),
                    WatchlistItem.active.is_(True),
                )
            )
            for uid, symbol in watchlist_result.all():
                if uid in watchlists_by_user:
                    watchlists_by_user[uid].append(symbol)

            # Build candidate objects
            for user, prefs, today_str in due_items:
                candidates.append(
                    BriefingCandidate(
                        user_id=user.id,
                        telegram_id=user.telegram_id,
                        today_date_str=today_str,
                        sectors=list(prefs.sectors) if prefs and prefs.sectors else [],
                        followed_companies=(
                            list(prefs.followed_companies) if prefs and prefs.followed_companies else []
                        ),
                        followed_markets=list(prefs.followed_markets) if prefs and prefs.followed_markets else [],
                        insight_types=list(prefs.insight_types) if prefs and prefs.insight_types else [],
                        watchlist=watchlists_by_user.get(user.id, []),
                    )
                )

    except Exception:
        logger.exception("Failed to fetch due briefing candidates from database")
        return []

    return candidates


async def _mark_briefing_delivered(
    user_id: uuid.UUID,
    today_date_str: str,
    sent_at: datetime,
) -> None:
    """Record briefing delivery in a dedicated, isolated database transaction."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(NotificationPreference)
                .where(NotificationPreference.user_id == user_id)
                .values(
                    last_briefing_sent_at=sent_at,
                    last_briefing_date=today_date_str,
                )
            )
            await db.commit()
    except Exception:
        logger.exception("Failed to update last_briefing_date for user %s", user_id)


async def process_single_briefing(
    candidate: BriefingCandidate,
    semaphore: asyncio.Semaphore,
) -> bool:
    """
    Generate and deliver a daily briefing to a single user with timeout and concurrency bounding.
    """
    async with semaphore:
        logger.info("Starting briefing generation for user %s (chat %s)", candidate.user_id, candidate.telegram_id)
        sent_at = datetime.now(timezone.utc)

        try:
            briefing_payload = {
                "user_id": str(candidate.user_id),
                "telegram_id": candidate.telegram_id,
                "sectors": candidate.sectors,
                "followed_companies": candidate.followed_companies,
                "followed_markets": candidate.followed_markets,
                "watchlist": candidate.watchlist,
                "insight_types": candidate.insight_types,
            }

            briefing_text = await asyncio.wait_for(
                run_briefing(briefing_payload),
                timeout=settings.BRIEFING_TIMEOUT_SECONDS,
            )

            if not briefing_text or not briefing_text.strip():
                logger.warning("Empty briefing text generated for user %s", candidate.user_id)
                return False

            await telegram_service.send_message(
                candidate.telegram_id,
                briefing_text,
            )

            await _mark_briefing_delivered(
                candidate.user_id,
                candidate.today_date_str,
                sent_at,
            )

            logger.info("Successfully delivered daily briefing to user %s", candidate.user_id)
            return True

        except asyncio.TimeoutError:
            logger.error(
                "Timed out generating briefing for user %s after %ds",
                candidate.user_id,
                settings.BRIEFING_TIMEOUT_SECONDS,
            )
            return False
        except Exception:
            logger.exception("Failed to generate or deliver briefing to user %s", candidate.user_id)
            return False


async def run_due_briefings() -> BriefingJobMetrics:
    """
    Scalable daily briefing job runner.

    Flow:
      1. Rapidly queries eligible candidates and batches their metadata.
      2. Immediately releases the discovery DB connection.
      3. Dispatches workers concurrently bounded by BRIEFING_CONCURRENCY_LIMIT.
      4. Tracks execution metrics and logs a structured execution summary.
    """
    global last_briefing_run_metrics

    start_time = datetime.now(timezone.utc)
    metrics = BriefingJobMetrics(start_time=start_time)

    try:
        candidates = await fetch_due_briefing_candidates(now_utc=start_time)
        metrics.total_due = len(candidates)

        if not candidates:
            metrics.end_time = datetime.now(timezone.utc)
            metrics.duration_seconds = (metrics.end_time - start_time).total_seconds()
            last_briefing_run_metrics = metrics
            return metrics

        logger.info("Found %d users due for daily briefing. Dispatching workers...", metrics.total_due)

        semaphore = asyncio.Semaphore(settings.BRIEFING_CONCURRENCY_LIMIT)
        tasks = [process_single_briefing(candidate, semaphore) for candidate in candidates]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if res is True:
                metrics.success_count += 1
            else:
                metrics.failure_count += 1

    except Exception:
        logger.exception("Unexpected error in run_due_briefings runner")

    metrics.end_time = datetime.now(timezone.utc)
    metrics.duration_seconds = (metrics.end_time - start_time).total_seconds()
    last_briefing_run_metrics = metrics

    logger.info(
        "Daily briefings job finished: %d due, %d succeeded, %d failed in %.2fs",
        metrics.total_due,
        metrics.success_count,
        metrics.failure_count,
        metrics.duration_seconds,
    )

    return metrics
