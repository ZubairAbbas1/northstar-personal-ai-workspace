import logging
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastmcp import FastMCP
from services.calendar_service import (
    get_next_meeting,
    get_today_events,
    search_calendar_events,
)

logger = logging.getLogger(__name__)
mcp = FastMCP("calendar")


@mcp.tool()
def calendar_get_today_events() -> list[dict[str, Any]]:
    """Get all scheduled calendar events for today."""
    logger.info("Fetching today's calendar events")
    return get_today_events()


@mcp.tool()
def calendar_get_next_meeting() -> dict[str, Any] | None:
    """Get details for the user's next upcoming meeting."""
    logger.info("Fetching next upcoming meeting")
    return get_next_meeting()


@mcp.tool()
def calendar_search_events(
    query: str,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Search calendar events matching a keyword, person, or title."""
    logger.info("Searching calendar events for: %s", query)
    return search_calendar_events(query=query, max_results=max_results)


if __name__ == "__main__":
    mcp.run(transport="stdio")
