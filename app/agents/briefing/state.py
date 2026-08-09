from typing import TypedDict


class BriefingState(TypedDict, total=False):
    user_id: str
    telegram_id: int

    # User preferences
    sectors: list[str]
    followed_companies: list[str]
    followed_markets: list[str]

    # Specific assets being monitored
    watchlist: list[str]

    # Preferred briefing content
    insight_types: list[str]

    # Briefing pipeline data
    raw_data: str
    briefing_text: str
