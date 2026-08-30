from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import base64
from email.utils import parsedate_to_datetime

BASE_DIR = Path(__file__).resolve().parent.parent

CREDENTIALS_FILE = (
    BASE_DIR
    / "secrets"
    / "gmail_credentials.json"
)

TOKEN_FILE = (
    BASE_DIR
    / "tokens"
    / "gmail_token.json"
)



SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

def get_gmail_service():

    creds = None


    if TOKEN_FILE.exists():

        creds = Credentials.from_authorized_user_file(
            str(TOKEN_FILE),
            SCOPES
        )


    # If credentials are missing or invalid,
    # authenticate again.
    if not creds or not creds.valid:

        # Token expired, but we can refresh it.
        if (
            creds
            and creds.expired
            and creds.refresh_token
        ):

            creds.refresh(
                Request()
            )

        else:

            # First login.
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE),
                SCOPES
            )

            creds = flow.run_local_server(
                port=0
            )


        # Save token so we don't log in
        # every single run.
        TOKEN_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        TOKEN_FILE.write_text(
            creds.to_json(),
            encoding="utf-8"
        )


    # Create Gmail API client.
    service = build(
        "gmail",
        "v1",
        credentials=creds
    )

    return service


def get_header(headers, name):

    for header in headers:

        if header["name"].lower() == name.lower():
            return header["value"]

    return ""

def decode_email_body(payload):

    body = payload.get("body", {})

    data = body.get("data")

    if data:

        decoded = base64.urlsafe_b64decode(
            data
        )

        return decoded.decode(
            "utf-8",
            errors="ignore"
        )


    # Multipart email
    for part in payload.get("parts", []):

        mime_type = part.get(
            "mimeType",
            ""
        )

        if mime_type == "text/plain":

            part_data = (
                part
                .get("body", {})
                .get("data")
            )

            if part_data:

                decoded = base64.urlsafe_b64decode(
                    part_data
                )

                return decoded.decode(
                    "utf-8",
                    errors="ignore"
                )


    return ""
def format_message(message):

    payload = message.get(
        "payload",
        {}
    )

    headers = payload.get(
        "headers",
        []
    )

    sender = get_header(
        headers,
        "From"
    )

    subject = get_header(
        headers,
        "Subject"
    )

    date = get_header(
        headers,
        "Date"
    )

    body = decode_email_body(
        payload
    )


    return {

        "id":
            message.get("id"),

        "thread_id":
            message.get("threadId"),

        "from":
            sender,

        "subject":
            subject,

        "date":
            date,

        "snippet":
            message.get(
                "snippet",
                ""
            ),

        "body":
            body[:5000]
    }
def get_recent_emails(
    max_results: int = 10
):

    service = get_gmail_service()


    result = (
        service
        .users()
        .messages()
        .list(
            userId="me",
            maxResults=max_results
        )
        .execute()
    )


    messages = result.get(
        "messages",
        []
    )


    emails = []


    for item in messages:

        message = (
            service
            .users()
            .messages()
            .get(
                userId="me",
                id=item["id"],
                format="full"
            )
            .execute()
        )

        emails.append(
            format_message(
                message
            )
        )
    return emails

def search_emails(
    query: str,
    max_results: int = 10
):

    service = get_gmail_service()


    result = (
        service
        .users()
        .messages()
        .list(
            userId="me",
            q=query,
            maxResults=max_results
        )
        .execute()
    )


    messages = result.get(
        "messages",
        []
    )


    emails = []


    for item in messages:

        message = (
            service
            .users()
            .messages()
            .get(
                userId="me",
                id=item["id"],
                format="full"
            )
            .execute()
        )

        emails.append(
            format_message(
                message
            )
        )
    return emails

def get_email(
    message_id: str
):

    service = get_gmail_service()


    message = (
        service
        .users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full"
        )
        .execute()
    )


    return format_message(
        message
    )