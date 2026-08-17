import asyncio
import logging

from telegram import Bot
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError

from app.config import settings


_bot: Bot | None = None
logger = logging.getLogger("finassist.telegram")

# Telegram permits 4096 characters. Leave room for Unicode edge cases and
# split at natural boundaries so long LLM replies remain readable.
TELEGRAM_MAX_LEN = 3500


def get_bot() -> Bot:
    global _bot

    if _bot is None:
        _bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    return _bot


async def send_message(chat_id: int, text: str, max_retries: int = 2) -> bool:
    """Send an LLM reply without handing untrusted text to Telegram's parser."""
    bot = get_bot()
    chunks = _split_message(text)
    if not chunks:
        return True

    for chunk in chunks:
        attempts = 0
        while True:
            try:
                await bot.send_message(chat_id=chat_id, text=chunk)
                break
            except RetryAfter as exc:
                attempts += 1
                wait_time = float(exc.retry_after) + 0.5
                logger.warning(
                    "Telegram rate limit hit for chat %s. Retrying in %.2fs (attempt %d/%d)",
                    chat_id,
                    wait_time,
                    attempts,
                    max_retries,
                )
                if attempts > max_retries:
                    logger.error("Exceeded max retries for chat %s due to rate limiting", chat_id)
                    return False
                await asyncio.sleep(wait_time)
            except Forbidden as exc:
                logger.warning("Telegram bot forbidden/blocked for chat %s: %s", chat_id, exc)
                return False
            except BadRequest as exc:
                logger.warning("Telegram BadRequest for chat %s: %s", chat_id, exc)
                return False
            except TelegramError as exc:
                attempts += 1
                logger.warning(
                    "Telegram error sending to chat %s: %s (attempt %d/%d)",
                    chat_id,
                    exc,
                    attempts,
                    max_retries,
                )
                if attempts > max_retries:
                    raise
                await asyncio.sleep(1.0)

    return True



def _split_message(text: str) -> list[str]:
    """Keep every delivered Telegram message within the supported size."""
    if not text:
        return []

    chunks = []
    remaining = text
    while len(remaining) > TELEGRAM_MAX_LEN:
        boundary = max(
            remaining.rfind("\n", 0, TELEGRAM_MAX_LEN + 1),
            remaining.rfind(" ", 0, TELEGRAM_MAX_LEN + 1),
        )
        if boundary <= 0:
            boundary = TELEGRAM_MAX_LEN

        chunks.append(remaining[:boundary].rstrip())
        remaining = remaining[boundary:].lstrip()

    if remaining:
        chunks.append(remaining)
    return chunks


async def send_status(chat_id: int, text: str):
    bot = get_bot()

    return await bot.send_message(
        chat_id=chat_id,
        text=text,
    )


async def update_status(
    chat_id: int,
    status_message_id: int,
    text: str,
) -> None:
    bot = get_bot()

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text=text,
        )
    except TelegramError:
        # Progress indicators are optional and must not make an agent tool fail.
        logger.warning("Could not update status message %s in chat %s", status_message_id, chat_id, exc_info=True)


async def delete_status(
    chat_id: int,
    status_message_id: int,
) -> None:
    bot = get_bot()

    try:
        await bot.delete_message(
            chat_id=chat_id,
            message_id=status_message_id,
        )
    except TelegramError:
        # A user may delete the status message before we do; this is non-fatal.
        logger.warning("Could not delete status message %s in chat %s", status_message_id, chat_id, exc_info=True)
