# FinAssist

> A private, conversational finance workspace in Telegram — market research, document intelligence, daily briefings, and Google Workspace assistance in one chat.

FinAssist turns a Telegram conversation into a focused financial assistant. Ask for a quote, upload a report, review a filing, catch up on email, or schedule a meeting. It keeps the context that matters while keeping replies short and useful.

## What it can do

| Area | Capabilities |
| --- | --- |
| Market research | Live quotes, company news, analyst recommendations, historical prices, earnings, reported financials, dividends, stock splits, macro series, and recent SEC filings. |
| Personal research library | Upload PDFs, documents, photos, and voice notes. FinAssist extracts/transcribes them, indexes the content, and answers follow-up questions using your own material. Scanned PDF pages are OCR’d when needed. |
| Daily briefing | Builds a concise daily briefing from your watchlist, followed companies, markets, sectors, and preferred insight types, delivered at your local preferred time. |
| Personalized chat | Remembers recent conversation context and durable preferences so answers reflect your role, watchlist, and interests. |
| Google Workspace | After a Google connection, it can retrieve relevant Gmail messages and create Calendar meetings/events. OAuth uses state validation, PKCE, offline access, and refresh tokens. |
| Onboarding and alerts | A skippable onboarding flow captures companies, markets, sectors, watchlist items, briefing time, and natural-language alert requests. |

## A quick example

```text
You: What moved NVDA today, and how did the latest earnings compare with estimates?

FinAssist: NVDA is up 2.1% today, per Finnhub. The latest reported EPS was...

You: Read the attached investor deck and flag anything that conflicts with those results.

You: Find the email from Acme about next week’s review and create a 30-minute meeting.
```

## Architecture

```text
Telegram
   │
   ├── Onboarding ──────────────── PostgreSQL / Supabase
   ├── Chat agent + tools ──────── Market-data providers, SEC EDGAR, FRED
   ├── Upload pipeline ─────────── Gemini extraction + pgvector retrieval
   ├── Daily briefing scheduler ── Telegram delivery
   └── Google OAuth ────────────── Gmail + Google Calendar
```

The application is a FastAPI service that runs the Telegram bot and scheduler in its lifespan. LangGraph coordinates chat and briefing flows; Postgres stores users, preferences, messages, OAuth state, and document embeddings.

## Getting started

### Prerequisites

- Python 3.11+
- PostgreSQL with the `vector` extension (Supabase Postgres works well)
- A Telegram Bot token
- A Gemini API key
- Finnhub and FRED API keys for market and macro data
- A Google OAuth web-client configuration for Gmail and Calendar workflows

### Install and configure

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set the required values in `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/finassist
TELEGRAM_BOT_TOKEN=...
GOOGLE_API_KEY=...
FINNHUB_API_KEY=...
FRED_API_KEY=...
SEC_EDGAR_USER_AGENT="FinAssist your-email@example.com"

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

Start the service:

```bash
uvicorn app.main:app --reload
```

Health check: `GET /health`

### Google OAuth setup

1. In Google Cloud, create a **Web application** OAuth client and add the exact value of `GOOGLE_REDIRECT_URI` as an authorized redirect URI.
2. Enable the Gmail and Google Calendar APIs for that project.
3. Set the client ID, secret, and redirect URI in `.env`.
4. Start a connection at `GET /auth/google/start?user_id=<finassist-user-uuid>`.
5. The callback at `/auth/google/callback` saves the Google identity, granted scopes, token expiry, and refresh token.

Google connections created before Calendar meeting support was enabled must be re-authorized so the account grants the `calendar.events` scope.

## Available Telegram interactions

| Send or ask | Result |
| --- | --- |
| `/start` | Begin the personalized, fully skippable onboarding flow. |
| “Quote AAPL” | Current price and daily movement. |
| “What are the latest filings for TSLA?” | Recent SEC filings with source links. |
| “Show US inflation” | Recent FRED macro observations. |
| “What did analysts say about MSFT?” | Latest recommendation breakdown. |
| A PDF, text document, image, or voice note | Extracted content is saved privately and can be queried later. |
| “Search my documents for …” | Semantic retrieval across the user’s indexed uploads. |
| “Connect my Google account” | Starts the Google authorization flow. |
| “Find the latest email from …” / “Schedule a meeting …” | Gmail retrieval and Calendar event creation after Google authorization. |

## Development and verification

Run the focused OAuth regression test:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_google_oauth.py' -v
```

Compile-check the application:

```bash
.venv/bin/python -m compileall -q app tests
```

Use Alembic for schema changes in deployed environments. For a fresh development database, startup creates the mapped tables and enables `vector`.

## Operational notes

- The daily briefing scheduler polls eligible users once per minute. It is suitable for a modest user base; move to per-user jobs or a queue as usage grows.
- OAuth access and refresh tokens are stored in the user record. Use encrypted storage/column encryption and restrict database access before production use.
- Never commit `.env`, OAuth client secrets, bot tokens, or database credentials.
- SEC EDGAR requires a descriptive `User-Agent` containing a real contact address.
- Market data availability depends on the entitlements of the configured provider keys.

## Stack

FastAPI · python-telegram-bot · LangGraph · Gemini · PostgreSQL/Supabase · pgvector · SQLAlchemy · APScheduler · Google OAuth · Finnhub · FRED · SEC EDGAR
