from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_active_user
from backend.db.session import get_db
from backend.models.memory import Memory
from backend.models.project import Project
from backend.models.task import Task
from backend.models.user import User

router = APIRouter(prefix="/search", tags=["Search"])


class SearchResult(BaseModel):
    id: str
    domain: str
    title: str
    snippet: str
    metadata: dict[str, Any] = {}


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]


@router.get("", response_model=SearchResponse)
async def universal_search(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    query: str = Query(min_length=2, max_length=200),
):
    pattern = f"%{query.strip()}%"
    task_rows = await db.execute(
        select(Task).where(
            Task.user_id == current_user.id,
            or_(Task.title.ilike(pattern), Task.description.ilike(pattern)),
        ).limit(20)
    )
    project_rows = await db.execute(
        select(Project).where(
            Project.user_id == current_user.id,
            or_(Project.name.ilike(pattern), Project.description.ilike(pattern)),
        ).limit(10)
    )
    memory_rows = await db.execute(
        select(Memory).where(
            Memory.user_id == current_user.id,
            Memory.is_active.is_(True),
            or_(Memory.fact.ilike(pattern), Memory.category.ilike(pattern)),
        ).limit(10)
    )

    results: list[SearchResult] = []
    for task in task_rows.scalars():
        results.append(SearchResult(
            id=str(task.id), domain="Task", title=task.title,
            snippet=task.description or f"{task.priority.title()} priority · {task.status.replace('_', ' ').title()}",
            metadata={"status": task.status, "priority": task.priority, "due_date": task.due_date},
        ))
    for project in project_rows.scalars():
        results.append(SearchResult(
            id=str(project.id), domain="Project", title=project.name,
            snippet=project.description or "Project workspace",
            metadata={"status": project.status, "color": project.color},
        ))
    for memory in memory_rows.scalars():
        results.append(SearchResult(
            id=str(memory.id), domain="Memory", title=memory.category.title(),
            snippet=memory.fact, metadata={"source": memory.source},
        ))
    return SearchResponse(query=query.strip(), total=len(results), results=results)
