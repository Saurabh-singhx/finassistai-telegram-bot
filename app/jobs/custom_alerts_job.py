import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import re
import uuid

from sqlalchemy import select, update

from app.config import settings
from app.database import AsyncSessionLocal
from app.jobs.utils import chunk_list, safe_float
from app.models.notifications import CustomAlert
from app.models.user import User
from app.services import telegram_service
from app.services.market_data import finnhub_client

logger = logging.getLogger("finassist.jobs.alerts")


@dataclass
class AlertCandidate:
    alert_id: uuid.UUID
    user_id: uuid.UUID
    telegram_id: int
    description: str
    condition: dict = field(default_factory=dict)


@dataclass
class AlertJobMetrics:
    start_time: datetime
    end_time: datetime | None = None
    total_active_alerts: int = 0
    triggered_count: int = 0
    failure_count: int = 0
    duration_seconds: float = 0.0


last_alerts_run_metrics: AlertJobMetrics | None = None


def _parse_quote_details(quote_text: str) -> dict:
    """
    Parse price and change percentage from a standard quote string.
    Example: 'TSLA: $210.50 (down 5.20% today, prev close $222.00)'
    """
    details: dict = {"price": None, "change_pct": None, "raw": quote_text}
    if not quote_text:
        return details

    price_match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", quote_text)
    if price_match:
        details["price"] = safe_float(price_match.group(1))

    pct_match = re.search(r"(up|down)?\s*([0-9]+(?:\.[0-9]+)?)\%", quote_text, re.IGNORECASE)
    if pct_match:
        direction = pct_match.group(1)
        val = safe_float(pct_match.group(2))
        if val is not None:
            if direction and direction.lower() == "down":
                details["change_pct"] = -val
            else:
                details["change_pct"] = val

    return details


def evaluate_condition(condition: dict, quote_details: dict) -> tuple[bool, str]:
    """
    Evaluate if an alert condition is met based on current quote details.
    Returns (is_triggered, explanation).
    """
    if not condition:
        return False, ""

    c_type = (condition.get("type") or condition.get("operator") or "").lower()
    target_val = safe_float(condition.get("value") or condition.get("target_price") or condition.get("threshold"))
    current_price = quote_details.get("price")
    change_pct = quote_details.get("change_pct")

    if target_val is None:
        return False, ""

    if c_type in ("price_above", "above", "gt", ">"):
        if current_price is not None and current_price >= target_val:
            return True, f"Price reached ${current_price:.2f} (above threshold ${target_val:.2f})"

    elif c_type in ("price_below", "below", "lt", "<"):
        if current_price is not None and current_price <= target_val:
            return True, f"Price reached ${current_price:.2f} (below threshold ${target_val:.2f})"

    elif c_type in ("price_drop_pct", "drop_pct", "drop"):
        if change_pct is not None and change_pct <= -abs(target_val):
            return True, f"Price dropped {abs(change_pct):.2f}% today (threshold: {abs(target_val):.2f}%)"

    elif c_type in ("price_gain_pct", "gain_pct", "gain", "surge"):
        if change_pct is not None and change_pct >= abs(target_val):
            return True, f"Price surged {abs(change_pct):.2f}% today (threshold: {abs(target_val):.2f}%)"

    elif c_type in ("price_change_pct", "change_pct", "movement"):
        if change_pct is not None and abs(change_pct) >= abs(target_val):
            return True, f"Price moved {abs(change_pct):.2f}% today (threshold: {abs(target_val):.2f}%)"

    return False, ""


async def fetch_active_alert_candidates() -> list[AlertCandidate]:
    """Load active custom alerts with structured conditions and user contact info."""
    candidates: list[AlertCandidate] = []
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CustomAlert, User)
                .join(User, User.id == CustomAlert.user_id)
                .where(CustomAlert.active.is_(True))
            )
            rows = result.all()

            for alert, user in rows:
                candidates.append(
                    AlertCandidate(
                        alert_id=alert.id,
                        user_id=user.id,
                        telegram_id=user.telegram_id,
                        description=alert.description,
                        condition=alert.condition or {},
                    )
                )
    except Exception:
        logger.exception("Failed to fetch active alerts from database")

    return candidates


