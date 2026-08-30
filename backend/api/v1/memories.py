import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_active_user
from backend.db.session import get_db
from backend.models.memory import Memory
from backend.models.user import User

router = APIRouter(prefix="/memories", tags=["Memory"])
MemoryCategory = Literal["preference", "project", "contact", "decision", "routine"]


class MemoryCreate(BaseModel):
    fact: str = Field(min_length=2, max_length=2000)
    category: MemoryCategory = "preference"
    source: str | None = Field(default="manual", max_length=100)


class MemoryUpdate(BaseModel):
    fact: str | None = Field(default=None, min_length=2, max_length=2000)
    category: MemoryCategory | None = None
    is_active: bool | None = None


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    fact: str
    source: str | None
    is_active: bool
    created_at: object
    updated_at: object


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    query: str | None = Query(default=None, max_length=200),
    include_archived: bool = False,
):
    statement = select(Memory).where(Memory.user_id == current_user.id)
    if not include_archived:
        statement = statement.where(Memory.is_active.is_(True))
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(or_(Memory.fact.ilike(pattern), Memory.category.ilike(pattern)))
    result = await db.execute(statement.order_by(Memory.updated_at.desc()))
    return result.scalars().all()


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    memory = Memory(
        user_id=current_user.id,
        fact=data.fact.strip(),
        category=data.category,
        source=data.source,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: uuid.UUID,
    data: MemoryUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(memory, key, value.strip() if key == "fact" and value else value)
    await db.commit()
    await db.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    await db.delete(memory)
    await db.commit()
