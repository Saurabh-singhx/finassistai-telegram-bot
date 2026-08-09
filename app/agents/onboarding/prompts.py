# Ordered onboarding questions.
# Every question is individually skippable, and the whole flow
# can be skipped in one shot ("skip all" / "skip onboarding").

ONBOARDING_QUESTIONS = [
    {
        "key": "role",
        "question": (
            "Quick one to start — what best describes you? "
            "Investor, analyst, founder, student, or finance professional?"
        ),
        "field": "role",
    },
    {
        "key": "followed_companies",
        "question": (
            "Which companies do you actively follow? "
            "You can list multiple companies or stock tickers, e.g. AAPL, NVDA, TSLA."
        ),
        "field": "followed_companies",
    },
    {
        "key": "followed_markets",
        "question": (
            "Which markets or indices do you actively follow? "
            "For example: S&P 500, NASDAQ, Dow Jones, Indian markets, or US equities."
        ),
        "field": "followed_markets",
    },
    {
        "key": "sectors",
        "question": (
            "Which sectors are you interested in? "
            "For example: technology, healthcare, energy, financials."
        ),
        "field": "sectors",
    },
    {
        "key": "watchlist",
        "question": (
            "Any specific stocks or companies you want me watching for you?"
        ),
        "field": "watchlist",
    },
    {
        "key": "insight_types",
        "question": (
            "What's most useful to you — market news, earnings, SEC filings, "
            "analyst ratings, macro events? You can list a few."
        ),
        "field": "insight_types",
    },
    {
        "key": "briefing_time",
        "question": (
            "When should I send your daily briefing? "
            "Give me a time, like 8am or 21:30."
        ),
        "field": "briefing_time",
    },
    {
        "key": "custom_alerts",
        "question": (
            'Last one — any custom alerts you want? '
            'e.g. "tell me if TSLA drops 5%" or '
            '"notify me on Fed rate decisions".'
        ),
        "field": "custom_alerts",
    },
]


SKIP_KEYWORDS = {
    "skip",
    "skip it",
    "no",
    "none",
    "next",
    "pass",
}

SKIP_ALL_KEYWORDS = {
    "skip all",
    "skip onboarding",
    "skip everything",
}


WELCOME_MESSAGE = (
    "Hey, I'm your finance assistant. I'll ask a handful of quick questions "
    "so I can actually be useful to you — feel free to skip any of them, "
    'or say "skip all" to jump straight in.'
)


ONBOARDING_DONE_MESSAGE = (
    "Got it, that's enough to get started. "
    "Ask me anything, or send a filing/report and I'll dig in."
)
