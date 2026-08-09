import logging
from datetime import datetime

import pytz
from sqlalchemy import select

from app.agents.briefing.graph import run_briefing
from app.database import AsyncSessionLocal
from app.models.notifications import NotificationPreference
from app.models.preferences import UserPreference
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.services import telegram_service

logger = logging.getLogger("finassist.jobs.briefing")


async def run_due_briefings() -> None:
    """Runs every minute (see scheduler.py). Checks which users' briefing_time matches the
    current local time in their timezone, and sends them a briefing. Simple polling approach —
    fine at this scale, swap for per-user scheduled jobs if the user base grows large."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User, NotificationPreference, UserPreference)
                .join(NotificationPreference, NotificationPreference.user_id == User.id)
                .outerjoin(UserPreference, UserPreference.user_id == User.id)
                .where(NotificationPreference.daily_briefing_enabled.is_(True))
            )
            rows = result.all()

            for user, notif, prefs in rows:
                try:
                    tz = pytz.timezone(notif.timezone or "Asia/Kolkata")
                    now_local = datetime.now(tz)
                    if now_local.hour == notif.briefing_time.hour and now_local.minute == notif.briefing_time.minute:
                        await _send_briefing(db, user, prefs)
                except Exception:
                    logger.exception("Failed to create briefing for user %s", user.id)
    except Exception:
        logger.exception("Failed to run due briefings")


async def _send_briefing(
    db,
    user: User,
    prefs: UserPreference | None,
) -> None:

    watchlist_result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user.id,
            WatchlistItem.active.is_(True),
        )
    )

    watchlist = [
        w.symbol_or_topic
        for w in watchlist_result.scalars().all()
    ]

    try:
        briefing_text = await run_briefing(
            {
                "user_id": str(user.id),
                "telegram_id": user.telegram_id,

                "sectors": (
                    prefs.sectors
                    if prefs
                    else []
                ) or [],

                "followed_companies": (
                    prefs.followed_companies
                    if prefs
                    else []
                ) or [],

                "followed_markets": (
                    prefs.followed_markets
                    if prefs
                    else []
                ) or [],

                "watchlist": watchlist,

                "insight_types": (
                    prefs.insight_types
                    if prefs
                    else []
                ) or [],
            }
        )

        await telegram_service.send_message(
            user.telegram_id,
            briefing_text,
        )

    except Exception:
        logger.exception(
            "Failed to generate or send briefing to user %s",
            user.id,
        )
