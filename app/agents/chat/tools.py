"""Tools bound to the chat agent's LLM. Each wraps a service call and returns a compact string —
keep outputs short since they get re-read by the LLM and the LLM's reply has to stay short too."""
from langchain_core.tools import tool
from datetime import datetime, timedelta, timezone
from app.models.GoogleOAuthState import GoogleOAuthState
from app.services.google_oauth import get_authorization_url
from app.services.market_data import finnhub_client, fred_client, sec_edgar
from app.services.rag_service import search_similar
from app.services.telegram_service import update_status


def build_chat_tools(db, user_id: str, chat_id: int, status_message_id: int):
    
    @tool
    async def get_stock_quote(symbol: str) -> str:
        """Get the latest price quote for a stock ticker symbol, e.g. AAPL."""
        await update_status(chat_id,status_message_id,
            f"📈 Checking {symbol.upper()} stock price..."
        )
        return await finnhub_client.get_quote(symbol)

    @tool
    async def get_company_news(symbol: str) -> str:
        """Get recent news headlines for a company ticker symbol."""
        await update_status(chat_id,status_message_id,
            f"📰 Fetching news for {symbol.upper()}..."
        )
        return await finnhub_client.get_company_news(symbol)

    @tool
    async def get_sec_filings(company_or_ticker: str) -> str:
        """Get recent SEC filings (10-K, 10-Q, 8-K) for a company name or ticker."""
        await update_status(chat_id,status_message_id,
            f"📄 Fetching SEC filings for {company_or_ticker.upper()}..."
        )
        return await sec_edgar.get_recent_filings(company_or_ticker)

    @tool
    async def get_macro_series(series_id: str) -> str:
        """Get a macroeconomic data series from FRED, e.g. 'CPIAUCSL' for CPI, 'UNRATE' for unemployment,
        'FEDFUNDS' for the fed funds rate."""
        await update_status(chat_id,status_message_id,
            f"📊 Fetching macroeconomic data for {series_id.upper()}..."
        )
        return await fred_client.get_series(series_id)
    
    @tool
    async def get_finnhub_analyst_ratings(symbol: str) -> str:
        """Get analyst ratings for a stock ticker symbol, e.g. AAPL."""
        await update_status(chat_id,status_message_id,
            f"📈 Checking {symbol.upper()} analyst ratings..."
        )
        return await finnhub_client.get_analyst_ratings(symbol)

    @tool
    async def get_finhub_historical_company_news(symbol: str, from_date: str, to_date: str) -> str:
        """Get historical news for a company from Finnhub within a date range."""
        await update_status(chat_id,status_message_id,
            f"📰 Fetching historical news for {symbol.upper()}..."
        )
        return await finnhub_client.get_historical_company_news(symbol, from_date, to_date)
    
    @tool
    async def get_finhub_historical_prices(symbol: str, start_timestamp: int, end_timestamp: int, resolution: str) -> str:
        """Get historical stock prices for a company from Finnhub within a date range."""
        await update_status(chat_id,status_message_id,
            f"📈 Fetching historical prices for {symbol.upper()}..."
        )
        return await finnhub_client.get_historical_prices(symbol, start_timestamp, end_timestamp, resolution)

    @tool
    async def get_finhub_historical_earnings(symbol: str) -> str:
        """Get historical earnings for a company from Finnhub."""
        await update_status(chat_id,status_message_id,
            f"📈 Fetching historical earnings for {symbol.upper()}..."
        )
        return await finnhub_client.get_earnings_history(symbol)

    @tool
    async def get_finhub_reported_financials(symbol: str) -> str:
        """Get reported financials for a company from Finnhub."""
        await update_status(chat_id,status_message_id,
            f"📈 Fetching reported financials for {symbol.upper()}..."
        )
        return await finnhub_client.get_reported_financials(symbol)

    @tool
    async def get_finhub_dividend_history(symbol: str, from_date: str, to_date: str) -> str:
        """Get dividend history for a company from Finnhub."""
        await update_status(chat_id,status_message_id,
            f"📈 Fetching dividend history for {symbol.upper()}..."
        )
        return await finnhub_client.get_dividend_history(symbol, from_date, to_date)

    @tool
    async def get_finhub_stock_splits(symbol: str, from_date: str, to_date: str) -> str:
        """Get stock split history for a company from Finnhub."""
        await update_status(chat_id,status_message_id,
            f"📈 Fetching stock split history for {symbol.upper()}..."
        )
        return await finnhub_client.get_stock_splits(symbol, from_date, to_date)

    @tool
    async def search_my_documents(query: str) -> str:
        """Search the user's previously uploaded documents (PDFs, reports, transcribed voice notes) for
        relevant context using semantic search."""
        await update_status(chat_id,status_message_id,
            f"📄 Searching uploaded documents for '{query}'..."
        )
        results = await search_similar(db, user_id=user_id, query=query, k=4)
        if not results:
            return "No relevant uploaded documents found."
        return "\n---\n".join(r.content[:800] for r in results)

    @tool
    async def connect_google_account() -> str:
        """Connect the user's Google account for additional data access."""
        authorization_url, google_state, code_verifier = get_authorization_url()
        oauth_state = GoogleOAuthState(
            state=google_state, user_id=user_id,
            code_verifier=code_verifier,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.add(oauth_state)
        await db.commit()
        return f"Here is the Google authorization URL: {authorization_url}"

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
    ]
