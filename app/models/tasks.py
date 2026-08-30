from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

TaskPriority = Literal["low", "medium", "high", "urgent"]
TaskStatus = Literal["todo", "in_progress", "completed", "cancelled"]


class TaskCreate(BaseModel):
    title: str = Field(description="Title of the task.")
    description: str | None = Field(default=None, description="Detailed description of the task.")
    project: str | None = Field(default=None, description="Associated project name.")
    priority: TaskPriority = Field(default="medium", description="Priority: low, medium, high, or urgent.")
    due_date: str | None = Field(default=None, description="Due date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).")
    estimated_minutes: int | None = Field(default=30, description="Estimated duration in minutes.")
    source_type: str | None = Field(default="manual", description="Source: email, meeting, manual, etc.")
    source_id: str | None = Field(default=None, description="ID of source entity.")


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    project: str | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_date: str | None = None
    estimated_minutes: int | None = None


class TaskItem(BaseModel):
    id: int | str
    title: str
    description: str | None = None
    project: str | None = None
    priority: TaskPriority = "medium"
    status: TaskStatus = "todo"
    due_date: str | None = None
    estimated_minutes: int | None = None
    source_type: str | None = None
    source_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
