import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.mutable import MutableDict

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
    )

    telegram_username: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    display_name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # User profile
    # ------------------------------------------------------------------

    role: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    timezone: Mapped[str] = mapped_column(
        String,
        default="Asia/Kolkata",
    )

    # ------------------------------------------------------------------
    # Onboarding
    # ------------------------------------------------------------------

    onboarding_state: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=lambda: {
            "step": 0,
            "completed": False,
            "skipped_all": False,
            "skipped_steps": [],
        },
    )

    # ------------------------------------------------------------------
    # Google OAuth 2.0
    # ------------------------------------------------------------------

    # Google's unique account identifier ("sub" claim).
    # This is more reliable than using email as the account identifier.
    google_id: Mapped[str | None] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=True,
    )

    # Google account email
    google_email: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )

    # Google profile information
    google_name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    google_picture: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    # OAuth tokens
   
    google_access_token: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    google_refresh_token: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    # When the current access token expires
    google_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # OAuth scopes granted by the user.
    
    google_scopes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # OAuth connection metadata
    google_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    google_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    preferences: Mapped["UserPreference"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    watchlist: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    notification_preference: Mapped["NotificationPreference"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    custom_alerts: Mapped[list["CustomAlert"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    memories: Mapped[list["UserMemory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )