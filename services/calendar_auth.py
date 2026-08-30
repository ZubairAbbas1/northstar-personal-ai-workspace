import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

CREDENTIALS_FILE = BASE_DIR / "secrets" / "gmail_credentials.json"
CALENDAR_TOKEN_FILE = BASE_DIR / "tokens" / "calendar_token.json"
GMAIL_TOKEN_FILE = BASE_DIR / "tokens" / "gmail_token.json"

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_calendar_credentials(interactive: bool = False) -> Credentials | None:
    """Acquires and refreshes Google OAuth credentials for Google Calendar."""
    creds = None

    # 1. Try calendar token file
    if CALENDAR_TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(CALENDAR_TOKEN_FILE),
                CALENDAR_SCOPES,
            )
        except Exception as e:
            logger.debug("Failed to load calendar token file: %s", e)

    # 2. Try gmail token file if calendar token missing
    if not creds and GMAIL_TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(GMAIL_TOKEN_FILE),
            )
        except Exception as e:
            logger.debug("Failed to load gmail token file for calendar: %s", e)

    # 3. Refresh if expired
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("Failed to refresh calendar token: %s", e)
                creds = None

    # 4. If still invalid and interactive mode requested, run browser login
    if not creds and interactive:
        if not CREDENTIALS_FILE.exists():
            logger.error("Credentials file not found at %s", CREDENTIALS_FILE)
            return None
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE),
                CALENDAR_SCOPES,
            )
            creds = flow.run_local_server(port=0)
            if creds and creds.valid:
                CALENDAR_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                CALENDAR_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to run interactive calendar OAuth flow: %s", e)
            return None

    return creds if creds and creds.valid else None


def get_calendar_access_token() -> str | None:
    """Returns a valid OAuth access token string for HTTP/MCP Authorization header."""
    creds = get_calendar_credentials(interactive=False)
    if creds and creds.valid:
        return creds.token
    return None


if __name__ == "__main__":
    print("Authorizing Google Calendar OAuth...")
    creds = get_calendar_credentials(interactive=True)
    if creds and creds.valid:
        print("Google Calendar OAuth authorized successfully!")
    else:
        print("Calendar OAuth authorization failed or skipped.")
