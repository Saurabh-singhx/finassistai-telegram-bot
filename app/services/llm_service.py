import logging
from functools import lru_cache

from google import genai
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.GOOGLE_API_KEY)


@lru_cache
def get_chat_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.4,
    )


def log_cache_usage(response) -> None:
    """Log implicit-cache hit info from a Gemini response, if present.
    Call this after llm.ainvoke(...) in agent_node to confirm caching is firing."""
    usage = getattr(response, "response_metadata", {}).get("usage_metadata", {})
    cached = usage.get("cached_content_token_count") or usage.get("cache_read_input_tokens")
    total_input = usage.get("prompt_token_count") or usage.get("input_tokens")
    if cached:
        logger.info(f"Gemini cache hit: {cached}/{total_input} input tokens served from cache")
    else:
        logger.debug(f"No cache hit. Total input tokens: {total_input}")


async def embed_text(text: str) -> list[float]:
    result = await client.aio.models.embed_content(
        model=settings.EMBEDDING_MODEL,
        contents=text,
        config={
            "task_type": "RETRIEVAL_DOCUMENT",
            "output_dimensionality": 768,
        },
    )
    return result.embeddings[0].values


async def embed_query(text: str) -> list[float]:
    result = await client.aio.models.embed_content(
        model=settings.EMBEDDING_MODEL,
        contents=text,
        config={
            "task_type": "RETRIEVAL_QUERY",
            "output_dimensionality": 768,
        },
    )
    return result.embeddings[0].values