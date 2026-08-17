import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from telegram import Update
from telegram.ext import Application

from app.bot.router import register_handlers
from app.config import settings
from app.core.logging import setup_logging
from app.database import init_db
from app.jobs.scheduler import get_scheduler_status, start_scheduler, stop_scheduler
from app.api.v1.google_auth import router as google_auth_router
setup_logging()
logger = logging.getLogger("finassist.main")

telegram_app: Application | None = None
TELEGRAM_WEBHOOK_PATH = "/telegram/webhook"


def _webhook_url() -> str:
    """Use an explicit URL locally, or Render's public URL in production."""
    base_url = settings.TELEGRAM_WEBHOOK_URL or os.getenv("RENDER_EXTERNAL_URL")
    if not base_url:
        raise RuntimeError(
            "Set TELEGRAM_WEBHOOK_URL, or deploy to Render where RENDER_EXTERNAL_URL is provided."
        )
    normalized_url = base_url.rstrip("/")
    if normalized_url.endswith(TELEGRAM_WEBHOOK_PATH):
        return normalized_url
    return f"{normalized_url}{TELEGRAM_WEBHOOK_PATH}"


def _validate_webhook_settings() -> str:
    webhook_url = _webhook_url()
    if not webhook_url.startswith("https://"):
        raise RuntimeError("TELEGRAM_WEBHOOK_URL must use HTTPS.")
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET must be configured.")
    return webhook_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app

    logger.info("Starting up %s (%s)...", settings.APP_NAME, settings.ENV)
    try:
        webhook_url = _validate_webhook_settings()
        await init_db()

        telegram_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        register_handlers(telegram_app)
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
            drop_pending_updates=True,
        )
        logger.info("Telegram webhook registered at %s", webhook_url)

        start_scheduler()
    except Exception:
        logger.exception("Application startup failed")
        raise

    yield

    logger.info("Shutting down...")
    stop_scheduler()
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()
        telegram_app = None


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.include_router(google_auth_router)


@app.post(TELEGRAM_WEBHOOK_PATH, status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request):
    """Accept a Telegram update and hand it to python-telegram-bot's queue."""
    if telegram_app is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is starting")

    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET or ""
    if not hmac.compare_digest(received_secret, expected_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    try:
        payload = await request.json()
        update = Update.de_json(payload, telegram_app.bot)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Telegram update") from None

    if update is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Telegram update")

    # `Application.start()` consumes this queue, keeping the HTTP acknowledgement
    # quick even when a message invokes a long-running agent workflow.
    telegram_app.update_queue.put_nowait(update)
    return {"ok": True}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "scheduler": get_scheduler_status(),
    }

