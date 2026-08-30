import logging
from typing import Any, List
import httpx

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


class SlackConnectionError(RuntimeError):
    """A safe, user-facing Slack connection or synchronization error."""

    def __init__(self, message: str, *, requires_reauth: bool = False):
        super().__init__(message)
        self.requires_reauth = requires_reauth


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token.strip()}",
        "User-Agent": "Northstar-Workspace/1.0",
    }


def _slack_error(payload: dict[str, Any]) -> SlackConnectionError:
    error = str(payload.get("error") or "unknown_error")
    if error == "missing_scope":
        return SlackConnectionError(
            "This Slack user token is missing the search:read user scope. Add the scope, reinstall the Slack app, and reconnect.",
            requires_reauth=True,
        )
    if error in {"invalid_auth", "not_authed", "account_inactive", "token_expired", "token_revoked"}:
        return SlackConnectionError(
            "Slack rejected or revoked this user token. Reinstall the Slack app and reconnect.",
            requires_reauth=True,
        )
    if error == "not_allowed_token_type":
        return SlackConnectionError(
            "Slack mention search requires a User OAuth Token beginning with xoxp-, not a bot or app token.",
            requires_reauth=True,
        )
    if error == "ratelimited":
        return SlackConnectionError("Slack is rate-limiting this connection. Wait a moment and try again.")
    return SlackConnectionError(f"Slack could not complete the request ({error}).")


async def _request(
    client: httpx.AsyncClient,
    api_method: str,
    token: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = await client.request(
            "POST" if api_method == "auth.test" else "GET",
            f"{SLACK_API_BASE}/{api_method}",
            headers=_headers(token),
            params=params,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Slack request %s failed: %s", api_method, exc)
        raise SlackConnectionError("Slack could not be reached. Check the network connection and try again.") from exc
    payload = response.json()
    if not payload.get("ok"):
        raise _slack_error(payload)
    return payload


async def validate_slack_user_token(token: str) -> dict[str, str]:
    """Validate the exact user token and scope required by mention search."""
    clean = token.strip()
    if not clean.startswith("xoxp-"):
        raise SlackConnectionError(
            "Use a Slack User OAuth Token beginning with xoxp-. Bot tokens cannot search your mentions.",
            requires_reauth=True,
        )
    async with httpx.AsyncClient(timeout=12.0) as client:
        identity = await _request(client, "auth.test", clean)
        # A successful empty search proves search:read is present without requiring messages to exist.
        await _request(client, "search.messages", clean, params={"query": "to:me", "count": 1})
    return {
        "user": str(identity.get("user") or "Slack user"),
        "team": str(identity.get("team") or "Slack workspace"),
        "user_id": str(identity.get("user_id") or ""),
        "team_id": str(identity.get("team_id") or ""),
    }


async def fetch_slack_mentions(
    token_data: dict[str, Any] | None,
) -> List[dict[str, Any]]:
    """Fetches recent mentions or important messages for the user from Slack."""
    if not token_data or not token_data.get("access_token"):
        return []

    token = str(token_data.get("access_token") or "").strip()
    if not token.startswith("xoxp-"):
        raise SlackConnectionError(
            "Slack mention search requires a User OAuth Token beginning with xoxp-. Reconnect Slack.",
            requires_reauth=True,
        )
    async with httpx.AsyncClient(timeout=12.0) as client:
        data = await _request(
            client,
            "search.messages",
            token,
            params={"query": "to:me", "count": 10, "sort": "timestamp", "sort_dir": "desc"},
        )
    matches = data.get("messages", {}).get("matches", [])
    return [
        {
            "text": str(match.get("text") or "").strip(),
            "username": match.get("username") or "Slack member",
            "channel": (match.get("channel") or {}).get("name") or "channel",
            "permalink": match.get("permalink"),
            "ts": str(match.get("ts") or ""),
        }
        for match in matches
    ]
