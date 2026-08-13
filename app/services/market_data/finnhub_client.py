import httpx
from app.config import settings
from app.services.market_data import alpha_vantage_client, fmp_client, polygon_client
from app.services.market_data.error_handling import return_unavailable
from app.services.market_data.historical_prices import format_bars, timestamp_to_date

BASE_URL = "https://finnhub.io/api/v1"


@return_unavailable("Finnhub")
async def get_quote(symbol: str) -> str:
    if not settings.FINNHUB_API_KEY:
        return "Finnhub API key not configured."
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BASE_URL}/quote", params={"symbol": symbol, "token": settings.FINNHUB_API_KEY})
        resp.raise_for_status()
        data = resp.json()
    if not data or data.get("c") in (None, 0):
        return f"No quote data found for {symbol}."
    change_pct = data.get("dp", 0)
    direction = "up" if change_pct >= 0 else "down"
    return f"{symbol}: ${data.get('c')} ({direction} {abs(change_pct):.2f}% today, prev close ${data.get('pc')})"


@return_unavailable("Finnhub")
async def get_company_news(symbol: str, limit: int = 5) -> str:
    if not settings.FINNHUB_API_KEY:
        return "Finnhub API key not configured."
    import datetime

    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/company-news",
            params={"symbol": symbol, "from": week_ago.isoformat(), "to": today.isoformat(), "token": settings.FINNHUB_API_KEY},
        )
        resp.raise_for_status()
        articles = resp.json()[:limit]
    if not articles:
        return f"No recent news for {symbol}."
    return "\n".join(f"- {a['headline']} ({a['source']})" for a in articles)

@return_unavailable("Finnhub")
async def get_historical_company_news(
    symbol: str,
    from_date: str,
    to_date: str,
    limit: int = 10,
) -> str:
    if not settings.FINNHUB_API_KEY:
        return "Finnhub API key not configured."

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/company-news",
            params={
                "symbol": symbol.upper(),
                "from": from_date,
                "to": to_date,
                "token": settings.FINNHUB_API_KEY,
            },
        )
        resp.raise_for_status()
        articles = resp.json()[:limit]

    if not articles:
        return f"No news found for {symbol} between {from_date} and {to_date}."

    return "\n".join(
        f"- {a.get('headline', 'No headline')} "
        f"({a.get('source', 'Unknown')}, {a.get('datetime', '')})"
        for a in articles
    )

@return_unavailable("Finnhub")
async def get_analyst_ratings(symbol: str) -> str:
    if not settings.FINNHUB_API_KEY:
        return "Finnhub API key not configured."
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BASE_URL}/stock/recommendation", params={"symbol": symbol, "token": settings.FINNHUB_API_KEY})
        resp.raise_for_status()
        data = resp.json()
    if not data:
        return f"No analyst ratings found for {symbol}."
    latest = data[0]
    return (
        f"{symbol} analyst ratings ({latest.get('period')}): "
        f"Buy {latest.get('buy')}, Hold {latest.get('hold')}, Sell {latest.get('sell')}, "
        f"Strong Buy {latest.get('strongBuy')}, Strong Sell {latest.get('strongSell')}"
    )

