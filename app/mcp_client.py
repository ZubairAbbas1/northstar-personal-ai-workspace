import logging
from pathlib import Path
import sys
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

GMAIL_SERVER = BASE_DIR / "mcp_servers" / "gmail_server.py"
CALENDAR_SERVER = BASE_DIR / "mcp_servers" / "calendar_server.py"
TASKS_SERVER = BASE_DIR / "mcp_servers" / "tasks_server.py"

# Server configuration
server_configs: dict[str, Any] = {
    "gmail": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(GMAIL_SERVER)],
    },
    "calendar": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(CALENDAR_SERVER)],
    },
}

if TASKS_SERVER.exists():
    server_configs["tasks"] = {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(TASKS_SERVER)],
    }

client = MultiServerMCPClient(server_configs)


async def get_gmail_tools():
    """Retrieves tools from the Gmail MCP server."""
    try:
        return await client.get_tools(server_name="gmail")
    except Exception as e:
        logger.exception("Failed to get Gmail tools: %s", e)
        return []


async def get_calendar_tools():
    """Retrieves tools from the Calendar MCP server."""
    try:
        return await client.get_tools(server_name="calendar")
    except Exception as e:
        logger.exception("Failed to get Calendar tools: %s", e)
        return []


async def get_tasks_tools():
    """Retrieves tools from the Tasks MCP server."""
    try:
        return await client.get_tools(server_name="tasks")
    except Exception as e:
        logger.exception("Failed to get Tasks tools: %s", e)
        return []