import json
import logging
from typing import Annotated, Any, Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_active_user
from backend.config import settings
from backend.db.session import get_db
from backend.models.integration import IntegrationAccount
from backend.models.user import User
from backend.integrations.gmail import GmailConnectionError, validate_gmail_app_password
from backend.integrations.discord import (
    DiscordConnectionError,
    fetch_accessible_channels,
    normalize_bot_token,
    validate_discord_bot,
)
from backend.integrations.slack import SlackConnectionError, validate_slack_user_token
from backend.services.crypto_service import crypto_service
from backend.services.oauth_service import (
    GOOGLE_SCOPES,
    authorization_url,
    exchange_github_code,
    exchange_google_code,
    parse_oauth_state,
    token_expiry,
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])
logger = logging.getLogger(__name__)

AVAILABLE_INTEGRATIONS = [
    {"id": "gmail", "name": "Gmail", "category": "Communication", "description": "Read and triage your inbox, then draft replies for your review.", "icon": "mail", "supported_scopes": ["Read email", "Search inbox", "Draft replies"], "is_available": True, "token_guide": "Use Google OAuth or a Google App Password."},
    {"id": "google_calendar", "name": "Google Calendar", "category": "Planning", "description": "Bring today's meetings and schedule context into your workspace.", "icon": "calendar", "supported_scopes": ["Read events", "Meeting context"], "is_available": True, "token_guide": "Use Google OAuth for Calendar access."},
    {"id": "github", "name": "GitHub", "category": "Development", "description": "Connect repository, pull request, and issue context.", "icon": "github", "supported_scopes": ["Read repositories", "Read issues and pull requests"], "is_available": True, "token_guide": "Use GitHub OAuth or a fine-grained personal access token."},
    {"id": "slack", "name": "Slack", "category": "Communication", "description": "Read your recent Slack mentions using a user-scoped Slack token.", "icon": "message-square", "supported_scopes": ["Search messages mentioning you"], "is_available": True, "token_guide": "Use a User OAuth Token beginning with xoxp- and the search:read user scope."},
    {"id": "discord", "name": "Discord", "category": "Communication", "description": "Read recent messages from only the server channels you select.", "icon": "discord", "supported_scopes": ["List servers", "Read selected channels", "Read message history"], "is_available": True, "token_guide": "Paste a bot token from the Discord Developer Portal. Never use your personal Discord account token."},
]
INTEGRATIONS_BY_ID = {item["id"]: item for item in AVAILABLE_INTEGRATIONS}


class IntegrationItemResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    icon: str
    supported_scopes: list[str]
    is_available: bool
    status: str
    account_email_or_id: str | None = None
    connected_at: Any | None = None
    token_guide: str | None = None
    oauth_ready: bool = True
    setup_message: str | None = None
    connection_error: str | None = None


class ConnectIntegrationRequest(BaseModel):
    account_email_or_id: str | None = None
    token_or_key: str
    connection_type: Literal["token", "app_password"] = "token"


class DiscordChannelResponse(BaseModel):
    id: str
    name: str
    guild_id: str
    guild_name: str
    selected: bool = False


class DiscordChannelSelectionRequest(BaseModel):
    channel_ids: list[str] = Field(default_factory=list, max_length=10)


def _oauth_readiness(provider: str) -> tuple[bool, str | None]:
    if provider in GOOGLE_SCOPES:
        ready = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
        return ready, None if ready else "Google OAuth setup is required before this connection can be authorized."
    if provider == "github":
        ready = bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)
        return ready, None if ready else "GitHub OAuth setup is required, or you can use an access token."
    return True, None


def _response(meta: dict[str, Any], account: IntegrationAccount | None) -> IntegrationItemResponse:
    oauth_ready, setup_message = _oauth_readiness(meta["id"])
    missing_credential = bool(account and not account.encrypted_access_token)
    return IntegrationItemResponse(
        **meta,
        status="error" if missing_credential else account.status if account else "disconnected",
        account_email_or_id=account.account_email_or_id if account else None,
        connected_at=account.created_at if account else None,
        oauth_ready=oauth_ready,
        setup_message=setup_message,
        connection_error=(
            "The saved credential is missing. Reconnect this integration."
            if missing_credential
            else account.error_message if account else None
        ),
    )


