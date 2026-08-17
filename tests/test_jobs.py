import asyncio
from datetime import datetime, time, timezone
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.jobs.custom_alerts_job import (
    AlertCandidate,
    _parse_quote_details,
    batch_fetch_quotes,
    evaluate_condition,
    run_custom_alerts,
)
from app.jobs.daily_briefing_job import (
    BriefingCandidate,
    fetch_due_briefing_candidates,
    process_single_briefing,
    run_due_briefings,
)
from app.jobs.scheduler import get_scheduler, get_scheduler_status, start_scheduler, stop_scheduler, trigger_job
from app.jobs.utils import chunk_list, get_safe_timezone, is_briefing_due, safe_float


class TestJobUtils(unittest.TestCase):
    def test_get_safe_timezone(self):
        tz = get_safe_timezone("America/New_York")
        self.assertEqual(str(tz), "America/New_York")

        tz_invalid = get_safe_timezone("Invalid/NonExistent_Zone")
        self.assertEqual(str(tz_invalid), "Asia/Kolkata")

        tz_none = get_safe_timezone(None)
        self.assertEqual(str(tz_none), "Asia/Kolkata")

    def test_is_briefing_due_at_exact_time(self):
        # 08:00 AM briefing time in Asia/Kolkata (+05:30)
        # 08:00 IST is 02:30 UTC
        now_utc = datetime(2026, 8, 17, 2, 30, 0, tzinfo=timezone.utc)
        briefing_time = time(8, 0)

        is_due, today_str = is_briefing_due(
            briefing_time=briefing_time,
            user_tz_name="Asia/Kolkata",
            last_briefing_date=None,
            now_utc=now_utc,
            window_minutes=120,
        )
        self.assertTrue(is_due)
        self.assertEqual(today_str, "2026-08-17")

    def test_is_briefing_due_within_catchup_window(self):
        # 08:45 IST is 03:15 UTC (45 minutes after 08:00 scheduled time)
        now_utc = datetime(2026, 8, 17, 3, 15, 0, tzinfo=timezone.utc)
        briefing_time = time(8, 0)

        is_due, today_str = is_briefing_due(
            briefing_time=briefing_time,
            user_tz_name="Asia/Kolkata",
            last_briefing_date=None,
            now_utc=now_utc,
            window_minutes=120,
        )
        self.assertTrue(is_due)
        self.assertEqual(today_str, "2026-08-17")

    def test_is_briefing_not_due_before_time(self):
        # 07:45 IST is 02:15 UTC (15 minutes before 08:00 scheduled time)
        now_utc = datetime(2026, 8, 17, 2, 15, 0, tzinfo=timezone.utc)
        briefing_time = time(8, 0)

        is_due, today_str = is_briefing_due(
            briefing_time=briefing_time,
            user_tz_name="Asia/Kolkata",
            last_briefing_date=None,
            now_utc=now_utc,
            window_minutes=120,
        )
        self.assertFalse(is_due)
        self.assertEqual(today_str, "2026-08-17")

    def test_is_briefing_not_due_after_window_expired(self):
        # 11:30 IST is 06:00 UTC (3.5 hours after 08:00, window is 2 hours)
        now_utc = datetime(2026, 8, 17, 6, 0, 0, tzinfo=timezone.utc)
        briefing_time = time(8, 0)

        is_due, today_str = is_briefing_due(
            briefing_time=briefing_time,
            user_tz_name="Asia/Kolkata",
            last_briefing_date=None,
            now_utc=now_utc,
            window_minutes=120,
        )
        self.assertFalse(is_due)
        self.assertEqual(today_str, "2026-08-17")

    def test_is_briefing_idempotency_same_day(self):
        # Even if time matches, if last_briefing_date == today, should NOT run again
        now_utc = datetime(2026, 8, 17, 2, 30, 0, tzinfo=timezone.utc)
        briefing_time = time(8, 0)

        is_due, today_str = is_briefing_due(
            briefing_time=briefing_time,
            user_tz_name="Asia/Kolkata",
            last_briefing_date="2026-08-17",
            now_utc=now_utc,
            window_minutes=120,
        )
        self.assertFalse(is_due)
        self.assertEqual(today_str, "2026-08-17")

    def test_chunk_list(self):
        items = list(range(10))
        chunks = list(chunk_list(items, 3))
        self.assertEqual(chunks, [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]])

    def test_safe_float(self):
        self.assertEqual(safe_float("123.45"), 123.45)
        self.assertEqual(safe_float(42), 42.0)
        self.assertIsNone(safe_float("invalid"))
        self.assertIsNone(safe_float(None))


