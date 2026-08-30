import uuid
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.base import Base, GUID, TimestampMixin


class AICredential(Base, TimestampMixin):
    __tablename__ = "ai_provider_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_ai_provider"),
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
    )  # "groq", "openai", "anthropic", "gemini", "ollama", "custom"
    encrypted_api_key: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )
    base_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    default_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    model_mode: Mapped[str] = mapped_column(
        String(20),
        default="balanced",
        nullable=False,
    )  # "fast", "balanced", "quality"
    allow_fallback: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationship
    user = relationship("User", back_populates="ai_credentials")
