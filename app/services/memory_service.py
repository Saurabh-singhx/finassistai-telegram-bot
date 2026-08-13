from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.memory import UserMemory
from app.models.messages import Message

RECENT_MESSAGE_LIMIT = 20


async def log_message(db: AsyncSession, user_id, thread_id: str, role: str, content: str, message_type: str = "text") -> None:
    db.add(Message(user_id=user_id, thread_id=thread_id, role=role, content=content, message_type=message_type))
    await db.flush()


from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

async def get_recent_messages(
    db: AsyncSession,
    user_id,
    limit: int = RECENT_MESSAGE_LIMIT,
):
    result = await db.execute(
        select(
            Message.role,
            Message.content,
            Message.message_type,
            Message.created_at,
        )
        .where(Message.user_id == user_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )

    return list(reversed(result.all()))


async def get_user_context(
    db: AsyncSession,
    user_id,
) -> str:
    """Build long-term user context for the system prompt."""

    # Get user profile / Google connection status
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    # Get long-term memories
    result = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(desc(UserMemory.importance))
    )
    memories = result.scalars().all()

    context_parts = []

    # Google connection status
    if user:
        google_connected = bool(
            user.google_id and user.google_refresh_token
        )

        context_parts.append(
            f"Google connected: {google_connected}"
        )

        if user.google_email:
            context_parts.append(
                f"Google email: {user.google_email}"
            )

    # Long-term memories
    if memories:
        context_parts.append(
            "\n".join(
                f"- {m.key}: {m.value}"
                for m in memories[:15]
            )
        )

    if not context_parts:
        return "Nothing yet — this may be an early conversation with this user."

    return "\n".join(context_parts)


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
