import uuid
from datetime import datetime, timezone
from typing import Annotated, List, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_active_user
from backend.db.session import get_db
from backend.models.task import Task
from backend.models.notification import Notification, NotificationPreference
from backend.models.project import Project
from backend.models.user import User

router = APIRouter(prefix="/tasks", tags=["Tasks"])


async def sync_task_notification(task: Task, db: AsyncSession) -> None:
    """Create or retire the single actionable notification for a task."""
    source_link = f"/tasks?task={task.id}"
    existing_result = await db.execute(
        select(Notification).where(
            Notification.user_id == task.user_id,
            Notification.source_link == source_link,
            Notification.category == "task",
        )
    )
    existing = existing_result.scalar_one_or_none()
    if task.status in ("completed", "cancelled") or task.due_date is None:
        if existing:
            existing.is_dismissed = True
        return

    now = datetime.now(timezone.utc)
    due = task.due_date if task.due_date.tzinfo else task.due_date.replace(tzinfo=timezone.utc)
    due_day = due.date()
    prefs_result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == task.user_id)
    )
    prefs = prefs_result.scalar_one_or_none()
    is_overdue = due < now
    should_notify = (is_overdue and (prefs is None or prefs.task_overdue)) or (
        due_day == now.date() and (prefs is None or prefs.task_due_today)
    )
    if not should_notify:
        if existing:
            existing.is_dismissed = True
        return

    title = "Task overdue" if is_overdue else "Task due today"
    message = f"{task.title} was due {due.strftime('%b %d at %H:%M')}" if is_overdue else f"{task.title} is due today."
    if existing:
        existing.title = title
        existing.message = message
        existing.severity = "urgent" if is_overdue or task.priority == "urgent" else "warning"
        existing.is_dismissed = False
    else:
        db.add(Notification(
            user_id=task.user_id,
            category="task",
            severity="urgent" if is_overdue or task.priority == "urgent" else "warning",
            title=title,
            message=message,
            source_link=source_link,
        ))


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    project_id: uuid.UUID | None = None
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    status: Literal["todo", "in_progress", "completed", "cancelled"] = "todo"
    due_date: datetime | None = None
    remind_at: datetime | None = None
    estimated_minutes: int = Field(default=30, ge=1, le=1440)
    source_type: str = "manual"
    source_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    project_id: uuid.UUID | None = None
    priority: Literal["low", "medium", "high", "urgent"] | None = None
    status: Literal["todo", "in_progress", "completed", "cancelled"] | None = None
    due_date: datetime | None = None
    remind_at: datetime | None = None
    estimated_minutes: int | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    status: str
    priority: str
    due_date: datetime | None = None
    remind_at: datetime | None = None
    estimated_minutes: int
    source_type: str
    source_id: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(default=None, alias="status"),
    priority_filter: str | None = Query(default=None, alias="priority"),
    project_id: uuid.UUID | None = Query(default=None),
):
    """Lists tasks for the authenticated user."""
    query = select(Task).where(Task.user_id == current_user.id)
    if status_filter:
        query = query.where(Task.status == status_filter)
    if priority_filter:
        query = query.where(Task.priority == priority_filter)
    if project_id:
        query = query.where(Task.project_id == project_id)

    query = query.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [TaskResponse.model_validate(t) for t in tasks]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Creates a new task for the authenticated user."""
    if data.project_id:
        owned_project = await db.execute(
            select(Project.id).where(Project.id == data.project_id, Project.user_id == current_user.id)
        )
        if owned_project.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task = Task(
        user_id=current_user.id,
        project_id=data.project_id,
        title=data.title,
        description=data.description,
        status=data.status,
        priority=data.priority,
        due_date=data.due_date,
        remind_at=data.remind_at,
        estimated_minutes=data.estimated_minutes,
        source_type=data.source_type,
        source_id=data.source_id,
    )
    db.add(task)
    await db.flush()
    await sync_task_notification(task, db)
    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Gets a specific task."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == current_user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Updates a task."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == current_user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    update_dict = data.model_dump(exclude_unset=True)
    if "project_id" in update_dict and update_dict["project_id"] is not None:
        owned_project = await db.execute(
            select(Project.id).where(
                Project.id == update_dict["project_id"], Project.user_id == current_user.id
            )
        )
        if owned_project.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if "status" in update_dict:
        if update_dict["status"] == "completed" and task.status != "completed":
            task.completed_at = datetime.now(timezone.utc)
        elif update_dict["status"] != "completed":
            task.completed_at = None

    for key, value in update_dict.items():
        setattr(task, key, value)

    await sync_task_notification(task, db)
    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Deletes a task."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == current_user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.delete(task)
    await db.commit()
