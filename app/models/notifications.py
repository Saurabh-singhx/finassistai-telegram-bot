import uuid
from datetime import datetime, time

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, Time, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationPreference(Base):
    """'When would you like your daily briefing?' + which channels/insight types trigger pushes."""

    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    daily_briefing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    briefing_time: Mapped[time] = mapped_column(Time, default=time(8, 0))
    timezone: Mapped[str] = mapped_column(String, default="Asia/Kolkata")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="notification_preference")


class CustomAlert(Base):
    """'Any custom alerts or events you'd like me to follow?' e.g. 'ping me if TSLA drops 5%'."""

    __tablename__ = "custom_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    description: Mapped[str] = mapped_column(String)  # raw text as given by the user
    # structured condition once parsed by the agent, e.g. {"symbol": "TSLA", "type": "price_drop_pct", "value": 5}
    condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="custom_alerts")
