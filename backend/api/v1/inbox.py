import json
import logging
from typing import Annotated, Any, List
from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_active_user
from backend.db.session import get_db
from backend.models.integration import IntegrationAccount
from backend.models.user import User
from backend.services.crypto_service import crypto_service
from backend.integrations.gmail import GmailConnectionError, fetch_recent_emails
from agents.model_factory import get_model_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inbox", tags=["Smart Inbox"])

class EmailItemResponse(BaseModel):
    id: str
    sender: str
    subject: str
    snippet: str
    category: str  # "urgent", "action_needed", "fyi", "ignore"
    reason: str
    suggested_action: str | None = None
    date: str
    is_read: bool = False
    is_live_sync: bool = False


class InboxStatusResponse(BaseModel):
    is_connected: bool
    account_email: str | None = None
    connection_status: str = "disconnected"
    sync_error: str | None = None
    total_emails: int
    urgent_count: int
    action_needed_count: int
    fyi_count: int
    ignore_count: int
    emails: List[EmailItemResponse]


class DraftReplyRequest(BaseModel):
    email_id: str
    subject: str
    snippet: str
    instruction: str | None = None


class DraftReplyResponse(BaseModel):
    email_id: str
    draft_subject: str
    draft_body: str


def classify_email(subject: str, snippet: str, sender: str) -> tuple[str, str, str | None]:
    """Lightweight deterministic heuristic triage for instant categorization."""
    text = f"{subject} {snippet}".lower()

    # Urgent checks
    if any(w in text for w in ["urgent", "asap", "emergency", "immediately", "deadline today", "security alert", "critical", "outage"]):
        return (
            "urgent",
            "Contains time-sensitive language or critical notice",
            "Review immediately and take necessary action"
        )

    # Action needed
    if any(w in text for w in ["please review", "feedback", "proposal", "contract", "signature", "can you", "let me know", "quote"]):
        return (
            "action_needed",
            "Awaiting your feedback, approval, or response",
            "Review contents and reply"
        )

    # Ignore / Newsletter
    if any(w in text for w in ["unsubscribe", "newsletter", "promotions", "no-reply@marketing", "digest", "deal", "discount", "% off"]):
        return (
            "ignore",
            "Automated promotional or broadcast email",
            None
        )

    return (
        "fyi",
        "Informational update requiring no immediate response",
        None
    )


@router.get("", response_model=InboxStatusResponse)
async def get_inbox(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Returns the user's Smart Inbox.
    If Gmail is connected with live credentials, it retrieves and triages live messages.
    Otherwise, it returns an honest empty state with an invitation to connect.
    """
    # 1. Check if user has connected Gmail in DB
    result = await db.execute(
        select(IntegrationAccount).where(
            IntegrationAccount.user_id == current_user.id,
            IntegrationAccount.provider == "gmail",
        )
    )
    acc = result.scalar_one_or_none()

    # 2. If DB credentials exist, fetch using DB account
    if acc and acc.encrypted_access_token:
        try:
            raw_token = crypto_service.decrypt(acc.encrypted_access_token)
            token_dict = json.loads(raw_token) if raw_token.startswith("{") else {"access_token": raw_token}
            live_msgs = await fetch_recent_emails(token_dict, max_results=15)

            items = []
            for msg in live_msgs:
                category, reason, action = classify_email(msg.get("subject", ""), msg.get("snippet", ""), msg.get("from", ""))
                items.append(
                    EmailItemResponse(
                        id=msg.get("id", ""),
                        sender=msg.get("from", "Unknown"),
                        subject=msg.get("subject", "No subject"),
                        snippet=msg.get("snippet", ""),
                        category=category,
                        reason=reason,
                        suggested_action=action,
                        date=msg.get("date", "Recent")[:16],
                        is_read=False,
                        is_live_sync=True,
                    )
                )

            if acc.status != "connected" or acc.error_message:
                acc.status = "connected"
                acc.error_message = None
                await db.commit()
            return InboxStatusResponse(
                is_connected=True,
                account_email=acc.account_email_or_id,
                connection_status="connected",
                total_emails=len(items),
                urgent_count=sum(1 for i in items if i.category == "urgent"),
                action_needed_count=sum(1 for i in items if i.category == "action_needed"),
                fyi_count=sum(1 for i in items if i.category == "fyi"),
                ignore_count=sum(1 for i in items if i.category == "ignore"),
                emails=items,
            )
        except GmailConnectionError as exc:
            sync_error = str(exc)
            logger.warning("Gmail sync failed for user %s: %s", current_user.id, sync_error)
        except Exception as exc:
            sync_error = "The saved Gmail connection could not be read. Reconnect Gmail and try again."
            logger.warning("Error fetching live Gmail for user %s from DB: %s", current_user.id, exc)

        acc.status = "error"
        acc.error_message = sync_error
        await db.commit()
        return InboxStatusResponse(
            is_connected=True,
            account_email=acc.account_email_or_id,
            connection_status="error",
            sync_error=sync_error,
            total_emails=0,
            urgent_count=0,
            action_needed_count=0,
            fyi_count=0,
            ignore_count=0,
            emails=[],
        )

    if acc:
        acc.status = "error"
        acc.error_message = "The saved Gmail credential is missing. Reconnect Gmail to continue syncing."
        await db.commit()

    # Never fall back to a process-wide token file or fabricated messages in the
    # multi-user API. Either would misrepresent or expose another user's mailbox.
    return InboxStatusResponse(
        is_connected=acc is not None,
        account_email=acc.account_email_or_id if acc else None,
        connection_status="error" if acc else "disconnected",
        sync_error=acc.error_message if acc else None,
        total_emails=0,
        urgent_count=0,
        action_needed_count=0,
        fyi_count=0,
        ignore_count=0,
        emails=[],
    )


@router.post("/draft-reply", response_model=DraftReplyResponse)
async def draft_email_reply(
    data: DraftReplyRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generates a review-only reply draft, using the configured model when available."""
    prefix = "Re: " if not data.subject.lower().startswith("re:") else ""
    subject = f"{prefix}{data.subject}"
    body = ""
    try:
        model = await get_model_for_user(
            str(current_user.id), task_complexity="simple", temperature=0.2, db_session=db
        )
        instruction = data.instruction or "Acknowledge the message and give a clear, non-invented next step."
        reply = await model.ainvoke([
            SystemMessage(content="Write only the email body. Be concise and professional. Do not invent commitments, dates, or facts. This is a draft for human review."),
            HumanMessage(content=f"Sender message subject: {data.subject}\nSender excerpt: {data.snippet[:1200]}\nUser instruction: {instruction}\nSign as: {current_user.full_name or 'Regards'}"),
        ])
        body = reply.content if isinstance(reply.content, str) else str(reply.content)
    except Exception:
        body = (
            f"Hi,\n\nThank you for your message about \"{data.subject}\". "
            "I’ve reviewed the details and will follow up with the appropriate next step.\n\n"
            f"Best regards,\n{current_user.full_name or 'Regards'}"
        )

    return DraftReplyResponse(
        email_id=data.email_id,
        draft_subject=subject,
        draft_body=body,
    )
