import json
import logging
import sys
from pathlib import Path
from typing import Any


# --------------------------------------------------
# Make project root importable
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


from fastmcp import FastMCP

from services.gmail_service import (
    get_recent_emails,
    search_emails,
    get_email,
)


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# MCP Server
# --------------------------------------------------

mcp = FastMCP("gmail")


# --------------------------------------------------
# Tool 1: Recent Emails
# --------------------------------------------------

@mcp.tool()
def gmail_recent_emails(
    max_results: int = 10
) -> list[dict[str, Any]]:

    """Get the user's most recent Gmail messages."""

    logger.info("Getting recent Gmail messages")

    max_results = max(
        1,
        min(max_results, 25)
    )

    emails = get_recent_emails(
        max_results=max_results
    )

    return emails

# --------------------------------------------------
# Tool 2: Search Gmail
# --------------------------------------------------

@mcp.tool()
def gmail_search(
    query: str,
    max_results: int = 10
) -> list[dict[str, Any]]:

    """Search Gmail using a Gmail search query."""

    if not query.strip():
        return []

    logger.info(
        "Searching Gmail: %s",
        query
    )

    max_results = max(
        1,
        min(max_results, 25)
    )

    emails = search_emails(
        query=query,
        max_results=max_results
    )

    return emails


# --------------------------------------------------
# Tool 3: Get Email
# --------------------------------------------------

@mcp.tool()
def gmail_get_email(
    message_id: str
) -> dict[str, Any]:

    """Get one Gmail message by its Gmail message ID."""

    logger.info(
        "Getting Gmail message"
    )

    email = get_email(
        message_id
    )

    return email


if __name__ == "__main__":
    mcp.run(
        transport="stdio"
    )