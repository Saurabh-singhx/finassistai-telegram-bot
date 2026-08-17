from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    ENV: str = "development"
    APP_NAME: str = "FinAssist Bot"

    # Database
    DATABASE_URL: str

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    # Public HTTPS endpoint registered with Telegram, for example:
    # https://finassist.onrender.com/telegram/webhook
    TELEGRAM_WEBHOOK_URL: str | None = None
    # A high-entropy value Telegram sends in the webhook request header.
    TELEGRAM_WEBHOOK_SECRET: str | None = None
    # LLM
    GOOGLE_API_KEY: str
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Market data - Phase 1
    FINNHUB_API_KEY: str | None = None
    FRED_API_KEY: str | None = None
    SEC_EDGAR_USER_AGENT: str = "FinAssistBot contact@example.com"

    # Market data - Phase 2
    ALPHA_VANTAGE_API_KEY: str | None = None
    FMP_API_KEY: str | None = None
    POLYGON_API_KEY: str | None = None

    # Google OAuth - Phase 2
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None

    # Scheduler & Background Jobs
    SCHEDULER_ENABLED: bool = True
    DEFAULT_BRIEFING_TIME: str = "08:00"
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    BRIEFING_JOB_INTERVAL_MINUTES: int = 1
    BRIEFING_CONCURRENCY_LIMIT: int = 10
    BRIEFING_TIMEOUT_SECONDS: int = 60
    BRIEFING_DISPATCH_WINDOW_MINUTES: int = 120
    BRIEFING_BATCH_SIZE: int = 100
    ALERTS_JOB_ENABLED: bool = True
    ALERTS_JOB_INTERVAL_MINUTES: int = 5
    ALERTS_CONCURRENCY_LIMIT: int = 10
    ALERTS_TIMEOUT_SECONDS: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
