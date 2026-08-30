import logging
from typing import Any, List
import httpx

logger = logging.getLogger(__name__)


async def fetch_slack_mentions(
    token_data: dict[str, Any] | None,
) -> List[dict[str, Any]]:
    """Fetches recent mentions or important messages for the user from Slack."""
    if not token_data or not token_data.get("access_token"):
        return []

    token = token_data.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://slack.com/api/search.messages?query=to:me&count=10",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    matches = data.get("messages", {}).get("matches", [])
                    return [
                        {
                            "text": m.get("text"),
                            "username": m.get("username"),
                            "channel": m.get("channel", {}).get("name"),
                            "permalink": m.get("permalink"),
                            "ts": m.get("ts"),
                        }
                        for m in matches
                    ]
    except Exception as e:
        logger.warning("Failed to fetch Slack mentions: %s", e)
    return []
