from datetime import datetime, time, timezone
import logging
from typing import Any

from googleapiclient.discovery import build

from services.calendar_auth import get_calendar_credentials

logger = logging.getLogger(__name__)


def get_calendar_api():
    """Builds the Google Calendar API client."""
    creds = get_calendar_credentials()
    if not creds:
        return None
    return build("calendar", "v3", credentials=creds)


def parse_event(event: dict[str, Any]) -> dict[str, Any]:
    """Formats raw Google Calendar API event into a clean dictionary."""
    start_info = event.get("start", {})
    end_info = event.get("end", {})

    start_time = start_info.get("dateTime") or start_info.get("date") or ""
    end_time = end_info.get("dateTime") or end_info.get("date") or ""

    attendees = [
        att.get("email") or att.get("displayName") or ""
        for att in event.get("attendees", [])
        if att.get("email") or att.get("displayName")
    ]

    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", "(No title)"),
        "description": event.get("description", ""),
        "start": start_time,
        "end": end_time,
        "location": event.get("location", ""),
        "hangout_link": event.get("hangoutLink", ""),
        "organizer": event.get("organizer", {}).get("email", ""),
        "attendees": attendees,
        "status": event.get("status", ""),
    }


def get_today_events() -> list[dict[str, Any]]:
    """Retrieves all calendar events for today."""
    service = get_calendar_api()
    if not service:
        logger.warning("Calendar service is unavailable (missing credentials).")
        return []

    try:
        now = datetime.now()
        start_of_day = datetime.combine(now.date(), time.min).isoformat() + "Z"
        end_of_day = datetime.combine(now.date(), time.max).isoformat() + "Z"

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
        return [parse_event(e) for e in events_result.get("items", [])]
    except Exception as e:
        logger.exception("Failed to retrieve today's calendar events: %s", e)
        return []


def get_next_meeting() -> dict[str, Any] | None:
    """Finds the immediately upcoming meeting starting after current time."""
    service = get_calendar_api()
    if not service:
        return None

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now_iso,
                maxResults=5,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = events_result.get("items", [])
        if items:
            return parse_event(items[0])
        return None
    except Exception as e:
        logger.exception("Failed to retrieve next meeting: %s", e)
        return None


def search_calendar_events(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Searches calendar events by query string."""
    service = get_calendar_api()
    if not service or not query.strip():
        return []

    try:
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                q=query,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return [parse_event(e) for e in events_result.get("items", [])]
    except Exception as e:
        logger.exception("Failed to search calendar events for '%s': %s", query, e)
        return []
