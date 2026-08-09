"""Shared helpers for normalizing historical OHLCV data from multiple providers."""

from datetime import datetime, timezone
from typing import Any


MAX_RETURNED_BARS = 50


def timestamp_to_date(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


def format_bars(symbol: str, provider: str, bars: list[dict[str, Any]]) -> str | None:
    """Return a bounded, tool-friendly OHLCV representation sorted oldest first."""
    if not bars:
        return None

    bars = bars[-MAX_RETURNED_BARS:]
    lines = [f"{symbol.upper()} historical prices via {provider} ({len(bars)} bars):"]
    for bar in bars:
        date = bar.get("date") or bar.get("timestamp") or "unknown date"
        lines.append(
            f"- {date}: O {bar.get('open')}, H {bar.get('high')}, "
            f"L {bar.get('low')}, C {bar.get('close')}, V {bar.get('volume')}"
        )
    return "\n".join(lines)
