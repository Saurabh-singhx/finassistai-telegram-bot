import httpx

from app.config import settings
from app.services.market_data.error_handling import return_unavailable

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


@return_unavailable("FRED")
async def get_series(series_id: str, limit: int = 5) -> str:
    if not settings.FRED_API_KEY:
        return "FRED API key not configured."
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            BASE_URL,
            params={
                "series_id": series_id,
                "api_key": settings.FRED_API_KEY,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    observations = data.get("observations", [])
    if not observations:
        return f"No data found for FRED series '{series_id}'."
    lines = [f"- {o['date']}: {o['value']}" for o in observations]
    return f"{series_id} (most recent first):\n" + "\n".join(lines)
