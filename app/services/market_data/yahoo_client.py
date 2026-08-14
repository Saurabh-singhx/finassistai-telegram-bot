"""Historical OHLCV data for Indian NSE/BSE stocks using Yahoo Finance."""

import asyncio

import yfinance as yf

from app.services.market_data.historical_prices import (
    format_bars,
    timestamp_to_date,
)


def normalize_indian_symbol(symbol: str) -> str:
    """
    Convert an Indian stock symbol to Yahoo Finance format.

    Examples:
        TCS -> TCS.NS
        INFY -> INFY.NS
        RELIANCE -> RELIANCE.NS

    If .NS or .BO is already supplied, it is preserved.
    """
    symbol = symbol.upper().strip()

    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol

    return f"{symbol}.NS"


def _get_yahoo_interval(resolution: str) -> str | None:
    """
    Convert our resolution format to Yahoo Finance interval format.

    Supported:
        D -> 1d
        W -> 1wk
        M -> 1mo
    """
    return {
        "D": "1d",
        "W": "1wk",
        "M": "1mo",
    }.get(resolution.upper())


def _fetch_yahoo_history(
    yahoo_symbol: str,
    from_date: str,
    to_date: str,
    interval: str,
):
    """
    Synchronous yfinance call.

    This function is executed in a worker thread because yfinance
    is synchronous.
    """
    ticker = yf.Ticker(yahoo_symbol)

    return ticker.history(
        start=from_date,
        end=to_date,
        interval=interval,
        auto_adjust=False,
        actions=False,
    )


async def get_indian_historical_prices(
    symbol: str,
    start_timestamp: int,
    end_timestamp: int,
    resolution: str = "D",
) -> str | None:
    """
    Fetch historical OHLCV data for an Indian stock.

    Parameters
    ----------
    symbol:
        NSE/BSE symbol.

        Examples:
            TCS
            TCS.NS
            INFY
            INFY.NS
            RELIANCE
            RELIANCE.NS

    start_timestamp:
        Unix timestamp for the beginning of the requested range.

    end_timestamp:
        Unix timestamp for the end of the requested range.

    resolution:
        Supported:
            D = daily
            W = weekly
            M = monthly

    Returns
    -------
    str | None
        Formatted historical price data, or None if Yahoo returned
        no usable data.
    """

    if not symbol or not symbol.strip():
        raise ValueError("symbol must not be empty.")

    if start_timestamp >= end_timestamp:
        raise ValueError(
            "start_timestamp must be earlier than end_timestamp."
        )

    interval = _get_yahoo_interval(resolution)

    if interval is None:
        return (
            f"Indian historical prices with resolution "
            f"{resolution.upper()} are not supported. "
            "Supported resolutions are D, W, and M."
        )

    yahoo_symbol = normalize_indian_symbol(symbol)

    from_date = timestamp_to_date(start_timestamp)
    to_date = timestamp_to_date(end_timestamp)

    print(
        f"========== YAHOO INDIA ==========\n"
        f"SYMBOL: {yahoo_symbol}\n"
        f"FROM: {from_date}\n"
        f"TO: {to_date}\n"
        f"INTERVAL: {interval}"
    )

    try:
        dataframe = await asyncio.to_thread(
            _fetch_yahoo_history,
            yahoo_symbol,
            from_date,
            to_date,
            interval,
        )

    except Exception as exc:
        print(
            f"YAHOO ERROR for {yahoo_symbol}: "
            f"{exc.__class__.__name__}: {exc}"
        )
        return None

    if dataframe is None or dataframe.empty:
        print(f"YAHOO: No data returned for {yahoo_symbol}")
        return None

    bars = []

    for index, row in dataframe.iterrows():

        try:
            # Yahoo's index can be timezone-aware.
            # We only need the trading date.
            if hasattr(index, "strftime"):
                date = index.strftime("%Y-%m-%d")
            else:
                date = str(index)[:10]

            open_price = row.get("Open")
            high_price = row.get("High")
            low_price = row.get("Low")
            close_price = row.get("Close")
            volume = row.get("Volume")

            # Skip malformed rows.
            if (
                open_price is None
                or high_price is None
                or low_price is None
                or close_price is None
            ):
                continue

            bars.append(
                {
                    "date": date,
                    "open": float(open_price),
                    "high": float(high_price),
                    "low": float(low_price),
                    "close": float(close_price),
                    "volume": float(volume or 0),
                }
            )

        except (TypeError, ValueError):
            continue

    if not bars:
        print(f"YAHOO: No usable bars for {yahoo_symbol}")
        return None

    print(
        f"YAHOO RESULT: {yahoo_symbol} "
        f"({len(bars)} bars)"
    )

    for bar in bars[:5]:
        print(
            f"- {bar['date']}: "
            f"O {bar['open']}, "
            f"H {bar['high']}, "
            f"L {bar['low']}, "
            f"C {bar['close']}, "
            f"V {bar['volume']}"
        )

    return format_bars(
        symbol.upper(),
        "Yahoo Finance",
        bars,
    )

async def get_indian_quote(symbol: str) -> str | None:
    symbol = normalize_indian_symbol(symbol)

    try:
        def fetch():
            ticker = yf.Ticker(symbol)
            return ticker.history(period="1d", interval="1d")

        df = await asyncio.to_thread(fetch)

        if df.empty:
            return None

        row = df.iloc[-1]

        close = float(row["Close"])
        open_price = float(row["Open"])
        high = float(row["High"])
        low = float(row["Low"])
        volume = float(row["Volume"])

        change = close - open_price
        change_pct = (change / open_price) * 100 if open_price else 0

        direction = "up" if change_pct >= 0 else "down"

        return (
            f"{symbol}: ₹{close:.2f} "
            f"({direction} {abs(change_pct):.2f}% today, "
            f"open ₹{open_price:.2f}, "
            f"high ₹{high:.2f}, "
            f"low ₹{low:.2f}, "
            f"volume {volume:,.0f})"
        )

    except Exception as exc:
        print(f"YAHOO INDIA QUOTE ERROR: {exc}")
        return None