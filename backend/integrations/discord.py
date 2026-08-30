from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"
READABLE_CHANNEL_TYPES = {0, 5}  # Guild text and announcement channels.


class DiscordConnectionError(RuntimeError):
    """A safe, user-facing Discord connection or synchronization error."""

    def __init__(self, message: str, *, requires_reauth: bool = False):
        super().__init__(message)
        self.requires_reauth = requires_reauth


def normalize_bot_token(token: str) -> str:
    clean = token.strip()
    if clean.lower().startswith("bot "):
        clean = clean[4:].strip()
    return clean


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bot {normalize_bot_token(token)}",
        "User-Agent": "Northstar-Workspace/1.0",
    }


def _friendly_error(response: httpx.Response) -> DiscordConnectionError:
    if response.status_code == 401:
        return DiscordConnectionError(
            "Discord rejected this bot token. Reset the token in the Developer Portal and reconnect.",
            requires_reauth=True,
        )
    if response.status_code == 403:
        return DiscordConnectionError("The Discord bot does not have permission to view this server or channel.")
    if response.status_code == 429:
        return DiscordConnectionError("Discord is rate-limiting this connection. Wait a moment and try again.")
    return DiscordConnectionError("Discord could not be reached. Check the bot setup and try again.")


async def _get(client: httpx.AsyncClient, path: str, token: str, params: dict[str, Any] | None = None) -> Any:
    response: httpx.Response | None = None
    for attempt in range(3):
        try:
            response = await client.get(f"{DISCORD_API_BASE}{path}", headers=_headers(token), params=params)
        except httpx.HTTPError as exc:
            logger.warning("Discord request failed: %s", exc)
            raise DiscordConnectionError("Discord could not be reached. Check the network connection and try again.") from exc
        if response.status_code != 429 or attempt == 2:
            break
        retry_after = 1.0
        try:
            payload = response.json()
            retry_after = float(payload.get("retry_after") or response.headers.get("retry-after") or 1)
        except (TypeError, ValueError):
            try:
                retry_after = float(response.headers.get("retry-after") or 1)
            except ValueError:
                retry_after = 1.0
        retry_after = min(max(retry_after, 0.1), 5.0)
        logger.info("Discord rate limit for %s; retrying in %.2f seconds", path, retry_after)
        await asyncio.sleep(retry_after)
    assert response is not None
    if response.is_error:
        logger.warning("Discord request %s failed with status %s", path, response.status_code)
        raise _friendly_error(response)
    return response.json()


async def validate_discord_bot(token: str) -> dict[str, Any]:
    """Validate a Discord bot token and return a safe identity summary."""
    clean = normalize_bot_token(token)
    if not clean:
        raise DiscordConnectionError("Enter a Discord bot token.")
    async with httpx.AsyncClient(timeout=12.0) as client:
        profile = await _get(client, "/users/@me", clean)
        if not profile.get("bot"):
            raise DiscordConnectionError("Use a Discord bot token, not a personal Discord account token.")
        guilds = await _get(client, "/users/@me/guilds", clean)
    return {
        "id": str(profile.get("id") or ""),
        "username": profile.get("global_name") or profile.get("username") or "Discord bot",
        "guild_count": len(guilds),
    }


async def fetch_accessible_channels(token: str) -> list[dict[str, str]]:
    """Return text channels visible to the bot, grouped with their server names."""
    clean = normalize_bot_token(token)
    async with httpx.AsyncClient(timeout=12.0) as client:
        guilds = await _get(client, "/users/@me/guilds", clean)
        channels: list[dict[str, str]] = []
        for guild in guilds[:50]:
            guild_id = str(guild.get("id") or "")
            if not guild_id:
                continue
            try:
                guild_channels = await _get(client, f"/guilds/{guild_id}/channels", clean)
            except DiscordConnectionError as exc:
                logger.info("Skipping inaccessible Discord server %s: %s", guild_id, exc)
                continue
            for channel in guild_channels:
                if channel.get("type") not in READABLE_CHANNEL_TYPES:
                    continue
                channels.append(
                    {
                        "id": str(channel.get("id") or ""),
                        "name": str(channel.get("name") or "unnamed-channel"),
                        "guild_id": guild_id,
                        "guild_name": str(guild.get("name") or "Discord server"),
                    }
                )
    return sorted(channels, key=lambda item: (item["guild_name"].lower(), item["name"].lower()))


async def fetch_discord_messages(
    token: str,
    selected_channels: list[dict[str, str]],
    limit_per_channel: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent messages only from the user's explicit channel allow-list."""
    clean = normalize_bot_token(token)
    limit = max(1, min(limit_per_channel, 25))
    messages: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=12.0) as client:
        for selected in selected_channels[:10]:
            channel_id = str(selected.get("id") or "")
            if not channel_id:
                continue
            payload = await _get(client, f"/channels/{channel_id}/messages", clean, {"limit": limit})
            for message in payload:
                author = message.get("author") or {}
                content = str(message.get("content") or "").strip()
                messages.append(
                    {
                        "id": str(message.get("id") or ""),
                        "content": content,
                        "author": author.get("global_name") or author.get("username") or "Unknown member",
                        "timestamp": str(message.get("timestamp") or ""),
                        "channel_id": channel_id,
                        "channel_name": selected.get("name") or "channel",
                        "guild_name": selected.get("guild_name") or "Discord server",
                        "attachment_count": len(message.get("attachments") or []),
                    }
                )
    return sorted(messages, key=lambda item: item["timestamp"], reverse=True)
