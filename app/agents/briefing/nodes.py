from app.agents.briefing.prompts import BRIEFING_SYSTEM_PROMPT
from app.agents.briefing.state import BriefingState
from app.services.llm_service import get_chat_llm
from app.services.market_data import finnhub_client

async def gather_data_node(state: BriefingState) -> BriefingState:
    chunks = []

    # 1. Explicit watchlist — highest priority
    watchlist = state.get("watchlist", [])[:8]

    # 2. Companies the user follows
    followed_companies = state.get("followed_companies", [])[:5]

    # Avoid fetching the same company twice
    symbols = []

    for symbol in watchlist + followed_companies:
        symbol = symbol.strip().upper()

        if symbol and symbol not in symbols:
            symbols.append(symbol)

    # Fetch company data
    for symbol in symbols:
        try:
            quote = await finnhub_client.get_quote(symbol)

            news = await finnhub_client.get_company_news(
                symbol,
                limit=2,
            )

            chunks.append(
                f"{symbol}: {quote}\n"
                f"{news}"
            )

        except Exception:
            chunks.append(
                f"{symbol}: Unable to fetch current data."
            )

    # 3. Followed markets
    # Keep this separate because markets may not be valid
    # Finnhub equity ticker symbols.
    followed_markets = state.get("followed_markets", [])[:3]

    if followed_markets:
        chunks.append(
            "FOLLOWED MARKETS:\n"
            + "\n".join(
                f"- {market}"
                for market in followed_markets
            )
        )

    # 4. Final raw data
    state["raw_data"] = (
        "\n\n".join(chunks)
        if chunks
        else "No relevant market data available today."
    )

    return state


async def compose_node(state: BriefingState) -> BriefingState:
    llm = get_chat_llm()

    prompt = BRIEFING_SYSTEM_PROMPT.format(
    followed_companies=", ".join(
        state.get("followed_companies") or []
    ) or "not specified",

    followed_markets=", ".join(
        state.get("followed_markets") or []
    ) or "not specified",

    sectors=", ".join(
        state.get("sectors") or []
    ) or "not specified",

    watchlist=", ".join(
        state.get("watchlist") or []
    ) or "not specified",

    insight_types=", ".join(
        state.get("insight_types") or []
    ) or "general market news",

    raw_data=state.get("raw_data")
        or "No market data available.",
    )   

    if not prompt.strip():
        raise ValueError("Briefing prompt is empty")

    response = await llm.ainvoke(prompt)

    content = response.content

    if isinstance(content, str):
        briefing_text = content

    elif isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))

        briefing_text = "\n".join(
            part for part in parts if part
    )
    else:
        briefing_text = str(content)

    state["briefing_text"] = briefing_text.strip()

    return state
