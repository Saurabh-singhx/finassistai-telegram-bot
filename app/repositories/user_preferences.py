import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preferences import UserPreference
from app.models.watchlist import WatchlistItem


async def get_user_financial_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """
    Fetch the user's financial preferences and watchlist.
    """

    preferences_result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == user_id
        )
    )

    preferences = preferences_result.scalar_one_or_none()

    watchlist_result = await db.execute(
        select(WatchlistItem)
        .where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.active.is_(True),
        )
        .order_by(WatchlistItem.created_at.desc())
    )

    watchlist = watchlist_result.scalars().all()

    return {
        "preferences": {
            "sectors": preferences.sectors if preferences else [],
            "followed_companies": (
                preferences.followed_companies
                if preferences
                else []
            ),
            "followed_markets": (
                preferences.followed_markets
                if preferences
                else []
            ),
            "insight_types": (
                preferences.insight_types
                if preferences
                else []
            ),
        },
        "watchlist": [
            {
                "id": str(item.id),
                "symbol_or_topic": item.symbol_or_topic,
                "item_type": item.item_type,
            }
            for item in watchlist
        ],
    }


async def update_user_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    sectors: list[str] | None = None,
    followed_companies: list[str] | None = None,
    followed_markets: list[str] | None = None,
    insight_types: list[str] | None = None,
) -> None:
    """
    Update only the preference fields that were provided.
    """

    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == user_id
        )
    )

    preferences = result.scalar_one_or_none()

    if not preferences:
        preferences = UserPreference(
            user_id=user_id,
        )
        db.add(preferences)

    if sectors is not None:
        preferences.sectors = sectors

    if followed_companies is not None:
        preferences.followed_companies = followed_companies

    if followed_markets is not None:
        preferences.followed_markets = followed_markets

    if insight_types is not None:
        preferences.insight_types = insight_types

    await db.commit()


async def add_watchlist_item(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol_or_topic: str,
    item_type: str = "ticker",
) -> WatchlistItem:
    """
    Add a stock/company/topic to the user's watchlist.
    """

    existing_result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.symbol_or_topic == symbol_or_topic,
        )
    )

    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.active = True
        existing.item_type = item_type

        await db.commit()
        await db.refresh(existing)

        return existing

    item = WatchlistItem(
        user_id=user_id,
        symbol_or_topic=symbol_or_topic,
        item_type=item_type,
        active=True,
    )

    db.add(item)

    await db.commit()
    await db.refresh(item)

    return item


async def remove_watchlist_item(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol_or_topic: str,
) -> bool:
    """
    Soft-delete an item from the watchlist.
    """

    result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.symbol_or_topic == symbol_or_topic,
            WatchlistItem.active.is_(True),
        )
    )

    item = result.scalar_one_or_none()

    if not item:
        return False

    item.active = False

    await db.commit()

    return True