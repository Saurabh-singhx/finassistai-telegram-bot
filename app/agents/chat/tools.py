"""Tools bound to the chat agent's LLM.

Tools should stay thin:
- validate/normalize tool input
- update user-facing status
- call service/repository functions
- return compact results

Database logic belongs in repositories/services.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from langchain_core.tools import tool

from app.models.GoogleOAuthState import GoogleOAuthState
from app.services.google_oauth import get_authorization_url
from app.services.market_data import (
    finnhub_client,
    fred_client,
    sec_edgar,
)
from app.services.rag_service import search_similar
from app.services.telegram_service import update_status

from app.repositories.user_preferences import (
    add_watchlist_item,
    get_user_financial_preferences,
    remove_watchlist_item,
    update_user_preferences,
)

from app.database import AsyncSessionLocal


def build_chat_tools(
    db,
    user_id: str,
    chat_id: int,
    status_message_id: int,
):
    user_uuid = UUID(user_id)

    @tool
    async def get_stock_quote(symbol: str) -> str:
        """Get the latest price quote for a stock ticker symbol, e.g. AAPL."""

        await update_status(
            chat_id,
            status_message_id,
            f"📈 Checking {symbol.upper()} stock price...",
        )

        return await finnhub_client.get_quote(symbol)

    @tool
    async def get_company_news(symbol: str) -> str:
        """Get recent news headlines for a company ticker symbol."""

        await update_status(
            chat_id,
            status_message_id,
            f"📰 Fetching news for {symbol.upper()}...",
        )

        return await finnhub_client.get_company_news(symbol)

    @tool
    async def get_sec_filings(company_or_ticker: str) -> str:
        """Get recent SEC filings such as 10-K, 10-Q and 8-K."""

        await update_status(
            chat_id,
            status_message_id,
            f"📄 Fetching SEC filings for {company_or_ticker.upper()}...",
        )

        return await sec_edgar.get_recent_filings(company_or_ticker)

    @tool
    async def get_macro_series(series_id: str) -> str:
        """Get a macroeconomic FRED series such as CPIAUCSL, UNRATE or FEDFUNDS."""

        await update_status(
            chat_id,
            status_message_id,
            f"📊 Fetching macroeconomic data for {series_id.upper()}...",
        )

        return await fred_client.get_series(series_id)

    @tool
    async def get_finnhub_analyst_ratings(symbol: str) -> str:
        """Get analyst ratings for a stock ticker."""

        await update_status(
            chat_id,
            status_message_id,
            f"📈 Checking {symbol.upper()} analyst ratings...",
        )

        return await finnhub_client.get_analyst_ratings(symbol)

    @tool
    async def get_finhub_historical_company_news(
        symbol: str,
        from_date: str,
        to_date: str,
    ) -> str:
        """Get historical company news within a date range."""

        await update_status(
            chat_id,
            status_message_id,
            f"📰 Fetching historical news for {symbol.upper()}...",
        )

        return await finnhub_client.get_historical_company_news(
            symbol,
            from_date,
            to_date,
        )

    @tool
    async def get_finhub_historical_prices(
        symbol: str,
        start_timestamp: int,
        end_timestamp: int,
        resolution: str,
    ) -> str:
        """Get historical stock prices for a company."""

        await update_status(
            chat_id,
            status_message_id,
            f"📈 Fetching historical prices for {symbol.upper()}...",
        )

        return await finnhub_client.get_historical_prices(
            symbol,
            start_timestamp,
            end_timestamp,
            resolution,
        )

    @tool
    async def get_finhub_historical_earnings(symbol: str) -> str:
        """Get historical earnings for a company."""

        await update_status(
            chat_id,
            status_message_id,
            f"📈 Fetching historical earnings for {symbol.upper()}...",
        )

        return await finnhub_client.get_earnings_history(symbol)

    @tool
    async def get_finhub_reported_financials(symbol: str) -> str:
        """Get reported financials for a company."""

        await update_status(
            chat_id,
            status_message_id,
            f"📊 Fetching reported financials for {symbol.upper()}...",
        )

        return await finnhub_client.get_reported_financials(symbol)

    @tool
    async def get_finhub_dividend_history(
        symbol: str,
        from_date: str,
        to_date: str,
    ) -> str:
        """Get dividend history for a company."""

        await update_status(
            chat_id,
            status_message_id,
            f"📈 Fetching dividend history for {symbol.upper()}...",
        )

        return await finnhub_client.get_dividend_history(
            symbol,
            from_date,
            to_date,
        )

    @tool
    async def get_finhub_stock_splits(
        symbol: str,
        from_date: str,
        to_date: str,
    ) -> str:
        """Get stock split history for a company."""

        await update_status(
            chat_id,
            status_message_id,
            f"📊 Fetching stock split history for {symbol.upper()}...",
        )

        return await finnhub_client.get_stock_splits(
            symbol,
            from_date,
            to_date,
        )

    @tool
    async def search_my_documents(query: str) -> str:
        """Search the user's uploaded documents for relevant information."""

        await update_status(
            chat_id,
            status_message_id,
            f"📄 Searching uploaded documents for '{query}'...",
        )

        results = await search_similar(
            db,
            user_id=user_uuid,
            query=query,
            k=4,
        )

        if not results:
            return "No relevant uploaded documents found."

        return "\n---\n".join(
            result.content[:800]
            for result in results
        )

    @tool
    async def connect_google_account() -> str:
        """Generate a Google OAuth authorization URL for the current user."""

        authorization_url, google_state, code_verifier = (
            get_authorization_url()
        )

        oauth_state = GoogleOAuthState(
            state=google_state,
            user_id=user_uuid,
            code_verifier=code_verifier,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=10)
            ),
        )

        db.add(oauth_state)
        await db.commit()

        return (
            "Google account connection required. "
            f"Authorize here: {authorization_url}"
        )

    @tool
    async def get_user_preferences() -> dict:
        """Get the current user's financial preferences and active watchlist."""

        return await get_user_financial_preferences(
            db,
            user_uuid,
        )

    @tool
    async def update_user_preferences(
        sectors: list[str] | None = None,
        followed_companies: list[str] | None = None,
        followed_markets: list[str] | None = None,
        insight_types: list[str] | None = None,
        add_watchlist: list[dict] | None = None,
        remove_watchlist: list[str] | None = None,
    ) -> str:
        """
        Update the current user's financial preferences and watchlist.

        Only explicitly provided preference fields are changed.

        add_watchlist example:
        {"symbol_or_topic": "AAPL", "item_type": "ticker"}

        item_type can be ticker, company, or topic.

        remove_watchlist contains the symbol/company/topic to remove.
        """

        await update_user_preferences(
            db,
            user_uuid,
            sectors=sectors,
            followed_companies=followed_companies,
            followed_markets=followed_markets,
            insight_types=insight_types,
        )

        for item in add_watchlist or []:
            await add_watchlist_item(
                db=db,
                user_id=user_uuid,
                symbol_or_topic=item["symbol_or_topic"],
                item_type=item.get("item_type", "ticker"),
            )

        for symbol_or_topic in remove_watchlist or []:
            await remove_watchlist_item(
                db=db,
                user_id=user_uuid,
                symbol_or_topic=symbol_or_topic,
            )

        return "User financial preferences updated successfully."

    return [
        get_stock_quote,
        get_company_news,
        get_sec_filings,
        get_macro_series,
        get_finnhub_analyst_ratings,
        get_finhub_historical_company_news,
        get_finhub_historical_prices,
        get_finhub_historical_earnings,
        get_finhub_reported_financials,
        get_finhub_dividend_history,
        get_finhub_stock_splits,
        search_my_documents,
        connect_google_account,
        get_user_preferences,
        update_user_preferences,
    ]