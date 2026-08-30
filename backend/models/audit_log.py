import uuid
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.base import Base, GUID, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

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
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # "read", "draft", "write_approved", "write_rejected", "config_change"
    target_service: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # "gmail", "calendar", "github", "slack", "ai", "tasks"
    summary: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    details_json: Mapped[str | None] = mapped_column(
        Text,
        default="{}",
        nullable=True,
    )

    # Relationship
    user = relationship("User", back_populates="audit_logs")
