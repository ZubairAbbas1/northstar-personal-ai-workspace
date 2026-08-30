import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_active_user
from backend.db.session import get_db
from backend.models.notification import Notification, NotificationPreference
from backend.models.user import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    severity: str
    title: str
    message: str
    source_link: str | None = None
    is_read: bool
    created_at: str


class NotificationPreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email_urgent: bool
    email_action_needed: bool
    email_newsletters: bool
    cal_reminders: bool
    cal_conflicts: bool
    task_due_today: bool
    task_overdue: bool
    slack_mentions: bool
    github_reviews: bool
    morning_brief_time: str
    evening_review_time: str


class UpdateNotificationPreferencesRequest(BaseModel):
    email_urgent: bool | None = None
    email_action_needed: bool | None = None
    email_newsletters: bool | None = None
    cal_reminders: bool | None = None
    cal_conflicts: bool | None = None
    task_due_today: bool | None = None
    task_overdue: bool | None = None
    slack_mentions: bool | None = None
    github_reviews: bool | None = None
    morning_brief_time: str | None = None
    evening_review_time: str | None = None


@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Lists recent active notifications for the current user."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_dismissed.is_(False))
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    items = result.scalars().all()
    return [
        NotificationResponse(
            id=n.id,
            category=n.category,
            severity=n.severity,
            title=n.title,
            message=n.message,
            source_link=n.source_link,
            is_read=n.is_read,
            created_at=n.created_at.isoformat(),
        )
        for n in items
    ]


@router.post("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Marks a notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    item.is_read = True
    await db.commit()
    return {"message": "Notification marked as read"}


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
async def mark_all_read(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Marks all notifications as read."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "All notifications marked as read"}


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Gets notification preferences."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
    return NotificationPreferencesResponse.model_validate(prefs)


@router.patch("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    data: UpdateNotificationPreferencesRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Updates notification preferences."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(prefs, k, v)

    await db.commit()
    await db.refresh(prefs)
    return NotificationPreferencesResponse.model_validate(prefs)
