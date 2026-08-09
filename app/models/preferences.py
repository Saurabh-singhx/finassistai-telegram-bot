import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserPreference(Base):
    """Onboarding answers, all nullable so any question (or all of them) can be skipped."""

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    # "Which companies, sectors, or markets do you actively follow?"
    sectors: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    followed_companies: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    followed_markets: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # "What type of financial insights are most valuable to you?"
    # e.g. market_news, earnings, sec_filings, analyst_ratings, macro
    insight_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="preferences")
