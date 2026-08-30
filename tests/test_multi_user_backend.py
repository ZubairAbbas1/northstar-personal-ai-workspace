import json
import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
import pytest_asyncio
import httpx
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.config import settings
from backend.api.v1.assistant import detect_intent, smart_inbox_response
from backend.api.v1.inbox import EmailItemResponse, InboxStatusResponse
from backend.db.base import Base
from backend.db.session import get_db
from backend.main import app
from backend.services.crypto_service import encrypt_secret, decrypt_secret, mask_secret
from agents.model_factory import resolve_model_name
from backend.services.oauth_service import create_oauth_state, parse_oauth_state
from backend.integrations.calendar import GoogleCalendarError
from backend.integrations.gmail import GmailConnectionError
from backend.integrations.discord import _get as discord_get
from backend.integrations.slack import SlackConnectionError, fetch_slack_mentions, validate_slack_user_token
from backend.models.integration import IntegrationAccount
from backend.models.user import User

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def test_crypto_service_encryption_decryption():
    secret = "unit-test-encryption-value"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    assert len(encrypted) > len(secret)

    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret


def test_crypto_service_masking():
    secret = "unit-test-masking-value-1234"
    masked = mask_secret(secret)
    assert masked.startswith("uni")
    assert masked.endswith("1234")
    assert "••••" in masked


def test_model_factory_routing():
    # Fast mode
    assert resolve_model_name("groq", "fast", "simple") == "openai/gpt-oss-20b"
    assert resolve_model_name("openai", "fast", "complex") == "gpt-4o-mini"

    # Balanced mode
    assert resolve_model_name("groq", "balanced", "simple") == "openai/gpt-oss-20b"
    assert resolve_model_name("groq", "balanced", "complex") == "openai/gpt-oss-120b"

    # Quality mode
    assert resolve_model_name("groq", "quality", "simple") == "openai/gpt-oss-120b"
    assert resolve_model_name("openai", "quality", "complex") == "gpt-4o"


def test_smart_inbox_response_answers_latest_email_question():
    inbox = InboxStatusResponse(
        is_connected=True,
        account_email="user@example.com",
        connection_status="connected",
        total_emails=2,
        urgent_count=0,
        action_needed_count=1,
        fyi_count=1,
        ignore_count=0,
        emails=[
            EmailItemResponse(
                id="latest",
                sender="Alex <alex@example.com>",
                subject="Project update",
                snippet="The launch checklist is ready.",
                category="fyi",
                reason="Informational",
                date="2026-08-29 17:00",
                is_live_sync=True,
            ),
            EmailItemResponse(
                id="older",
                sender="Sam <sam@example.com>",
                subject="Review requested",
                snippet="Please review the proposal.",
                category="action_needed",
                reason="Reply requested",
                date="2026-08-29 16:00",
                is_live_sync=True,
            ),
        ],
    )

    response = smart_inbox_response("What is my latest email?", inbox)

    assert "Project update" in response
    assert "Alex" in response
    assert "launch checklist" in response
    assert "0 urgent" not in response


def test_assistant_routes_calendar_questions_to_live_calendar():
    assert detect_intent("What is on my calendar for tomorrow?") == "calendar_query"
    assert detect_intent("Show my schedule today") == "calendar_query"


def test_assistant_routes_github_questions_to_connected_context():
    assert detect_intent("Can you check my repos on my GitHub profile?") == "github"
    assert detect_intent("Show my open pull requests") == "github"


def test_assistant_routes_discord_questions_to_selected_channels():
    assert detect_intent("What is the latest message in Discord?") == "discord"


def test_assistant_routes_slack_questions_to_connected_context():
    assert detect_intent("What is my latest Slack mention?") == "slack"


