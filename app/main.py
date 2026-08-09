import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from telegram.ext import Application

from app.bot.router import register_handlers
from app.config import settings
from app.core.logging import setup_logging
from app.database import init_db
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.api.v1.google_auth import router as google_auth_router
setup_logging()
logger = logging.getLogger("finassist.main")

telegram_app: Application | None = None
_polling_task: asyncio.Task | None = None


async def _run_polling(application: Application) -> None:
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram bot polling started.")


def _log_polling_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    try:
        task.result()
    except Exception:
        logger.exception("Telegram polling stopped unexpectedly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app, _polling_task

    logger.info("Starting up %s (%s)...", settings.APP_NAME, settings.ENV)
    try:
        await init_db()

        telegram_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        register_handlers(telegram_app)
        _polling_task = asyncio.create_task(_run_polling(telegram_app))
        _polling_task.add_done_callback(_log_polling_task_result)

        start_scheduler()
    except Exception:
        logger.exception("Application startup failed")
        raise

    yield

    logger.info("Shutting down...")
    stop_scheduler()
    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.include_router(google_auth_router)

@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}
