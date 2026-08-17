from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Create tables + pgvector extension. For production, prefer Alembic migrations."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "ALTER TABLE notification_preferences "
                "ADD COLUMN IF NOT EXISTS last_briefing_sent_at TIMESTAMPTZ, "
                "ADD COLUMN IF NOT EXISTS last_briefing_date VARCHAR(10);"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE custom_alerts "
                "ADD COLUMN IF NOT EXISTS last_triggered_at TIMESTAMPTZ;"
            )
        )

