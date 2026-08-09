import httpx

from app.config import settings
from app.services.market_data.error_handling import return_unavailable

# SEC requires a descriptive User-Agent with contact info on every request, or it will 403 you.
HEADERS = {"User-Agent": settings.SEC_EDGAR_USER_AGENT}
FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_URL = "https://data.sec.gov/submissions"
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

_ticker_cik_cache: dict[str, str] | None = None


async def _resolve_cik(company_or_ticker: str) -> str | None:
    global _ticker_cik_cache
    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
        if _ticker_cik_cache is None:
            resp = await client.get(TICKER_MAP_URL)
            resp.raise_for_status()
            data = resp.json()
            _ticker_cik_cache = {
                v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()
            }
        return _ticker_cik_cache.get(company_or_ticker.upper())


@return_unavailable("SEC EDGAR")
async def get_recent_filings(company_or_ticker: str, limit: int = 5) -> str:
    cik = await _resolve_cik(company_or_ticker)
    if not cik:
        return f"Could not resolve a CIK for '{company_or_ticker}'. Try the exact ticker symbol."

    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
        resp = await client.get(f"{SUBMISSIONS_URL}/CIK{cik}.json")
        resp.raise_for_status()
        data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])[:limit]
    dates = recent.get("filingDate", [])[:limit]
    accessions = recent.get("accessionNumber", [])[:limit]
    if not forms:
        return f"No recent filings found for {company_or_ticker}."

    lines = []
    for form, date, accession in zip(forms, dates, accessions):
        acc_no_dash = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/{accession}-index.htm"
        lines.append(f"- {form} filed {date}: {url}")
    return "\n".join(lines)
