import functools
import logging

logger = logging.getLogger("finassist.errors")


def handle_errors(fallback_message: str = "Something broke on my end — give me a second and try again."):
    """Wraps a Telegram handler so an unhandled exception never crashes the polling loop
    and the user always gets a short, human reply instead of silence."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            try:
                return await func(update, context, *args, **kwargs)
            except Exception:
                logger.exception("Unhandled error in handler %s", func.__name__)
                try:
                    if update and update.effective_chat:
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=fallback_message)
                except Exception:
                    logger.exception("Failed to send fallback error message")

        return wrapper

    return decorator