async def get_historical_prices(
    symbol: str,
    start_timestamp: int,
    end_timestamp: int,
    resolution: str = "D",
) -> str:
    """Fetch candles from Finnhub, with daily fallbacks for restricted plans."""
    from_date = timestamp_to_date(start_timestamp)
    to_date = timestamp_to_date(end_timestamp)
    errors = []

    if settings.FINNHUB_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{BASE_URL}/stock/candle",
                    params={
                        "symbol": symbol.upper(),
                        "resolution": resolution,
                        "from": start_timestamp,
                        "to": end_timestamp,
                        "token": settings.FINNHUB_API_KEY,
                    },
                )
                response.raise_for_status()
                data = response.json()

            if data.get("s") == "ok":
                bars = [
                    {
                        "date": timestamp_to_date(timestamp),
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "close": close_price,
                        "volume": volume,
                    }
                    for timestamp, open_price, high_price, low_price, close_price, volume in zip(
                        data.get("t", []), data.get("o", []), data.get("h", []),
                        data.get("l", []), data.get("c", []), data.get("v", []),
                    )
                ]
                result = format_bars(symbol, "Finnhub", bars)
                if result:
                    return result
        except httpx.HTTPStatusError as exc:
            errors.append(
                f"Finnhub HTTP {exc.response.status_code}: {exc.response.text}"
            )

        except (httpx.HTTPError, ValueError, TypeError) as exc:
            errors.append(f"Finnhub: {exc}")

    # Polygon supports the same aggregate-bar resolutions as this tool and is
    # the first fallback when Finnhub's plan rejects a candle request.
    try:
        result = await polygon_client.get_historical_prices(
            symbol, from_date, to_date, resolution
        )
        if result:
            return result
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        errors.append(f"Polygon: {exc.__class__.__name__}")

    # FMP and Alpha Vantage provide daily bars only through this fallback path.
    if resolution.upper() == "D":
        for provider, fetcher in (
            ("FMP", fmp_client.get_historical_prices),
            ("Alpha Vantage", alpha_vantage_client.get_daily_historical_prices),
        ):
            try:
                result = await fetcher(symbol, from_date, to_date)
                if result:
                    return result
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                errors.append(f"{provider}: {exc.__class__.__name__}")

    requested_resolution = resolution.upper()
    if requested_resolution != "D":
        return (
            f"Historical {requested_resolution} candles for {symbol.upper()} are unavailable. "
            "Finnhub denied the request, and the configured fallbacks support daily bars only."
        )
    return (
        f"Historical daily prices for {symbol.upper()} are unavailable from the configured providers. "
        f"Checked Finnhub, Polygon, FMP, and Alpha Vantage "
        f"({'; '.join(errors) or 'no data returned'})."
    )

@return_unavailable("Finnhub")
async def get_earnings_history(symbol: str, limit: int = 8) -> str:
    if not settings.FINNHUB_API_KEY:
        return "Finnhub API key not configured."

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/stock/earnings",
            params={
                "symbol": symbol.upper(),
                "token": settings.FINNHUB_API_KEY,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return f"No earnings history found for {symbol}."

    data = data[:limit]

    return "\n".join(
        f"{item.get('period')}: "
        f"actual EPS {item.get('actual')}, "
        f"estimate EPS {item.get('estimate')}, "
        f"surprise {item.get('surprise')}, "
        f"surprise % {item.get('surprisePercent')}"
        for item in data
    )

@return_unavailable("Finnhub")
async def get_reported_financials(
    symbol: str,
    limit: int = 4,
) -> str:
    if not settings.FINNHUB_API_KEY:
        return "Finnhub API key not configured."

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/stock/financials-reported",
            params={
                "symbol": symbol.upper(),
                "token": settings.FINNHUB_API_KEY,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return f"No reported financials found for {symbol}."

    return str(data)

@return_unavailable("Finnhub")
async def get_dividend_history(
    symbol: str,
    from_date: str,
    to_date: str,
) -> str:
    if not settings.FINNHUB_API_KEY:
        return "Finnhub API key not configured."

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/stock/dividend",
            params={
                "symbol": symbol.upper(),
                "from": from_date,
                "to": to_date,
                "token": settings.FINNHUB_API_KEY,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return f"No dividend history found for {symbol}."

    return "\n".join(
        f"{item.get('date')}: ${item.get('amount')}"
        for item in data
    )

@return_unavailable("Finnhub")
async def get_stock_splits(
    symbol: str,
    from_date: str,
    to_date: str,
) -> str:
    if not settings.FINNHUB_API_KEY:
        return "Finnhub API key not configured."

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/stock/split",
            params={
                "symbol": symbol.upper(),
                "from": from_date,
                "to": to_date,
                "token": settings.FINNHUB_API_KEY,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return f"No stock splits found for {symbol}."

    return "\n".join(
        f"{item.get('date')}: "
        f"{item.get('fromFactor')} → {item.get('toFactor')}"
        for item in data
    )
