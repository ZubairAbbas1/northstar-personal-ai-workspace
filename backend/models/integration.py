import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.base import Base, GUID, TimestampMixin


class IntegrationAccount(Base, TimestampMixin):
    __tablename__ = "integration_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_integration_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # "gmail", "google_calendar", "github", "slack", "discord"
    account_email_or_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    encrypted_access_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    encrypted_refresh_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    scopes: Mapped[str | None] = mapped_column(
        Text,
        default="[]",
        nullable=True,
    )  # JSON-serialized list of granted OAuth scopes
    status: Mapped[str] = mapped_column(
        String(50),
        default="connected",
        nullable=False,
    )  # "connected", "needs_reauth", "error", "disconnected"
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        default="{}",
        nullable=True,
    )  # JSON-serialized metadata (e.g. workspace name, repo list)

    # Relationship
    user = relationship("User", back_populates="integrations")