async def batch_fetch_quotes(symbols: set[str]) -> dict[str, dict]:
    """
    Fetch stock quotes for distinct symbols concurrently with rate bounding.
    Deduplicates symbols across all users so each symbol is fetched at most once.
    """
    quotes: dict[str, dict] = {}
    sem = asyncio.Semaphore(settings.ALERTS_CONCURRENCY_LIMIT)

    async def _fetch(symbol: str):
        async with sem:
            try:
                raw_quote = await finnhub_client.get_quote(symbol)
                quotes[symbol] = _parse_quote_details(raw_quote)
            except Exception:
                logger.exception("Failed to fetch quote for symbol '%s'", symbol)
                quotes[symbol] = {"price": None, "change_pct": None, "raw": ""}

    tasks = [_fetch(s) for s in symbols if s]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    return quotes


async def _mark_alert_triggered(alert_id: uuid.UUID, deactivate: bool = False) -> None:
    """Update alert trigger timestamp in database."""
    try:
        async with AsyncSessionLocal() as db:
            values: dict = {"last_triggered_at": datetime.now(timezone.utc)}
            if deactivate:
                values["active"] = False

            await db.execute(
                update(CustomAlert)
                .where(CustomAlert.id == alert_id)
                .values(**values)
            )
            await db.commit()
    except Exception:
        logger.exception("Failed to update trigger status for alert %s", alert_id)


async def run_custom_alerts() -> AlertJobMetrics:
    """
    Scalable background job for checking price and condition alerts.

    Optimizations:
      1. Loads active alerts and extracts required symbols.
      2. Batch-fetches symbol quotes once per distinct symbol (O(unique_symbols) API calls instead of O(alerts)).
      3. Evaluates conditions in-memory and dispatches triggered alerts.
      4. Tracks and logs performance metrics.
    """
    global last_alerts_run_metrics

    start_time = datetime.now(timezone.utc)
    metrics = AlertJobMetrics(start_time=start_time)

    try:
        candidates = await fetch_active_alert_candidates()
        metrics.total_active_alerts = len(candidates)

        if not candidates:
            metrics.end_time = datetime.now(timezone.utc)
            metrics.duration_seconds = (metrics.end_time - start_time).total_seconds()
            last_alerts_run_metrics = metrics
            return metrics

        # Extract symbols
        symbols_to_fetch: set[str] = set()
        for c in candidates:
            sym = c.condition.get("symbol") if isinstance(c.condition, dict) else None
            if sym:
                symbols_to_fetch.add(str(sym).strip().upper())

        quotes_by_symbol = await batch_fetch_quotes(symbols_to_fetch)

        # Evaluate and dispatch
        for candidate in candidates:
            try:
                sym = candidate.condition.get("symbol") if isinstance(candidate.condition, dict) else None
                sym = str(sym).strip().upper() if sym else None
                quote_details = quotes_by_symbol.get(sym, {}) if sym else {}

                is_triggered, explanation = evaluate_condition(candidate.condition, quote_details)

                if is_triggered:
                    message_text = (
                        f"🔔 Alert Triggered: {sym or 'Market Alert'}\n\n"
                        f"Condition: {candidate.description}\n"
                        f"Trigger: {explanation}\n"
                        f"Current Market Data: {quote_details.get('raw', 'N/A')}"
                    )

                    await telegram_service.send_message(
                        candidate.telegram_id,
                        message_text,
                    )

                    # Mark triggered (deactivate if specified as one-time)
                    is_one_time = candidate.condition.get("one_time", False)
                    await _mark_alert_triggered(candidate.alert_id, deactivate=is_one_time)
                    metrics.triggered_count += 1

            except Exception:
                logger.exception("Error evaluating custom alert %s", candidate.alert_id)
                metrics.failure_count += 1

    except Exception:
        logger.exception("Unexpected error in run_custom_alerts job")

    metrics.end_time = datetime.now(timezone.utc)
    metrics.duration_seconds = (metrics.end_time - start_time).total_seconds()
    last_alerts_run_metrics = metrics

    logger.info(
        "Custom alerts check finished: %d active alerts, %d triggered, %d failed in %.2fs",
        metrics.total_active_alerts,
        metrics.triggered_count,
        metrics.failure_count,
        metrics.duration_seconds,
    )

    return metrics
