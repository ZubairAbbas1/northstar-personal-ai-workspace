from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx

from backend.auth.security import create_access_token, decode_access_token
from backend.config import settings


GOOGLE_SCOPES = {
    "gmail": [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
    ],
    "google_calendar": [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/calendar.readonly",
    ],
}
GITHUB_SCOPES = ["read:user", "user:email", "repo"]
SUPPORTED_OAUTH_PROVIDERS = {*GOOGLE_SCOPES, "github"}


def callback_url(provider: str) -> str:
    callback_provider = "google" if provider in GOOGLE_SCOPES else provider
    return (
        f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}"
        f"{settings.API_PREFIX}/integrations/{callback_provider}/callback"
    )


def create_oauth_state(user_id: UUID, provider: str) -> str:
    if provider not in SUPPORTED_OAUTH_PROVIDERS:
        raise ValueError("Unsupported OAuth provider")
    return create_access_token(
        subject=str(user_id),
        expires_delta=timedelta(minutes=10),
        extra_claims={"type": "oauth_state", "provider": provider},
    )


def parse_oauth_state(state: str, expected_callback: str) -> tuple[UUID, str]:
    payload = decode_access_token(state)
    provider = payload.get("provider")
    callback_provider = "google" if provider in GOOGLE_SCOPES else provider
    if payload.get("type") != "oauth_state" or callback_provider != expected_callback:
        raise ValueError("Invalid OAuth state")
    if provider not in SUPPORTED_OAUTH_PROVIDERS:
        raise ValueError("Unsupported OAuth provider")
    try:
        user_id = UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid OAuth state") from exc
    return user_id, provider


def authorization_url(provider: str, user_id: UUID) -> str:
    state = create_oauth_state(user_id, provider)
    if provider in GOOGLE_SCOPES:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise RuntimeError("Google OAuth is not configured")
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": callback_url(provider),
                "response_type": "code",
                "scope": " ".join(GOOGLE_SCOPES[provider]),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )

    if provider == "github":
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise RuntimeError("GitHub OAuth is not configured")
        return "https://github.com/login/oauth/authorize?" + urlencode(
            {
                "client_id": settings.GITHUB_CLIENT_ID,
                "redirect_uri": callback_url(provider),
                "scope": " ".join(GITHUB_SCOPES),
                "state": state,
            }
        )
    raise ValueError("Unsupported OAuth provider")


async def exchange_google_code(code: str, provider: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": callback_url(provider),
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        profile_response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        profile_response.raise_for_status()
        profile = profile_response.json()

    token_data.update(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "scopes": GOOGLE_SCOPES[provider],
            "account_email_or_id": profile.get("email") or profile.get("sub"),
        }
    )
    return token_data


async def exchange_github_code(code: str) -> dict[str, Any]:
    headers = {"Accept": "application/json", "User-Agent": "Northstar-Workspace"}
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers=headers,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": callback_url("github"),
            },
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        if "access_token" not in token_data:
            raise ValueError(token_data.get("error_description") or "GitHub OAuth failed")
        profile_response = await client.get(
            "https://api.github.com/user",
            headers={**headers, "Authorization": f"Bearer {token_data['access_token']}"},
        )
        profile_response.raise_for_status()
        profile = profile_response.json()

    token_data.update(
        {
            "scopes": GITHUB_SCOPES,
            "account_email_or_id": f"@{profile['login']}",
        }
    )
    return token_data


def token_expiry(token_data: dict[str, Any]) -> datetime | None:
    expires_in = token_data.get("expires_in")
    if not expires_in:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
