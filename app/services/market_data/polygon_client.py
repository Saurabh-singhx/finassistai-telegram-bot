"""Polygon aggregate-bars fallback for historical OHLCV data."""

import httpx

from app.config import settings
from app.services.market_data.historical_prices import format_bars, timestamp_to_date

BASE_URL = "https://api.polygon.io"


def _resolution_parts(resolution: str) -> tuple[int, str] | None:
    normalized = resolution.upper()
    named = {"D": (1, "day"), "W": (1, "week"), "M": (1, "month")}
    if normalized in named:
        return named[normalized]
    if normalized.isdigit() and int(normalized) > 0:
        return int(normalized), "minute"
    return None


async def get_historical_prices(
    symbol: str,
    from_date: str,
    to_date: str,
    resolution: str,
) -> str | None:
    if not settings.POLYGON_API_KEY:
        return None
    interval = _resolution_parts(resolution)
    if not interval:
        return None

    multiplier, timespan = interval
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{BASE_URL}/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
            params={"adjusted": "true", "sort": "asc", "limit": 5000, "apiKey": settings.POLYGON_API_KEY},
        )
        response.raise_for_status()
        payload = response.json()
    
    rows = payload.get("results", [])
    if not isinstance(rows, list):
        return None
    bars = [
        {
            "date": timestamp_to_date(row["t"] // 1000),
            "open": row.get("o"),
            "high": row.get("h"),
            "low": row.get("l"),
            "close": row.get("c"),
            "volume": row.get("v"),
        }
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("t"), int)
    ]
    return format_bars(symbol, "Polygon", bars)
