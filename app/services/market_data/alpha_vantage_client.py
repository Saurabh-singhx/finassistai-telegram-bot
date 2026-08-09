"""Alpha Vantage fallback for daily historical prices."""

from datetime import date

import httpx

from app.config import settings
from app.services.market_data.historical_prices import format_bars

BASE_URL = "https://www.alphavantage.co/query"


async def get_daily_historical_prices(
    symbol: str,
    from_date: str,
    to_date: str,
) -> str | None:
    if not settings.ALPHA_VANTAGE_API_KEY:
        return None

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            BASE_URL,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol.upper(),
                "outputsize": "full",
                "apikey": settings.ALPHA_VANTAGE_API_KEY,
            },
        )
        response.raise_for_status()
        payload = response.json()

    # Alpha Vantage reports rate-limit and entitlement failures in a 200 response.
    series = payload.get("Time Series (Daily)", {})
    if not isinstance(series, dict):
        return None

    start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
    bars = []
    for bar_date, row in series.items():
        if not isinstance(row, dict) or not start <= date.fromisoformat(bar_date) <= end:
            continue
        bars.append(
            {
                "date": bar_date,
                "open": row.get("1. open"),
                "high": row.get("2. high"),
                "low": row.get("3. low"),
                "close": row.get("4. close"),
                "volume": row.get("5. volume"),
            }
        )

    bars.sort(key=lambda bar: bar["date"])
    return format_bars(symbol, "Alpha Vantage", bars)
