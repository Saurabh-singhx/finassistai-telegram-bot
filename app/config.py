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

    # LLM
    GOOGLE_API_KEY: str
    LLM_MODEL: str = "gemini-3.1-flash-lite"
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

    # Scheduler
    DEFAULT_BRIEFING_TIME: str = "08:00"
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