class TestDailyBriefingJob(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_due_briefing_candidates_batching(self):
        user_id_1 = uuid.uuid4()
        user_id_2 = uuid.uuid4()

        user1 = MagicMock(id=user_id_1, telegram_id=111)
        notif1 = MagicMock(
            briefing_time=time(8, 0),
            timezone="Asia/Kolkata",
            last_briefing_date=None,
        )
        prefs1 = MagicMock(
            sectors=["Technology"],
            followed_companies=["AAPL"],
            followed_markets=["US"],
            insight_types=["earnings"],
        )

        user2 = MagicMock(id=user_id_2, telegram_id=222)
        notif2 = MagicMock(
            briefing_time=time(8, 0),
            timezone="Asia/Kolkata",
            last_briefing_date="2026-08-17",  # already sent
        )
        prefs2 = MagicMock(sectors=[], followed_companies=[], followed_markets=[], insight_types=[])

        # DB session mock
        session = AsyncMock()
        first_result = MagicMock()
        first_result.all.return_value = [(user1, notif1, prefs1), (user2, notif2, prefs2)]

        watchlist_result = MagicMock()
        watchlist_result.all.return_value = [(user_id_1, "AAPL"), (user_id_1, "MSFT")]

        session.execute.side_effect = [first_result, watchlist_result]

        session_ctx = MagicMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=None)

        now_utc = datetime(2026, 8, 17, 2, 30, 0, tzinfo=timezone.utc)

        with patch("app.jobs.daily_briefing_job.AsyncSessionLocal", return_value=session_ctx):
            candidates = await fetch_due_briefing_candidates(now_utc=now_utc)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].user_id, user_id_1)
        self.assertEqual(candidates[0].telegram_id, 111)
        self.assertEqual(candidates[0].watchlist, ["AAPL", "MSFT"])
        self.assertEqual(candidates[0].sectors, ["Technology"])

    async def test_process_single_briefing_success(self):
        user_id = uuid.uuid4()
        candidate = BriefingCandidate(
            user_id=user_id,
            telegram_id=999,
            today_date_str="2026-08-17",
            sectors=["Finance"],
            watchlist=["JPM"],
        )

        semaphore = asyncio.Semaphore(5)

        with (
            patch("app.jobs.daily_briefing_job.run_briefing", new=AsyncMock(return_value="Market summary today")),
            patch("app.jobs.daily_briefing_job.telegram_service.send_message", new=AsyncMock(return_value=True)) as send_mock,
            patch("app.jobs.daily_briefing_job._mark_briefing_delivered", new=AsyncMock()) as mark_mock,
        ):
            success = await process_single_briefing(candidate, semaphore)

        self.assertTrue(success)
        send_mock.assert_awaited_once_with(999, "Market summary today")
        mark_mock.assert_awaited_once()

    async def test_process_single_briefing_timeout_handling(self):
        user_id = uuid.uuid4()
        candidate = BriefingCandidate(
            user_id=user_id,
            telegram_id=999,
            today_date_str="2026-08-17",
        )
        semaphore = asyncio.Semaphore(5)

        async def slow_briefing(*args, **kwargs):
            await asyncio.sleep(5)
            return "Late text"

        with (
            patch("app.jobs.daily_briefing_job.run_briefing", side_effect=slow_briefing),
            patch.object(daily_briefing_job.settings, "BRIEFING_TIMEOUT_SECONDS", 0.01),
        ):
            success = await process_single_briefing(candidate, semaphore)

        self.assertFalse(success)

    async def test_run_due_briefings_flow(self):
        candidates = [
            BriefingCandidate(user_id=uuid.uuid4(), telegram_id=1, today_date_str="2026-08-17"),
            BriefingCandidate(user_id=uuid.uuid4(), telegram_id=2, today_date_str="2026-08-17"),
        ]

        with (
            patch("app.jobs.daily_briefing_job.fetch_due_briefing_candidates", new=AsyncMock(return_value=candidates)),
            patch("app.jobs.daily_briefing_job.process_single_briefing", new=AsyncMock(side_effect=[True, False])),
        ):
            metrics = await run_due_briefings()

        self.assertEqual(metrics.total_due, 2)
        self.assertEqual(metrics.success_count, 1)
        self.assertEqual(metrics.failure_count, 1)
        self.assertGreaterEqual(metrics.duration_seconds, 0.0)


