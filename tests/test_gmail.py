import base64

from services.gmail_service import decode_email_body, format_message, get_header


def test_get_header_is_case_insensitive():
    headers = [{"name": "From", "value": "alex@example.com"}]
    assert get_header(headers, "from") == "alex@example.com"
    assert get_header(headers, "subject") == ""


def test_decode_email_body_supports_plain_text_parts():
    encoded = base64.urlsafe_b64encode(b"Project update").decode()
    payload = {
        "parts": [
            {"mimeType": "text/html", "body": {}},
            {"mimeType": "text/plain", "body": {"data": encoded}},
        ]
    }
    assert decode_email_body(payload) == "Project update"


def test_format_message_returns_normalized_fields():
    encoded = base64.urlsafe_b64encode(b"Hello from the body").decode()
    message = {
        "id": "message-1",
        "threadId": "thread-1",
        "snippet": "Hello",
        "payload": {
            "headers": [
                {"name": "From", "value": "alex@example.com"},
                {"name": "Subject", "value": "Weekly update"},
                {"name": "Date", "value": "Fri, 28 Aug 2026 09:00:00 +0000"},
            ],
            "body": {"data": encoded},
        },
    }
    result = format_message(message)
    assert result["id"] == "message-1"
    assert result["thread_id"] == "thread-1"
    assert result["from"] == "alex@example.com"
    assert result["subject"] == "Weekly update"
    assert result["body"] == "Hello from the body"
