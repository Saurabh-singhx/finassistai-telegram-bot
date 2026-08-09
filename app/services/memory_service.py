from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import UserMemory
from app.models.messages import Message

RECENT_MESSAGE_LIMIT = 20


async def log_message(db: AsyncSession, user_id, thread_id: str, role: str, content: str, message_type: str = "text") -> None:
    db.add(Message(user_id=user_id, thread_id=thread_id, role=role, content=content, message_type=message_type))
    await db.flush()


async def get_recent_messages(db: AsyncSession, user_id, limit: int = RECENT_MESSAGE_LIMIT) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.user_id == user_id).order_by(desc(Message.created_at)).limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def get_user_context(db: AsyncSession, user_id) -> str:
    """Renders long-term UserMemory facts into a short string injected into the chat system prompt.
    This is the 'build context about the user over time' piece — distinct from the LangGraph
    checkpointer, which only covers the current conversation thread."""
    result = await db.execute(select(UserMemory).where(UserMemory.user_id == user_id).order_by(desc(UserMemory.importance)))
    memories = result.scalars().all()
    if not memories:
        return "Nothing yet — this may be an early conversation with this user."
    return "\n".join(f"- {m.key}: {m.value}" for m in memories[:15])


async def upsert_memory(db: AsyncSession, user_id, key: str, value: str, importance: float = 0.5) -> None:
    """Called by the summarization background job (see jobs/), not on every message —
    keeps LLM summarization cost bounded."""
    result = await db.execute(select(UserMemory).where(UserMemory.user_id == user_id, UserMemory.key == key))
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = value
        existing.importance = importance
    else:
        db.add(UserMemory(user_id=user_id, key=key, value=value, importance=importance))
    await db.flush()
