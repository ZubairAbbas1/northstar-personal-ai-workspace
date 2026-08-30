import asyncio
from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Any, List
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


class GoogleCalendarError(RuntimeError):
    """A safe, user-facing Google Calendar synchronization error."""


def build_calendar_client_from_token(token_data: dict[str, Any]):
    """Builds a Google Calendar API client from decrypted user token data."""
    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes", SCOPES),
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _fetch_events_for_date_sync(
    token_data: dict[str, Any] | None,
    target_date: date,
    timezone_offset_minutes: int = 0,
) -> List[dict[str, Any]]:
    """Fetches calendar events for one local date."""
    if not token_data or not token_data.get("access_token"):
        raise GoogleCalendarError("Google Calendar authorization is missing. Reconnect the calendar and try again.")

    try:
        service = build_calendar_client_from_token(token_data)
        local_zone = timezone(timedelta(minutes=-timezone_offset_minutes))
        start_of_day = datetime.combine(target_date, time.min, tzinfo=local_zone).astimezone(timezone.utc).isoformat()
        end_of_day = datetime.combine(target_date, time.max, tzinfo=local_zone).astimezone(timezone.utc).isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        clean_events = []
        for e in events:
            start = e.get("start", {}).get("dateTime", e.get("start", {}).get("date", ""))
            end = e.get("end", {}).get("dateTime", e.get("end", {}).get("date", ""))
            attendees = [a.get("email") for a in e.get("attendees", []) if a.get("email")]

            clean_events.append({
                "id": e.get("id"),
                "summary": e.get("summary", "Untitled Meeting"),
                "start": start,
                "end": end,
                "attendees": attendees,
                "description": e.get("description", ""),
                "location": e.get("location", ""),
            })

        return clean_events
    except GoogleCalendarError:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch Google Calendar events: %s", exc)
        message = str(exc).lower()
        if "invalid_grant" in message or "unauthorized" in message or "401" in message:
            raise GoogleCalendarError("Google Calendar authorization expired. Reconnect the calendar to continue syncing.") from exc
        if "403" in message or "insufficient" in message:
            raise GoogleCalendarError("Google Calendar access was denied. Reconnect and approve Calendar read access.") from exc
        raise GoogleCalendarError("Google Calendar could not be synchronized. Check the connection and try again.") from exc


def _fetch_today_events_sync(
    token_data: dict[str, Any] | None,
    timezone_offset_minutes: int = 0,
) -> List[dict[str, Any]]:
    local_zone = timezone(timedelta(minutes=-timezone_offset_minutes))
    return _fetch_events_for_date_sync(token_data, datetime.now(local_zone).date(), timezone_offset_minutes)


async def fetch_today_events(
    token_data: dict[str, Any] | None,
    timezone_offset_minutes: int = 0,
) -> List[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_today_events_sync, token_data, timezone_offset_minutes)


async def fetch_events_for_date(
    token_data: dict[str, Any] | None,
    target_date: date,
    timezone_offset_minutes: int = 0,
) -> List[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_events_for_date_sync, token_data, target_date, timezone_offset_minutes)