async def _upsert_account(
    db: AsyncSession,
    user_id: Any,
    provider: str,
    account_label: str,
    access_token: str,
    refresh_token: str | None = None,
    scopes: list[str] | None = None,
    expires_at: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> IntegrationAccount:
    result = await db.execute(select(IntegrationAccount).where(IntegrationAccount.user_id == user_id, IntegrationAccount.provider == provider))
    account = result.scalar_one_or_none()
    if account is None:
        account = IntegrationAccount(user_id=user_id, provider=provider)
        db.add(account)
    account.account_email_or_id = account_label
    account.encrypted_access_token = crypto_service.encrypt(access_token)
    account.encrypted_refresh_token = crypto_service.encrypt(refresh_token)
    account.token_expires_at = expires_at
    account.scopes = json.dumps(scopes or [])
    if metadata is not None:
        account.metadata_json = json.dumps(metadata)
    account.status = "connected"
    account.error_message = None
    await db.commit()
    await db.refresh(account)
    return account


@router.get("", response_model=list[IntegrationItemResponse])
async def list_integrations(current_user: Annotated[User, Depends(get_current_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(IntegrationAccount).where(IntegrationAccount.user_id == current_user.id))
    accounts = {account.provider: account for account in result.scalars().all()}
    return [_response(item, accounts.get(item["id"])) for item in AVAILABLE_INTEGRATIONS]


@router.post("/{provider}/connect", response_model=IntegrationItemResponse)
async def connect_integration(provider: str, data: ConnectIntegrationRequest, current_user: Annotated[User, Depends(get_current_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Connect a provider using its supported credential flow."""
    provider = provider.lower()
    meta = INTEGRATIONS_BY_ID.get(provider)
    if not meta:
        raise HTTPException(status_code=404, detail="Integration is not supported")
    token = data.token_or_key.strip()
    if not token:
        raise HTTPException(status_code=422, detail="A token or app password is required")

    if provider in GOOGLE_SCOPES:
        if provider != "gmail" or data.connection_type != "app_password":
            raise HTTPException(status_code=400, detail="Use Google OAuth to connect this integration")
        email = (data.account_email_or_id or "").strip().lower()
        if "@" not in email:
            raise HTTPException(status_code=422, detail="A valid Google email address is required")
        try:
            await validate_gmail_app_password(email, token)
        except GmailConnectionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        encrypted_payload = json.dumps({"email": email, "app_password": token})
        account = await _upsert_account(db, current_user.id, provider, f"{email} (App Password)", encrypted_payload)
        return _response(meta, account)

    if provider == "discord":
        token = normalize_bot_token(token)
        try:
            identity = await validate_discord_bot(token)
        except DiscordConnectionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        guild_count = int(identity.get("guild_count") or 0)
        server_label = "server" if guild_count == 1 else "servers"
        label = f"{identity['username']} · {guild_count} {server_label}"
        account = await _upsert_account(
            db,
            current_user.id,
            provider,
            label,
            token,
            scopes=["guilds", "guilds.channels.read", "messages.read"],
            metadata={
                "bot_id": identity.get("id"),
                "guild_count": guild_count,
                "selected_channels": [],
            },
        )
        return _response(meta, account)

    if provider == "slack":
        try:
            identity = await validate_slack_user_token(token)
        except SlackConnectionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        label = f"{identity['user']} · {identity['team']}"
        account = await _upsert_account(
            db,
            current_user.id,
            provider,
            label,
            token,
            scopes=["search:read"],
            metadata={"user_id": identity.get("user_id"), "team_id": identity.get("team_id")},
        )
        return _response(meta, account)

    headers = {"Authorization": f"Bearer {token}", "User-Agent": "Northstar-Workspace"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if provider == "github":
                response = await client.get("https://api.github.com/user", headers=headers)
                response.raise_for_status()
                label = f"@{response.json()['login']}"
            else:
                raise HTTPException(status_code=400, detail="Unsupported connection method")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="The provider rejected this credential") from exc

    account = await _upsert_account(db, current_user.id, provider, label, token)
    return _response(meta, account)


async def _discord_account(db: AsyncSession, user_id: Any) -> IntegrationAccount:
    result = await db.execute(
        select(IntegrationAccount).where(
            IntegrationAccount.user_id == user_id,
            IntegrationAccount.provider == "discord",
        )
    )
    account = result.scalar_one_or_none()
    if not account or not account.encrypted_access_token:
        raise HTTPException(status_code=409, detail="Connect Discord before choosing channels")
    return account


def _account_metadata(account: IntegrationAccount) -> dict[str, Any]:
    try:
        payload = json.loads(account.metadata_json or "{}")
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


@router.get("/discord/channels", response_model=list[DiscordChannelResponse])
async def list_discord_channels(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    account = await _discord_account(db, current_user.id)
    token = crypto_service.decrypt(account.encrypted_access_token) or ""
    selected_ids = {
        str(item.get("id"))
        for item in _account_metadata(account).get("selected_channels", [])
        if isinstance(item, dict) and item.get("id")
    }
    try:
        channels = await fetch_accessible_channels(token)
    except DiscordConnectionError as exc:
        account.status = "needs_reauth" if exc.requires_reauth else "connected"
        account.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if account.status != "connected" or account.error_message:
        account.status = "connected"
        account.error_message = None
        await db.commit()
    return [DiscordChannelResponse(**channel, selected=channel["id"] in selected_ids) for channel in channels]


@router.put("/discord/channels", response_model=list[DiscordChannelResponse])
async def update_discord_channels(
    data: DiscordChannelSelectionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    account = await _discord_account(db, current_user.id)
    token = crypto_service.decrypt(account.encrypted_access_token) or ""
    requested_ids = list(dict.fromkeys(data.channel_ids))
    try:
        channels = await fetch_accessible_channels(token)
    except DiscordConnectionError as exc:
        account.status = "needs_reauth" if exc.requires_reauth else "connected"
        account.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    accessible = {channel["id"]: channel for channel in channels}
    missing = [channel_id for channel_id in requested_ids if channel_id not in accessible]
    if missing:
        raise HTTPException(status_code=422, detail="One or more selected Discord channels are no longer accessible")
    metadata = _account_metadata(account)
    metadata["selected_channels"] = [accessible[channel_id] for channel_id in requested_ids]
    account.metadata_json = json.dumps(metadata)
    account.status = "connected"
    account.error_message = None
    await db.commit()
    selected = set(requested_ids)
    return [DiscordChannelResponse(**channel, selected=channel["id"] in selected) for channel in channels]


@router.get("/{provider}/oauth-url")
async def get_oauth_url(provider: str, current_user: Annotated[User, Depends(get_current_active_user)]):
    provider = provider.lower()
    try:
        url = authorization_url(provider, current_user.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"url": url, "provider": provider}


def _frontend_redirect(**params: str) -> RedirectResponse:
    return RedirectResponse(url=f"{settings.FRONTEND_URL.rstrip('/')}/integrations?{urlencode(params)}", status_code=status.HTTP_302_FOUND)


async def _oauth_user(db: AsyncSession, state: str, callback_provider: str) -> tuple[User, str]:
    user_id, provider = parse_oauth_state(state, callback_provider)
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise ValueError("OAuth user is unavailable")
    return user, provider


@router.get("/google/callback")
async def google_oauth_callback(db: Annotated[AsyncSession, Depends(get_db)], code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code or not state:
        return _frontend_redirect(error="google_authorization_cancelled")
    try:
        user, provider = await _oauth_user(db, state, "google")
        token_data = await exchange_google_code(code, provider)
        await _upsert_account(db, user.id, provider, token_data["account_email_or_id"], json.dumps(token_data), token_data.get("refresh_token"), token_data.get("scopes"), token_expiry(token_data))
        return _frontend_redirect(connected=provider)
    except Exception as exc:
        logger.warning("Google OAuth callback failed: %s", exc)
        await db.rollback()
        return _frontend_redirect(error="google_connection_failed")


@router.get("/github/callback")
async def github_oauth_callback(db: Annotated[AsyncSession, Depends(get_db)], code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code or not state:
        return _frontend_redirect(error="github_authorization_cancelled")
    try:
        user, provider = await _oauth_user(db, state, "github")
        token_data = await exchange_github_code(code)
        await _upsert_account(db, user.id, provider, token_data["account_email_or_id"], token_data["access_token"], scopes=token_data.get("scopes"))
        return _frontend_redirect(connected=provider)
    except Exception:
        await db.rollback()
        return _frontend_redirect(error="github_connection_failed")


@router.post("/{provider}/disconnect")
async def disconnect_integration(provider: str, current_user: Annotated[User, Depends(get_current_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(IntegrationAccount).where(IntegrationAccount.user_id == current_user.id, IntegrationAccount.provider == provider.lower()))
    account = result.scalar_one_or_none()
    if account:
        await db.delete(account)
        await db.commit()
    return {"message": f"{provider} disconnected successfully"}