@pytest.mark.asyncio
async def test_slack_requires_user_token_and_search_scope(monkeypatch):
    with pytest.raises(SlackConnectionError, match="User OAuth Token"):
        await validate_slack_user_token("xoxb-unit-test-bot-token")

    calls: list[tuple[str, dict | None]] = []

    class FakeSlackClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, headers=None, params=None):
            api_method = url.rsplit("/", 1)[-1]
            calls.append((api_method, params))
            payload = (
                {"ok": True, "user": "Zubair", "team": "Northstar", "user_id": "U1", "team_id": "T1"}
                if api_method == "auth.test"
                else {"ok": True, "messages": {"matches": []}}
            )
            return httpx.Response(200, request=httpx.Request(method, url), json=payload)

    monkeypatch.setattr("backend.integrations.slack.httpx.AsyncClient", lambda **kwargs: FakeSlackClient())
    identity = await validate_slack_user_token("xoxp-unit-test-user-token")
    mentions = await fetch_slack_mentions({"access_token": "xoxp-unit-test-user-token"})

    assert identity == {"user": "Zubair", "team": "Northstar", "user_id": "U1", "team_id": "T1"}
    assert mentions == []
    assert calls == [
        ("auth.test", None),
        ("search.messages", {"query": "to:me", "count": 1}),
        ("search.messages", {"query": "to:me", "count": 10, "sort": "timestamp", "sort_dir": "desc"}),
    ]


