import logging
from pathlib import Path
import sys
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastmcp import FastMCP
from services.tasks_service import (
    complete_task,
    create_task,
    get_overdue_tasks,
    get_task,
    get_tasks,
    get_today_tasks,
    get_upcoming_tasks,
    update_task,
)

logger = logging.getLogger(__name__)
mcp = FastMCP("tasks")


@mcp.tool()
def tasks_get_tasks(
    status: str | None = None,
    project: str | None = None,
    priority: str | None = None,
) -> list[dict[str, Any]]:
    """List tasks with optional filtering by status, project, or priority."""
    logger.info("Listing tasks (status=%s, project=%s, priority=%s)", status, project, priority)
    return get_tasks(status=status, project=project, priority=priority)


@mcp.tool()
def tasks_get_today_tasks() -> list[dict[str, Any]]:
    """Get all active tasks due today or needing immediate attention."""
    logger.info("Fetching today's tasks")
    return get_today_tasks()


@mcp.tool()
def tasks_get_overdue_tasks() -> list[dict[str, Any]]:
    """Get all active overdue tasks past their due date."""
    logger.info("Fetching overdue tasks")
    return get_overdue_tasks()


@mcp.tool()
def tasks_get_upcoming_tasks(days_ahead: int = 7) -> list[dict[str, Any]]:
    """Get all tasks due in the upcoming specified number of days."""
    logger.info("Fetching upcoming tasks for next %d days", days_ahead)
    return get_upcoming_tasks(days_ahead=days_ahead)


@mcp.tool()
def tasks_get_task(task_id: int) -> dict[str, Any] | None:
    """Get detailed information for a specific task by ID."""
    logger.info("Fetching task %d", task_id)
    return get_task(task_id)


@mcp.tool()
def tasks_create_task(
    title: str,
    description: str | None = None,
    project: str | None = None,
    priority: str = "medium",
    due_date: str | None = None,
    estimated_minutes: int = 30,
    source_type: str = "manual",
    source_id: str | None = None,
) -> dict[str, Any]:
    """Create a new task."""
    logger.info("Creating task '%s'", title)
    return create_task(
        title=title,
        description=description,
        project=project,
        priority=priority,
        due_date=due_date,
        estimated_minutes=estimated_minutes,
        source_type=source_type,
        source_id=source_id,
    )


@mcp.tool()
def tasks_update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    project: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    due_date: str | None = None,
    estimated_minutes: int | None = None,
) -> dict[str, Any] | None:
    """Update properties of an existing task."""
    logger.info("Updating task %d", task_id)
    return update_task(
        task_id=task_id,
        title=title,
        description=description,
        project=project,
        priority=priority,
        status=status,
        due_date=due_date,
        estimated_minutes=estimated_minutes,
    )


@mcp.tool()
def tasks_complete_task(task_id: int) -> dict[str, Any] | None:
    """Mark a task as completed."""
    logger.info("Completing task %d", task_id)
    return complete_task(task_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
