import json
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_active_user
from backend.db.session import get_db
from backend.integrations.calendar import GoogleCalendarError, fetch_events_for_date
from backend.models.integration import IntegrationAccount
from backend.models.user import User
from backend.services.crypto_service import crypto_service

router = APIRouter(prefix="/calendar", tags=["Calendar"])


class CalendarEventResponse(BaseModel):
    id: str
    summary: str
    start: str
    end: str
    attendees: list[str] = Field(default_factory=list)
    description: str = ""
    location: str = ""


class CalendarResponse(BaseModel):
    is_connected: bool
    account_email: str | None = None
    connection_status: str = "disconnected"
    sync_error: str | None = None
    events: list[CalendarEventResponse]


async def get_calendar_for_date(
    current_user: User,
    db: AsyncSession,
    target_date: date,
    timezone_offset_minutes: int = 0,
) -> CalendarResponse:
    result = await db.execute(
        select(IntegrationAccount).where(
            IntegrationAccount.user_id == current_user.id,
            IntegrationAccount.provider == "google_calendar",
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        return CalendarResponse(is_connected=False, events=[])

    label = account.account_email_or_id or current_user.email
    token_data: dict[str, Any] | None = None
    if account.encrypted_access_token:
        decrypted = crypto_service.decrypt(account.encrypted_access_token)
        try:
            token_data = json.loads(decrypted or "{}")
        except json.JSONDecodeError:
            token_data = {"access_token": decrypted}
    try:
        events = await fetch_events_for_date(token_data, target_date, timezone_offset_minutes)
    except GoogleCalendarError as exc:
        account.status = "needs_reauth"
        account.error_message = str(exc)
        await db.commit()
        return CalendarResponse(
            is_connected=True,
            account_email=label,
            connection_status="needs_reauth",
            sync_error=str(exc),
            events=[],
        )

    if account.status != "connected" or account.error_message:
        account.status = "connected"
        account.error_message = None
        await db.commit()
    return CalendarResponse(
        is_connected=True,
        account_email=label,
        connection_status="connected",
        events=[CalendarEventResponse(**event) for event in events],
    )


@router.get("/today", response_model=CalendarResponse)
async def get_today_calendar(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    timezone_offset_minutes: Annotated[int, Query(ge=-840, le=840)] = 0,
):
    local_zone = timezone(timedelta(minutes=-timezone_offset_minutes))
    return await get_calendar_for_date(
        current_user,
        db,
        datetime.now(local_zone).date(),
        timezone_offset_minutes,
    )


@router.get("/day", response_model=CalendarResponse)
async def get_calendar_day(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: Annotated[date, Query(alias="date")],
    timezone_offset_minutes: Annotated[int, Query(ge=-840, le=840)] = 0,
):
    return await get_calendar_for_date(current_user, db, target_date, timezone_offset_minutes)
