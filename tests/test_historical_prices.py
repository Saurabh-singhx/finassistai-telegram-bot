import unittest
from unittest.mock import AsyncMock, patch

from app.services.market_data import alpha_vantage_client, fmp_client, finnhub_client, polygon_client


class HistoricalPriceFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_fmp_when_finnhub_is_not_available(self):
        fmp_result = "AAPL historical prices via FMP (1 bars):\n- 2026-08-01: O 1, H 2, L 0, C 1, V 100"

        with (
            patch.object(finnhub_client.settings, "FINNHUB_API_KEY", None),
            patch.object(polygon_client, "get_historical_prices", new=AsyncMock(return_value=None)) as polygon,
            patch.object(fmp_client, "get_historical_prices", new=AsyncMock(return_value=fmp_result)) as fmp,
            patch.object(alpha_vantage_client, "get_daily_historical_prices", new=AsyncMock()) as alpha,
        ):
            result = await finnhub_client.get_historical_prices(
                "AAPL", 1785542400, 1785628800, "D"
            )

        self.assertEqual(result, fmp_result)
        polygon.assert_awaited_once_with("AAPL", "2026-08-01", "2026-08-02", "D")
        fmp.assert_awaited_once_with("AAPL", "2026-08-01", "2026-08-02")
        alpha.assert_not_awaited()
