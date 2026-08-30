import base64
import asyncio
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import imaplib
import json
import logging
from typing import Any, List
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailConnectionError(RuntimeError):
    """A safe, user-facing Gmail connection or synchronization error."""


def _friendly_imap_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "application-specific password required" in message:
        return "Google requires a 16-character App Password. Your normal Gmail password will not work."
    if "authenticationfailed" in message or "invalid credentials" in message or "login failed" in message:
        return "Gmail rejected the email address or App Password. Generate a new App Password and reconnect."
    if "10013" in message or "forbidden by its access permissions" in message:
        return "This computer blocked Gmail's secure IMAP connection on port 993. Allow outbound IMAP access and try again."
    if isinstance(exc, (TimeoutError, OSError)):
        return "Gmail could not be reached. Check the network connection and try again."
    return "Gmail could not verify this connection. Generate a new App Password and try again."


def _login_imap(email_address: str, app_password: str) -> imaplib.IMAP4_SSL:
    clean_password = "".join(app_password.split())
    if len(clean_password) != 16:
        raise GmailConnectionError("Enter the 16-character Google App Password, not your normal Gmail password.")
    mail: imaplib.IMAP4_SSL | None = None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", port=993, timeout=15)
        mail.login(email_address.strip(), clean_password)
        status, _ = mail.select("INBOX", readonly=True)
        if status != "OK":
            raise GmailConnectionError("Gmail connected, but the inbox could not be opened. Make sure IMAP access is allowed.")
        return mail
    except GmailConnectionError:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass
        raise
    except Exception as exc:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass
        raise GmailConnectionError(_friendly_imap_error(exc)) from exc


def validate_gmail_app_password_sync(email_address: str, app_password: str) -> None:
    """Verifies an App Password before it is encrypted and saved."""
    mail = _login_imap(email_address, app_password)
    try:
        mail.close()
    finally:
        mail.logout()


async def validate_gmail_app_password(email_address: str, app_password: str) -> None:
    await asyncio.to_thread(validate_gmail_app_password_sync, email_address, app_password)


def build_gmail_client_from_token(token_data: dict[str, Any]):
    """Builds a Google API client from a decrypted user token dictionary."""
    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes", SCOPES),
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_header(headers: list[dict[str, str]], name: str) -> str:
    """Helper to extract a specific header value by name."""
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def decode_imap_header(val: str) -> str:
    """Decodes MIME encoded header strings into plain text."""
    if not val:
        return ""
    try:
        decoded_list = decode_header(val)
        parts = []
        for text, encoding in decoded_list:
            if isinstance(text, bytes):
                parts.append(text.decode(encoding or "utf-8", errors="ignore"))
            else:
                parts.append(str(text))
        return "".join(parts)
    except Exception:
        return val


def fetch_emails_via_imap(email_address: str, app_password: str, max_results: int = 10) -> List[dict[str, Any]]:
    """Retrieves recent emails via Google App Password SSL IMAP."""
    mail: imaplib.IMAP4_SSL | None = None
    try:
        mail = _login_imap(email_address, app_password)

        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            return []

        mail_ids = messages[0].split()
        target_ids = mail_ids[-max_results:]

        results = []
        for m_id in reversed(target_ids):
            res, msg_data = mail.fetch(m_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = decode_imap_header(msg.get("Subject", "No Subject"))
                    sender = decode_imap_header(msg.get("From", "Unknown"))
                    to_addr = decode_imap_header(msg.get("To", ""))
                    date_hdr = msg.get("Date", "")

                    # Extract snippet from text body
                    snippet = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                try:
                                    snippet = part.get_payload(decode=True).decode("utf-8", errors="ignore")[:300]
                                    break
                                except Exception:
                                    pass
                    else:
                        try:
                            snippet = msg.get_payload(decode=True).decode("utf-8", errors="ignore")[:300]
                        except Exception:
                            pass

                    results.append({
                        "id": str(m_id.decode("utf-8")),
                        "thread_id": str(m_id.decode("utf-8")),
                        "from": sender,
                        "to": to_addr,
                        "subject": subject,
                        "date": date_hdr,
                        "snippet": " ".join(snippet.split()) if snippet else subject,
                    })

        return results
    except GmailConnectionError:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch emails via IMAP: %s", exc)
        raise GmailConnectionError(_friendly_imap_error(exc)) from exc
    finally:
        if mail:
            try:
                mail.close()
            except Exception:
                pass
            try:
                mail.logout()
            except Exception:
                pass


async def fetch_recent_emails(
    token_data: dict[str, Any] | None,
    max_results: int = 10,
) -> List[dict[str, Any]]:
    """Fetches recent inbox emails for a specific user via OAuth or App Password."""
    if not token_data:
        return []

    # 1. Check if App Password / IMAP connection
    if token_data.get("app_password") and token_data.get("email"):
        return await asyncio.to_thread(
            fetch_emails_via_imap,
            token_data["email"],
            token_data["app_password"],
            max_results,
        )

    # 2. Check if OAuth token
    if not token_data.get("access_token"):
        return []

    try:
        service = build_gmail_client_from_token(token_data)
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                maxResults=max(1, min(max_results, 25)),
                q="in:inbox",
            )
            .execute()
        )

        messages = response.get("messages", [])
        emails = []

        for msg_meta in messages:
            msg = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_meta["id"],
                    format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"],
                )
                .execute()
            )

            headers = msg.get("payload", {}).get("headers", [])
            date_str = get_header(headers, "Date")
            try:
                date_iso = parsedate_to_datetime(date_str).isoformat() if date_str else ""
            except Exception:
                date_iso = date_str

            emails.append({
                "id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "from": get_header(headers, "From"),
                "to": get_header(headers, "To"),
                "subject": get_header(headers, "Subject"),
                "date": date_iso,
                "snippet": msg.get("snippet", ""),
            })

        return emails
    except Exception as exc:
        logger.warning("Failed to fetch Gmail messages: %s", exc)
        message = str(exc).lower()
        if "invalid_grant" in message or "unauthorized" in message or "401" in message:
            raise GmailConnectionError("Google authorization expired. Reconnect Gmail to continue syncing.") from exc
        raise GmailConnectionError("Gmail could not be synchronized. Reconnect the account and try again.") from exc


async def search_user_emails(
    token_data: dict[str, Any] | None,
    query: str,
    max_results: int = 10,
) -> List[dict[str, Any]]:
    """Searches user emails matching a query."""
    if not token_data or not query.strip():
        return []

    # If App Password, fallback to fetching recent
    if token_data.get("app_password"):
        recent = await fetch_recent_emails(token_data, max_results=max_results)
        q_lower = query.lower()
        return [
            e for e in recent
            if q_lower in e.get("subject", "").lower() or q_lower in e.get("from", "").lower() or q_lower in e.get("snippet", "").lower()
        ]

    try:
        service = build_gmail_client_from_token(token_data)
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                maxResults=max(1, min(max_results, 25)),
                q=query,
            )
            .execute()
        )

        messages = response.get("messages", [])
        emails = []

        for msg_meta in messages:
            msg = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_meta["id"],
                    format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"],
                )
                .execute()
            )
            headers = msg.get("payload", {}).get("headers", [])
            emails.append({
                "id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "from": get_header(headers, "From"),
                "to": get_header(headers, "To"),
                "subject": get_header(headers, "Subject"),
                "snippet": msg.get("snippet", ""),
            })

        return emails
    except Exception as e:
        logger.warning("Failed to search Gmail: %s", e)
        return []