@pytest.mark.asyncio
async def test_discord_rate_limit_is_retried_automatically():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"retry_after": 0})
        return httpx.Response(200, json={"id": "bot-1", "bot": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        payload = await discord_get(client, "/users/@me", "test-token")

    assert calls == 2
    assert payload["id"] == "bot-1"


@pytest.mark.asyncio
async def test_assistant_lists_repositories_from_connected_github(client, db_session, monkeypatch):
    response = await client.post("/api/v1/auth/register", json={
        "email": "github-assistant@example.com",
        "password": "Password123!",
        "full_name": "GitHub Assistant",
    })
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    user = (await db_session.execute(select(User).where(User.email == "github-assistant@example.com"))).scalar_one()
    db_session.add(IntegrationAccount(
        user_id=user.id,
        provider="github",
        account_email_or_id="@octocat",
        encrypted_access_token=encrypt_secret("test-github-token"),
        status="connected",
    ))
    await db_session.commit()

    async def repositories(token_data, max_results=10):
        assert token_data == {"access_token": "test-github-token"}
        assert max_results == 10
        return [{
            "full_name": "octocat/hello-world",
            "description": "A test repository",
            "private": False,
            "language": "Python",
        }]

    monkeypatch.setattr("backend.api.v1.assistant.fetch_github_repositories", repositories)
    answer = await client.post(
        "/api/v1/assistant/chat",
        headers=headers,
        json={"message": "Can you check my repos on GitHub?"},
    )

    assert answer.status_code == 200
    assert answer.json()["intent"] == "github"
    assert "octocat/hello-world" in answer.json()["response"]
    assert answer.json()["sources_used"] == ["github"]


@pytest.mark.asyncio
async def test_discord_connection_channel_allow_list_and_assistant(client, db_session, monkeypatch):
    response = await client.post("/api/v1/auth/register", json={
        "email": "discord-assistant@example.com",
        "password": "Password123!",
        "full_name": "Discord Assistant",
    })
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def validate_bot(token: str):
        assert token == "test-discord-bot-token"
        return {"id": "bot-1", "username": "Northstar Bot", "guild_count": 1}

    channels = [
        {"id": "channel-1", "name": "product", "guild_id": "guild-1", "guild_name": "Northstar Team"},
        {"id": "channel-2", "name": "random", "guild_id": "guild-1", "guild_name": "Northstar Team"},
    ]

    async def accessible_channels(token: str):
        assert token == "test-discord-bot-token"
        return channels

    monkeypatch.setattr("backend.api.v1.integrations.validate_discord_bot", validate_bot)
    monkeypatch.setattr("backend.api.v1.integrations.fetch_accessible_channels", accessible_channels)

    connected = await client.post(
        "/api/v1/integrations/discord/connect",
        headers=headers,
        json={"connection_type": "token", "token_or_key": "Bot test-discord-bot-token"},
    )
    assert connected.status_code == 200
    assert connected.json()["status"] == "connected"
    assert "Northstar Bot" in connected.json()["account_email_or_id"]

    user = (await db_session.execute(select(User).where(User.email == "discord-assistant@example.com"))).scalar_one()
    account = (await db_session.execute(select(IntegrationAccount).where(
        IntegrationAccount.user_id == user.id,
        IntegrationAccount.provider == "discord",
    ))).scalar_one()
    assert decrypt_secret(account.encrypted_access_token) == "test-discord-bot-token"
    assert "test-discord-bot-token" not in connected.text

    available = await client.get("/api/v1/integrations/discord/channels", headers=headers)
    assert available.status_code == 200
    assert all(not channel["selected"] for channel in available.json())

    selected = await client.put(
        "/api/v1/integrations/discord/channels",
        headers=headers,
        json={"channel_ids": ["channel-1"]},
    )
    assert selected.status_code == 200
    assert next(channel for channel in selected.json() if channel["id"] == "channel-1")["selected"] is True

    async def recent_messages(token: str, selected_channels, limit_per_channel=10):
        assert token == "test-discord-bot-token"
        assert [channel["id"] for channel in selected_channels] == ["channel-1"]
        return [{
            "id": "message-1",
            "content": "The launch checklist is ready.",
            "author": "Alex",
            "timestamp": "2026-08-30T10:00:00+00:00",
            "channel_id": "channel-1",
            "channel_name": "product",
            "guild_name": "Northstar Team",
            "attachment_count": 0,
        }]

    monkeypatch.setattr("backend.api.v1.assistant.fetch_discord_messages", recent_messages)
    answer = await client.post(
        "/api/v1/assistant/chat",
        headers=headers,
        json={"message": "What is the latest Discord message?"},
    )
    assert answer.status_code == 200
    assert answer.json()["intent"] == "discord"
    assert "launch checklist" in answer.json()["response"]
    assert answer.json()["sources_used"] == ["discord"]


@pytest.mark.asyncio
async def test_slack_connection_and_assistant_mentions(client, db_session, monkeypatch):
    response = await client.post("/api/v1/auth/register", json={
        "email": "slack-assistant@example.com",
        "password": "Password123!",
        "full_name": "Slack Assistant",
    })
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def validate_user_token(token: str):
        assert token == "xoxp-unit-test-user-token"
        return {"user": "Zubair", "team": "Northstar", "user_id": "U1", "team_id": "T1"}

    monkeypatch.setattr("backend.api.v1.integrations.validate_slack_user_token", validate_user_token)
    connected = await client.post(
        "/api/v1/integrations/slack/connect",
        headers=headers,
        json={"connection_type": "token", "token_or_key": "xoxp-unit-test-user-token"},
    )
    assert connected.status_code == 200
    assert connected.json()["status"] == "connected"
    assert "Zubair · Northstar" == connected.json()["account_email_or_id"]
    assert "xoxp-unit-test-user-token" not in connected.text

    user = (await db_session.execute(select(User).where(User.email == "slack-assistant@example.com"))).scalar_one()
    account = (await db_session.execute(select(IntegrationAccount).where(
        IntegrationAccount.user_id == user.id,
        IntegrationAccount.provider == "slack",
    ))).scalar_one()
    assert decrypt_secret(account.encrypted_access_token) == "xoxp-unit-test-user-token"
    assert json.loads(account.scopes) == ["search:read"]

    async def recent_mentions(token_data):
        assert token_data == {"access_token": "xoxp-unit-test-user-token"}
        return [{
            "text": "Please review the launch checklist.",
            "username": "Alex",
            "channel": "product",
            "permalink": "https://example.slack.com/archives/C1/p1",
            "ts": "1770000000.000100",
        }]

    monkeypatch.setattr("backend.api.v1.assistant.fetch_slack_mentions", recent_mentions)
    answer = await client.post(
        "/api/v1/assistant/chat",
        headers=headers,
        json={"message": "What is my latest Slack mention?"},
    )
    assert answer.status_code == 200
    assert answer.json()["intent"] == "slack"
    assert "launch checklist" in answer.json()["response"]
    assert answer.json()["sources_used"] == ["slack"]


def test_oauth_state_is_signed_and_provider_bound():
    user_id = uuid.uuid4()
    state = create_oauth_state(user_id, "gmail")
    parsed_user_id, provider = parse_oauth_state(state, "google")
    assert parsed_user_id == user_id
    assert provider == "gmail"

    with pytest.raises(ValueError):
        parse_oauth_state(state, "github")
    with pytest.raises(ValueError):
        parse_oauth_state(state + "tampered", "google")


@pytest.mark.asyncio
async def test_auth_registration_and_login(client):
    # 1. Register User
    reg_payload = {
        "email": "sarah@example.com",
        "password": "Password123!",
        "full_name": "Sarah Connor",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == "sarah@example.com"
    token = reg_data["access_token"]

    # 2. Access /me
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["full_name"] == "Sarah Connor"

    # 3. Login
    login_payload = {
        "email": "sarah@example.com",
        "password": "Password123!",
    }
    login_resp = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


@pytest.mark.asyncio
async def test_integrations_do_not_create_demo_connections(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", None)
    response = await client.post("/api/v1/auth/register", json={
        "email": "integrations@example.com",
        "password": "Password123!",
        "full_name": "Integration User",
    })
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    onboarding = await client.post(
        "/api/v1/auth/complete-onboarding",
        headers=headers,
        json={"selected_integrations": ["gmail"], "productivity_goals": []},
    )
    assert onboarding.status_code == 200

    integrations = await client.get("/api/v1/integrations", headers=headers)
    assert integrations.status_code == 200
    assert {item["id"] for item in integrations.json()} == {"gmail", "google_calendar", "github", "slack", "discord"}
    assert all(item["status"] == "disconnected" for item in integrations.json())
    assert next(item for item in integrations.json() if item["id"] == "google_calendar")["oauth_ready"] is False

    inbox = await client.get("/api/v1/inbox", headers=headers)
    assert inbox.status_code == 200
    assert inbox.json()["is_connected"] is False
    assert inbox.json()["total_emails"] == 0
    assert inbox.json()["emails"] == []

    rejected_demo = await client.post(
        "/api/v1/integrations/gmail/connect",
        headers=headers,
        json={"connection_type": "sandbox", "token_or_key": "not-a-real-credential"},
    )
    assert rejected_demo.status_code == 422

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", None)
    oauth = await client.get("/api/v1/integrations/gmail/oauth-url", headers=headers)
    assert oauth.status_code == 503

    user = (await db_session.execute(select(User).where(User.email == "integrations@example.com"))).scalar_one()
    db_session.add(IntegrationAccount(
        user_id=user.id,
        provider="gmail",
        account_email_or_id="legacy@example.com",
        status="connected",
    ))
    await db_session.commit()
    legacy = next(item for item in (await client.get("/api/v1/integrations", headers=headers)).json() if item["id"] == "gmail")
    assert legacy["status"] == "error"
    assert "missing" in legacy["connection_error"]
    legacy_inbox = (await client.get("/api/v1/inbox", headers=headers)).json()
    assert legacy_inbox["connection_status"] == "error"
    assert "missing" in legacy_inbox["sync_error"]


@pytest.mark.asyncio
async def test_gmail_credentials_are_verified_and_sync_errors_are_visible(client, monkeypatch):
    response = await client.post("/api/v1/auth/register", json={
        "email": "gmail-sync@example.com",
        "password": "Password123!",
        "full_name": "Gmail Sync User",
    })
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def reject_credentials(email: str, password: str) -> None:
        raise GmailConnectionError("Google requires a 16-character App Password.")

    monkeypatch.setattr("backend.api.v1.integrations.validate_gmail_app_password", reject_credentials)
    rejected = await client.post("/api/v1/integrations/gmail/connect", headers=headers, json={
        "connection_type": "app_password",
        "account_email_or_id": "gmail-sync@example.com",
        "token_or_key": "abcdefghijklmnop",
    })
    assert rejected.status_code == 400
    assert "App Password" in rejected.json()["detail"]
    assert next(item for item in (await client.get("/api/v1/integrations", headers=headers)).json() if item["id"] == "gmail")["status"] == "disconnected"

    async def accept_credentials(email: str, password: str) -> None:
        return None

    async def fail_sync(token_data, max_results=10):
        raise GmailConnectionError("Gmail rejected the email address or App Password.")

    monkeypatch.setattr("backend.api.v1.integrations.validate_gmail_app_password", accept_credentials)
    connected = await client.post("/api/v1/integrations/gmail/connect", headers=headers, json={
        "connection_type": "app_password",
        "account_email_or_id": "gmail-sync@example.com",
        "token_or_key": "abcdefghijklmnop",
    })
    assert connected.status_code == 200

    monkeypatch.setattr("backend.api.v1.inbox.fetch_recent_emails", fail_sync)
    inbox = await client.get("/api/v1/inbox", headers=headers)
    assert inbox.status_code == 200
    assert inbox.json()["is_connected"] is True
    assert inbox.json()["connection_status"] == "error"
    assert "rejected" in inbox.json()["sync_error"]
    gmail = next(item for item in (await client.get("/api/v1/integrations", headers=headers)).json() if item["id"] == "gmail")
    assert gmail["status"] == "error"
    assert "rejected" in gmail["connection_error"]


@pytest.mark.asyncio
async def test_calendar_sync_errors_require_reauthorization(client, db_session, monkeypatch):
    response = await client.post("/api/v1/auth/register", json={
        "email": "calendar-sync@example.com",
        "password": "Password123!",
        "full_name": "Calendar Sync User",
    })
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    user = (await db_session.execute(select(User).where(User.email == "calendar-sync@example.com"))).scalar_one()
    db_session.add(IntegrationAccount(
        user_id=user.id,
        provider="google_calendar",
        account_email_or_id=user.email,
        encrypted_access_token=encrypt_secret(json.dumps({"access_token": "expired-token"})),
        status="connected",
    ))
    await db_session.commit()

    async def fail_calendar(token_data, target_date, timezone_offset_minutes=0):
        assert isinstance(target_date, date)
        assert timezone_offset_minutes == -300
        raise GoogleCalendarError("Google Calendar authorization expired. Reconnect the calendar to continue syncing.")

    monkeypatch.setattr("backend.api.v1.calendar.fetch_events_for_date", fail_calendar)
    calendar = await client.get(
        "/api/v1/calendar/today?timezone_offset_minutes=-300", headers=headers
    )
    assert calendar.status_code == 200
    assert calendar.json()["is_connected"] is True
    assert calendar.json()["connection_status"] == "needs_reauth"
    assert "expired" in calendar.json()["sync_error"]
    integration = next(item for item in (await client.get("/api/v1/integrations", headers=headers)).json() if item["id"] == "google_calendar")
    assert integration["status"] == "needs_reauth"


@pytest.mark.asyncio
async def test_due_task_creates_actionable_notification(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "alerts@example.com",
        "password": "Password123!",
        "full_name": "Alert User",
    })
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    task = await client.post("/api/v1/tasks", headers=headers, json={
        "title": "Overdue release check",
        "priority": "urgent",
        "due_date": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    })
    assert task.status_code == 201

    notifications = await client.get("/api/v1/notifications", headers=headers)
    assert notifications.status_code == 200
    items = notifications.json()
    assert len(items) == 1
    assert items[0]["title"] == "Task overdue"
    assert items[0]["source_link"] == f"/tasks?task={task.json()['id']}"

    completed = await client.patch(
        f"/api/v1/tasks/{task.json()['id']}", headers=headers, json={"status": "completed"}
    )
    assert completed.status_code == 200
    assert (await client.get("/api/v1/notifications", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_user_task_isolation(client):
    # Register User A
    user_a_resp = await client.post("/api/v1/auth/register", json={
        "email": "userA@example.com",
        "password": "PasswordA123!",
        "full_name": "User A",
    })
    token_a = user_a_resp.json()["access_token"]

    # Register User B
    user_b_resp = await client.post("/api/v1/auth/register", json={
        "email": "userB@example.com",
        "password": "PasswordB123!",
        "full_name": "User B",
    })
    token_b = user_b_resp.json()["access_token"]

    # User A creates a task
    headers_a = {"Authorization": f"Bearer {token_a}"}
    create_resp = await client.post("/api/v1/tasks", headers=headers_a, json={
        "title": "Secret Proposal for User A",
        "priority": "high",
        "estimated_minutes": 45,
    })
    assert create_resp.status_code == 201
    task_a_id = create_resp.json()["id"]

    # User A lists tasks -> sees 1 task
    list_a = await client.get("/api/v1/tasks", headers=headers_a)
    assert len(list_a.json()) == 1
    assert list_a.json()[0]["title"] == "Secret Proposal for User A"

    # User B lists tasks -> sees 0 tasks (Isolated)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    list_b = await client.get("/api/v1/tasks", headers=headers_b)
    assert len(list_b.json()) == 0

    # User B tries to access User A's task -> 404 Not Found
    get_b = await client.get(f"/api/v1/tasks/{task_a_id}", headers=headers_b)
    assert get_b.status_code == 404


@pytest.mark.asyncio
async def test_byok_ai_settings(client):
    # Register user
    reg_resp = await client.post("/api/v1/auth/register", json={
        "email": "dev@example.com",
        "password": "Password123!",
        "full_name": "Developer",
    })
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Initial settings -> platform default
    get_resp = await client.get("/api/v1/ai-settings", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["use_platform_default"] is True

    # Update to BYOK with Groq key
    update_resp = await client.post("/api/v1/ai-settings", headers=headers, json={
        "provider": "groq",
        "api_key": "unit-test-provider-key-not-a-secret",
        "model_mode": "quality",
        "use_platform_default": False,
    })
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["use_platform_default"] is False
    assert data["provider"] == "groq"
    assert data["model_mode"] == "quality"
    # Never expose plain key
    assert "unit-test-provider-key-not-a-secret" not in str(data)
    assert "••••" in data["masked_api_key"]


@pytest.mark.asyncio
async def test_memory_search_and_assistant_are_tenant_isolated(client):
    async def register(email):
        response = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": email.split("@")[0],
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    headers_a = await register("memory-a@example.com")
    headers_b = await register("memory-b@example.com")

    memory = await client.post("/api/v1/memories", headers=headers_a, json={
        "category": "project",
        "fact": "Project Lighthouse launches on Friday",
    })
    assert memory.status_code == 201

    await client.post("/api/v1/tasks", headers=headers_a, json={
        "title": "Prepare Lighthouse launch notes",
        "priority": "urgent",
        "estimated_minutes": 25,
    })

    search_a = await client.get("/api/v1/search", headers=headers_a, params={"query": "Lighthouse"})
    search_b = await client.get("/api/v1/search", headers=headers_b, params={"query": "Lighthouse"})
    assert search_a.json()["total"] == 2
    assert search_b.json()["total"] == 0

    memories_b = await client.get("/api/v1/memories", headers=headers_b)
    assert memories_b.json() == []

    next_a = await client.post("/api/v1/assistant/chat", headers=headers_a, json={"message": "What should I do next?"})
    next_b = await client.post("/api/v1/assistant/chat", headers=headers_b, json={"message": "What should I do next?"})
    assert "Prepare Lighthouse launch notes" in next_a.json()["response"]
    assert "task list is clear" in next_b.json()["response"]


@pytest.mark.asyncio
async def test_task_cannot_reference_another_users_project(client):
    owner = await client.post("/api/v1/auth/register", json={
        "email": "project-owner@example.com", "password": "Password123!", "full_name": "Owner",
    })
    outsider = await client.post("/api/v1/auth/register", json={
        "email": "project-outsider@example.com", "password": "Password123!", "full_name": "Outsider",
    })
    owner_headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}
    outsider_headers = {"Authorization": f"Bearer {outsider.json()['access_token']}"}
    project = await client.post("/api/v1/projects", headers=owner_headers, json={"name": "Private Project"})

    response = await client.post("/api/v1/tasks", headers=outsider_headers, json={
        "title": "Cross-tenant task", "project_id": project.json()["id"],
    })
    assert response.status_code == 404
