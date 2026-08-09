import functools
import logging

import httpx

logger = logging.getLogger("finassist.market_data")


def return_unavailable(provider: str):
    """Turn expected provider/network failures into tool-safe responses."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except httpx.TimeoutException:
                logger.warning("%s timed out in %s", provider, func.__name__, exc_info=True)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "%s returned HTTP %s in %s",
                    provider,
                    exc.response.status_code,
                    func.__name__,
                    exc_info=True,
                )
            except httpx.RequestError:
                logger.warning("%s request failed in %s", provider, func.__name__, exc_info=True)
            except (ValueError, KeyError, TypeError):
                logger.exception("Invalid %s response in %s", provider, func.__name__)
            else:
                return

            return f"{provider} data is temporarily unavailable. Please try again shortly."

        return wrapper

    return decorator
