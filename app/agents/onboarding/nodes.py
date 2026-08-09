from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.onboarding.prompts import ONBOARDING_DONE_MESSAGE, ONBOARDING_QUESTIONS, WELCOME_MESSAGE
from app.agents.onboarding.state import OnboardingState
from app.agents.onboarding.tools import is_skip, is_skip_all, parse_time_answer, split_list_answer
from app.models.notifications import CustomAlert, NotificationPreference
from app.models.preferences import UserPreference
from app.models.user import User
from app.models.watchlist import WatchlistItem


async def _get_or_create_prefs(db: AsyncSession, user_id) -> UserPreference:
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = UserPreference(user_id=user_id)
        db.add(prefs)
        await db.flush()
    return prefs


async def _get_or_create_notif(db: AsyncSession, user_id) -> NotificationPreference:
    result = await db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    notif = result.scalar_one_or_none()
    if not notif:
        notif = NotificationPreference(user_id=user_id)
        db.add(notif)
        await db.flush()
    return notif

async def save_answer(
    db: AsyncSession,
    user: User,
    step: int,
    text: str,
) -> None:
    question = ONBOARDING_QUESTIONS[step]
    field = question["field"]

    if field == "role":
        user.role = text.strip()

    elif field == "followed_companies":
        prefs = await _get_or_create_prefs(db, user.id)
        prefs.followed_companies = split_list_answer(text)

    elif field == "followed_markets":
        prefs = await _get_or_create_prefs(db, user.id)
        prefs.followed_markets = split_list_answer(text)

    elif field == "sectors":
        prefs = await _get_or_create_prefs(db, user.id)
        prefs.sectors = split_list_answer(text)

    elif field == "watchlist":
        for item in split_list_answer(text):
            db.add(
                WatchlistItem(
                    user_id=user.id,
                    symbol_or_topic=item,
                    item_type="ticker",
                )
            )

    elif field == "insight_types":
        prefs = await _get_or_create_prefs(db, user.id)
        prefs.insight_types = split_list_answer(text)

    elif field == "briefing_time":
        parsed = parse_time_answer(text)

        if parsed:
            notif = await _get_or_create_notif(db, user.id)
            notif.briefing_time = parsed

    elif field == "custom_alerts":
        for item in split_list_answer(text):
            db.add(
                CustomAlert(
                    user_id=user.id,
                    description=item,
                )
            )

async def run_onboarding_turn(db: AsyncSession, user: User, incoming_text: str) -> str:
    """Advance onboarding by exactly one turn and return the reply text.
    This is intentionally a plain function (called from the graph's single node) rather than
    spread across many graph nodes, since each Telegram message is a fresh invocation and
    the durable state already lives in Postgres via user.onboarding_state."""
    state = user.onboarding_state or {"step": 0, "completed": False, "skipped_all": False, "skipped_steps": []}
    step = state.get("step", 0)

    # First message of the flow (empty incoming_text signals "just started")
    if step == 0 and not incoming_text:
        await _get_or_create_prefs(db, user.id)
        await _get_or_create_notif(db, user.id)

        return (
            WELCOME_MESSAGE
            + "\n\n"
            + ONBOARDING_QUESTIONS[0]["question"]
        )
    
    if is_skip_all(incoming_text):
        await _get_or_create_prefs(db, user.id)
        await _get_or_create_notif(db, user.id)

        state["skipped_all"] = True
        state["completed"] = True
        state["step"] = len(ONBOARDING_QUESTIONS)

        user.onboarding_state = dict(state)

        return ONBOARDING_DONE_MESSAGE

    if step < len(ONBOARDING_QUESTIONS):
        if is_skip(incoming_text):
            state.setdefault("skipped_steps", []).append(ONBOARDING_QUESTIONS[step]["key"])
        else:
            await save_answer(db, user, step, incoming_text)

        step += 1
        state["step"] = step
        user.onboarding_state = state

        if step < len(ONBOARDING_QUESTIONS):
            return ONBOARDING_QUESTIONS[step]["question"]

        state["completed"] = True
        user.onboarding_state = state
        return ONBOARDING_DONE_MESSAGE

    state["completed"] = True
    user.onboarding_state = state
    return ONBOARDING_DONE_MESSAGE