class TestCustomAlertsJob(unittest.IsolatedAsyncioTestCase):
    def test_parse_quote_details(self):
        quote_1 = "TSLA: $210.50 (down 5.20% today, prev close $222.00)"
        details_1 = _parse_quote_details(quote_1)
        self.assertEqual(details_1["price"], 210.50)
        self.assertEqual(details_1["change_pct"], -5.20)

        quote_2 = "AAPL: $180.00 (up 2.50% today, prev close $175.60)"
        details_2 = _parse_quote_details(quote_2)
        self.assertEqual(details_2["price"], 180.00)
        self.assertEqual(details_2["change_pct"], 2.50)

    def test_evaluate_condition(self):
        quote = {"price": 100.0, "change_pct": -6.0, "raw": "..."}

        # price_below triggered
        cond_below = {"symbol": "TEST", "type": "price_below", "target_price": 105.0}
        triggered, exp = evaluate_condition(cond_below, quote)
        self.assertTrue(triggered)

        # price_above not triggered
        cond_above = {"symbol": "TEST", "type": "price_above", "target_price": 105.0}
        triggered, _ = evaluate_condition(cond_above, quote)
        self.assertFalse(triggered)

        # price_drop_pct triggered (dropped 6% vs 5% target)
        cond_drop = {"symbol": "TEST", "type": "price_drop_pct", "value": 5.0}
        triggered, exp = evaluate_condition(cond_drop, quote)
        self.assertTrue(triggered)

    async def test_batch_fetch_quotes_deduplication(self):
        with patch("app.jobs.custom_alerts_job.finnhub_client.get_quote", new=AsyncMock(return_value="AAPL: $180.00")) as mock_quote:
            quotes = await batch_fetch_quotes({"AAPL", "AAPL", "MSFT"})

        self.assertEqual(mock_quote.await_count, 2)
        self.assertIn("AAPL", quotes)
        self.assertIn("MSFT", quotes)

    async def test_run_custom_alerts_flow(self):
        alert_id = uuid.uuid4()
        user_id = uuid.uuid4()

        candidate = AlertCandidate(
            alert_id=alert_id,
            user_id=user_id,
            telegram_id=12345,
            description="TSLA drops 5%",
            condition={"symbol": "TSLA", "type": "price_drop_pct", "value": 5.0},
        )

        with (
            patch("app.jobs.custom_alerts_job.fetch_active_alert_candidates", new=AsyncMock(return_value=[candidate])),
            patch(
                "app.jobs.custom_alerts_job.batch_fetch_quotes",
                new=AsyncMock(return_value={"TSLA": {"price": 200.0, "change_pct": -6.0, "raw": "TSLA down 6%"}}),
            ),
            patch("app.jobs.custom_alerts_job.telegram_service.send_message", new=AsyncMock(return_value=True)) as send_mock,
            patch("app.jobs.custom_alerts_job._mark_alert_triggered", new=AsyncMock()) as mark_mock,
        ):
            metrics = await run_custom_alerts()

        self.assertEqual(metrics.total_active_alerts, 1)
        self.assertEqual(metrics.triggered_count, 1)
        send_mock.assert_awaited_once()
        mark_mock.assert_awaited_once_with(alert_id, deactivate=False)


class TestSchedulerLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        stop_scheduler()

    async def test_start_and_stop_scheduler(self):
        sched = start_scheduler()
        self.assertIsNotNone(sched)
        self.assertTrue(sched.running)

        status = get_scheduler_status()
        self.assertTrue(status["running"])
        self.assertTrue(any(j["id"] == "daily_briefings" for j in status["jobs"]))

        stop_scheduler()
        self.assertIsNone(get_scheduler())

    async def test_trigger_job_not_found(self):
        start_scheduler()
        res = trigger_job("non_existent_job")
        self.assertFalse(res)



# Alias daily_briefing_job for test patch references
from app.jobs import daily_briefing_job
