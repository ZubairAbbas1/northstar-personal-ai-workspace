import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.base import Base, GUID, TimestampMixin


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

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
    category: Mapped[str] = mapped_column(
        String(50),
        default="system",
        index=True,
        nullable=False,
    )  # "email", "calendar", "task", "slack", "github", "system"
    severity: Mapped[str] = mapped_column(
        String(20),
        default="info",
        nullable=False,
    )  # "info", "warning", "urgent"
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_link: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        nullable=False,
    )
    is_dismissed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationship
    user = relationship("User", back_populates="notifications")


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_notification_prefs"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    email_urgent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_action_needed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_newsletters: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cal_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cal_conflicts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    task_due_today: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    task_overdue: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    slack_mentions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    github_reviews: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    morning_brief_time: Mapped[str] = mapped_column(String(10), default="08:30", nullable=False)
    evening_review_time: Mapped[str] = mapped_column(String(10), default="19:00", nullable=False)

    # Relationship
    user = relationship("User", back_populates="notification_preferences")
