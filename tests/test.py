import asyncio
from sqlalchemy import text
from websockets.version import tag
from app.services.market_data import finnhub_client, fred_client, sec_edgar
from app.services.rag_service import search_similar
from datetime import datetime, timezone
from app.services.google_oauth import get_user_google_credentials
from app.services.google_service import read_gmail_messages, create_calendar_event
from app.agents.chat.graph import run_chat_turn
from typing import Any
from app.services.market_data.finnhub_client import get_historical_prices
async def get_stock_quote(symbol: str) -> str:
    """Get the latest price quote for a stock ticker symbol, e.g. AAPL."""
    return await finnhub_client.get_quote(symbol)

async def get_company_news(symbol: str) -> str:
        """Get recent news headlines for a company ticker symbol."""
        return await finnhub_client.get_company_news(symbol)

async def get_sec_filings(company_or_ticker: str) -> str:

    """Get recent SEC filings (10-K, 10-Q, 8-K) for a company name or ticker."""
    return await sec_edgar.get_recent_filings(company_or_ticker)

async def get_macro_series(series_id: str) -> str:
    """Get a macroeconomic data series from FRED, e.g. 'CPIAUCSL' for CPI, 'UNRATE' for unemployment,
    'FEDFUNDS' for the fed funds rate."""
    return await fred_client.get_series(series_id)

async def search_my_documents(query: str) -> str:
    """Search the user's previously uploaded documents (PDFs, reports, transcribed voice notes) for
    relevant context using semantic search."""
    results = await search_similar(db, user_id=user_id, query=query, k=4)
    if not results:
        return "No relevant uploaded documents found."
    return "\n---\n".join(r.content[:800] for r in results)

async def tool_check(user_id: str) -> list[dict[str, Any]]:
    """Get recent messages for the user, if needed for context."""
    messages = await get_recent_messages_tool(user_id=user_id)
    return messages

async def search_gmail(
        query: str | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search and read the user's Gmail messages if they are connected.

        Use Gmail search syntax in `query`, for example:
        - is:unread
        - from:example@gmail.com
        - subject:invoice
        - has:attachment
        - newer_than:7d
        - is:unread from:example@gmail.com

        Returns full Gmail messages including headers, snippets, labels,
        and message payload data.
        """

        # await update_status(
        #     chat_id,
        #     status_message_id,
        #     f"📊 Searching Gmail messages...",
        # )
        credentials = await get_user_google_credentials("89144b23-0ed2-47d7-8dc8-de1cfb2a359a")

        messages =  read_gmail_messages(
            credentials,
            query=query,
            max_results=max_results,
        )

        # def clean_email_html(html: str) -> str:
        #     soup = BeautifulSoup(html, "html.parser")

        #     # Remove images and tracking pixels
        #     for tag in soup.find_all(["img", "svg", "script", "style"]):
        #         tag.decompose()

        #     # Remove links that are just tracking/redirect URLs
        #     for a in soup.find_all("a"):
        #         text = a.get_text(" ", strip=True)

        #         if text:
        #             a.replace_with(text)
        #         else:
        #             a.decompose()

        #     return soup.get_text(
        #     separator="\n",
        #     strip=True,
        # )

        for message in messages:
            print("\n--- EMAIL ---")
            print(f"From: {message['from']}")
            print(f"Subject: {message['subject']}")
            print(f"Date: {message['date']}")
            print()
            print(message)

async def create_tool_calendar_event(
        summary: str,
        start: dict[str, str],
        end: dict[str, str],
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create an event in the user's primary Google Calendar if they are connected.

        `start` and `end` must contain either:
        - dateTime: RFC3339 timestamp for a timed event
        - date: YYYY-MM-DD for an all-day event

        `attendees` should contain email addresses.
        """
        credentials = await get_user_google_credentials("89144b23-0ed2-47d7-8dc8-de1cfb2a359a")

        created_event =  create_calendar_event(
            credentials,
            summary=summary,
            start=start,
            end=end,
            description=description,
            location=location,
            attendees=attendees,
        )

        print("\n--- CALENDAR EVENT CREATED ---")
        print(f"Summary: {created_event['summary']}")
        print(f"Start: {created_event['start']}")
        print(f"End: {created_event['end']}")

def to_timestamp(date: str) -> int:
    return int(
        datetime.strptime(date, "%Y-%m-%d")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )

async def run_tests():
    # Test get_stock_quote
    quote = await get_stock_quote("TCS")
    print(f"Stock Quote for INFY: {quote}")

    # Test get_company_news
    news = await get_company_news("INFY")
    print(f"Company News for INFY: {news}")

    # Test get_sec_filings
    filings = await get_sec_filings("INFY")
    print(f"SEC Filings for INFY: {filings}")

    # Test get_macro_series
    macro_data = await get_macro_series("CPIAUCSL")
    print(f"Macroeconomic Data for CPIAUCSL: {macro_data}")

    historical_prices = await get_historical_prices(
        symbol="INFY.NS",
        start_timestamp=to_timestamp("2026-08-06"),
        end_timestamp=to_timestamp("2026-08-13"),
        resolution="D",
    )
    print(f"Historical Prices for INFY: {historical_prices}")

async def check_ai_response():
    # current_date_time = datetime.now(
    #     ZoneInfo("Asia/Kolkata")
    # ).strftime("%Y-%m-%d %H:%M:%S %z")

    response = await run_chat_turn(
        user_id="cd281dd1-b733-4975-9927-5fcf8a58d75c",
        thread_id="1825492294",
        user_context="google account connected : False",
        user_text="stock quote for hdfc",
        chat_id="",
        status_message_id="",
    )
    print(f"AI Response: {response}")
    # print(f"Current Date and Time in Asia/Kolkata timezone: {current_date_time}")

if __name__ == "__main__":
    asyncio.run(check_ai_response())