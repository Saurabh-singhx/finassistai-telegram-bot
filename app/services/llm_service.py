from functools import lru_cache

from google import genai
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings


client = genai.Client(api_key=settings.GOOGLE_API_KEY)


@lru_cache
def get_chat_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.4,
    )


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