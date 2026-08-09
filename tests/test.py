import asyncio
from app.services.market_data import finnhub_client, fred_client, sec_edgar
from app.services.rag_service import search_similar

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

async def run_tests():
    # Test get_stock_quote
    quote = await get_stock_quote("AAPL")
    print(f"Stock Quote for AAPL: {quote}")

    # Test get_company_news
    news = await get_company_news("AAPL")
    print(f"Company News for AAPL: {news}")

    # Test get_sec_filings
    filings = await get_sec_filings("AAPL")
    print(f"SEC Filings for AAPL: {filings}")

    # Test get_macro_series
    macro_data = await get_macro_series("CPIAUCSL")
    print(f"Macroeconomic Data for CPIAUCSL: {macro_data}")


asyncio.run(run_tests())