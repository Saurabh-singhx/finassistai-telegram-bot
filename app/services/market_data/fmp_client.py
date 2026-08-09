"""Financial Modeling Prep fallbacks for market-data endpoints."""

from datetime import date

import httpx

from app.config import settings
from app.services.market_data.historical_prices import format_bars

BASE_URL = "https://financialmodelingprep.com/stable"


async def get_historical_prices(
    symbol: str,
    from_date: str,
    to_date: str,
) -> str | None:
    """Fetch daily historical OHLCV data, returning None when FMP cannot provide it."""
    if not settings.FMP_API_KEY:
        return None

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{BASE_URL}/historical-price-eod/full",
            params={"symbol": symbol.upper(), "apikey": settings.FMP_API_KEY},
        )
        response.raise_for_status()
        payload = response.json()

    # FMP's legacy endpoint returns {"historical": [...]}; the stable endpoint
    # may return the row list directly. Support both shapes.
    rows = payload.get("historical", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return None

    start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
    bars = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("date"):
            continue
        row_date = date.fromisoformat(row["date"])
        if start <= row_date <= end:
            bars.append(
                {
                    "date": row["date"],
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                }
            )

    bars.sort(key=lambda bar: bar["date"])
    return format_bars(symbol, "FMP", bars)
