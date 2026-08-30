import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.model_factory import get_model_for_user
from backend.api.v1.calendar import get_calendar_for_date, get_today_calendar
from backend.api.v1.inbox import get_inbox
from backend.auth.dependencies import get_current_active_user
from backend.db.session import get_db
from backend.integrations.github import (
    GitHubConnectionError,
    fetch_github_issues,
    fetch_github_prs,
    fetch_github_repositories,
)
from backend.integrations.discord import DiscordConnectionError, fetch_discord_messages
from backend.models.integration import IntegrationAccount
from backend.models.memory import Memory
from backend.models.project import Project
from backend.models.task import Task
from backend.models.user import User
from backend.services.crypto_service import crypto_service
from services.priority_scoring import score_tasks

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])
logger = logging.getLogger(__name__)
Intent = Literal["what_next", "morning_brief", "smart_inbox", "meeting_prep", "calendar_query", "github", "discord", "universal_search", "memory", "general"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None
    model_mode: Literal["fast", "balanced", "quality"] = "balanced"
    timezone_offset_minutes: int = Field(default=0, ge=-840, le=840)


class ChatResponse(BaseModel):
    thread_id: str
    intent: str
    response: str
    sources_used: list[str] = []
    action_proposal: dict[str, Any] | None = None
    error: str | None = None


def detect_intent(message: str) -> Intent:
    text = message.lower()
    if any(phrase in text for phrase in ("what should i do", "what do i do", "do next", "highest priority", "focus on")):
        return "what_next"
    if any(phrase in text for phrase in ("morning brief", "brief my day", "today overview", "plan my day")):
        return "morning_brief"
    if any(word in text for word in ("inbox", "email", "emails")):
        return "smart_inbox"
    if any(phrase in text for phrase in ("meeting prep", "prepare for", "next meeting")):
        return "meeting_prep"
    if any(word in text for word in ("calendar", "schedule", "appointments", "events", "meetings")):
        return "calendar_query"
    if any(word in text for word in ("github", "repo", "repository", "repositories", "pull request")):
        return "github"
    if "discord" in text:
        return "discord"
    if any(word in text for word in ("search", "find", "where did")):
        return "universal_search"
    if any(phrase in text for phrase in ("remember that", "remember:", "what do you remember", "memory")):
        return "memory"
    return "general"


def smart_inbox_response(message: str, inbox: Any) -> str:
    """Answer the mailbox question instead of returning the same count for every email intent."""
    text = message.lower().strip()

    if not inbox.is_connected:
        return "Gmail is not connected yet, so I cannot read your mailbox. Connect Gmail from Integrations first."
    if inbox.sync_error:
        return f"Gmail is connected, but I cannot read it right now: {inbox.sync_error}"
    if not inbox.emails:
        return "Gmail is connected, but there are no inbox messages available to show."

    if any(phrase in text for phrase in ("latest", "newest", "most recent", "last email", "recent email")):
        email = inbox.emails[0]
        snippet = email.snippet.strip() or "No preview is available."
        return (
            f"Your latest email is **{email.subject or 'No subject'}**\n\n"
            f"**From:** {email.sender or 'Unknown sender'}\n"
            f"**Received:** {email.date or 'Date unavailable'}\n\n"
            f"{snippet}"
        )

    if "urgent" in text:
        matches = [email for email in inbox.emails if email.category == "urgent"]
        if not matches:
            return f"I can see {inbox.total_emails} recent inbox messages, and none are classified as urgent."
        lines = "\n".join(f"• **{email.subject or 'No subject'}** — {email.sender or 'Unknown sender'}" for email in matches[:5])
        return f"You have {len(matches)} urgent message{'s' if len(matches) != 1 else ''}:\n\n{lines}"

    if "action" in text or "reply" in text or "respond" in text:
        matches = [email for email in inbox.emails if email.category == "action_needed"]
        if not matches:
            return f"I can see {inbox.total_emails} recent inbox messages, and none are currently classified as needing action."
        lines = "\n".join(f"• **{email.subject or 'No subject'}** — {email.sender or 'Unknown sender'}" for email in matches[:5])
        return f"These messages may need action:\n\n{lines}"

    recent = "\n".join(
        f"• **{email.subject or 'No subject'}** — {email.sender or 'Unknown sender'}"
        for email in inbox.emails[:3]
    )
    return (
        f"Yes — Gmail is connected and I can see {inbox.total_emails} recent inbox messages. "
        f"There are **{inbox.urgent_count} urgent** and **{inbox.action_needed_count} action-needed** messages.\n\n"
        f"Most recent:\n{recent}"
    )


def calendar_target_date(message: str, timezone_offset_minutes: int) -> tuple[date, str]:
    local_zone = timezone(timedelta(minutes=-timezone_offset_minutes))
    today = datetime.now(local_zone).date()
    text = message.lower()
    if "tomorrow" in text:
        return today + timedelta(days=1), "tomorrow"
    return today, "today"


def format_calendar_time(value: str, timezone_offset_minutes: int) -> str:
    if not value:
        return "Time unavailable"
    if len(value) == 10:
        return "All day"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        local_zone = timezone(timedelta(minutes=-timezone_offset_minutes))
        return parsed.astimezone(local_zone).strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return value


def task_dict(task: Task, project_name: str | None = None) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "project": project_name,
        "priority": task.priority,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "estimated_minutes": task.estimated_minutes,
    }


async def what_next_response(user: User, db: AsyncSession) -> tuple[str, list[str]] | None:
    rows = await db.execute(
        select(Task, Project.name)
        .outerjoin(Project, Task.project_id == Project.id)
        .where(Task.user_id == user.id, Task.status.in_(["todo", "in_progress"]))
    )
    tasks = [task_dict(task, project_name) for task, project_name in rows.all()]
    if not tasks:
        return None
    ranked = score_tasks(tasks)
    top = ranked[0]
    task = top["task"]
    reasons = "\n".join(f"• {reason.rsplit(' (+', 1)[0]}" for reason in top["reasons"])
    alternatives = ", ".join(item["task"]["title"] for item in ranked[1:3])
    response = (
        f"Focus on **{task['title']}** next.\n\n"
        f"**Priority score:** {top['score']}/100\n{reasons}\n\n"
        f"Set aside about {task['estimated_minutes']} minutes and start with the smallest concrete next step."
    )
    if alternatives:
        response += f"\n\nIf blocked, move to: {alternatives}."
    return response, ["tasks"]


async def search_response(message: str, user: User, db: AsyncSession) -> tuple[str, list[str]]:
    cleaned = message.strip().strip('"')
    for prefix in ("search across all my connected accounts for:", "search for", "find"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip().strip('"')
            break
    pattern = f"%{cleaned}%"
    task_rows = await db.execute(select(Task).where(Task.user_id == user.id, or_(Task.title.ilike(pattern), Task.description.ilike(pattern))).limit(5))
    project_rows = await db.execute(select(Project).where(Project.user_id == user.id, or_(Project.name.ilike(pattern), Project.description.ilike(pattern))).limit(5))
    memory_rows = await db.execute(select(Memory).where(Memory.user_id == user.id, Memory.is_active.is_(True), Memory.fact.ilike(pattern)).limit(5))
    lines: list[str] = []
    sources: list[str] = []
    for task in task_rows.scalars():
        lines.append(f"• **Task:** {task.title} — {task.priority} priority, {task.status.replace('_', ' ')}")
        sources.append("tasks")
    for project in project_rows.scalars():
        lines.append(f"• **Project:** {project.name} — {project.description or 'No description'}")
        sources.append("projects")
    for memory in memory_rows.scalars():
        lines.append(f"• **Memory:** {memory.fact}")
        sources.append("memories")
    if not lines:
        return f"I couldn't find “{cleaned}” in your tasks, projects, or saved memories.", []
    return f"I found {len(lines)} matching item{'s' if len(lines) != 1 else ''}:\n\n" + "\n".join(lines), sorted(set(sources))


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    data: ChatRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    thread_id = data.thread_id or str(uuid.uuid4())
    intent = detect_intent(data.message)

    if intent == "what_next":
        result = await what_next_response(current_user, db)
        if result:
            return ChatResponse(thread_id=thread_id, intent=intent, response=result[0], sources_used=result[1])
        return ChatResponse(thread_id=thread_id, intent=intent, response="Your task list is clear. Add a task or check the Smart Inbox for a new action item.", sources_used=["tasks"])

    if intent == "universal_search":
        response, sources = await search_response(data.message, current_user, db)
        return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=sources)

    if intent == "memory":
        lower = data.message.lower().strip()
        if lower.startswith(("remember that ", "remember: ")):
            fact = data.message.split("that", 1)[-1] if "that" in lower else data.message.split(":", 1)[-1]
            memory = Memory(user_id=current_user.id, category="preference", fact=fact.strip(), source="assistant")
            db.add(memory)
            await db.commit()
            return ChatResponse(thread_id=thread_id, intent=intent, response=f"Saved to your private memory: “{fact.strip()}”.", sources_used=["memories"])
        rows = await db.execute(select(Memory).where(Memory.user_id == current_user.id, Memory.is_active.is_(True)).order_by(Memory.updated_at.desc()).limit(10))
        memories = rows.scalars().all()
        response = "I don't have any saved memories yet." if not memories else "Here’s what I remember:\n\n" + "\n".join(f"• {item.fact}" for item in memories)
        return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["memories"])

    if intent == "smart_inbox":
        inbox = await get_inbox(current_user, db)
        response = smart_inbox_response(data.message, inbox)
        return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["gmail"] if inbox.is_connected else [])

    if intent == "calendar_query":
        target_date, label = calendar_target_date(data.message, data.timezone_offset_minutes)
        calendar = await get_calendar_for_date(
            current_user,
            db,
            target_date,
            data.timezone_offset_minutes,
        )
        if not calendar.is_connected:
            response = "Google Calendar is not connected. Connect it from Integrations first."
            return ChatResponse(thread_id=thread_id, intent=intent, response=response)
        if calendar.sync_error:
            response = f"Google Calendar is connected, but I could not read it: {calendar.sync_error}"
            return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["calendar"])
        if not calendar.events:
            response = f"Your calendar is connected, and you have no events scheduled for {label}."
            return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["calendar"])
        lines = []
        for event in calendar.events:
            event_time = format_calendar_time(event.start, data.timezone_offset_minutes)
            detail = f" — {event.location}" if event.location else ""
            lines.append(f"• **{event_time}** — {event.summary}{detail}")
        response = f"You have {len(calendar.events)} event{'s' if len(calendar.events) != 1 else ''} {label}:\n\n" + "\n".join(lines)
        return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["calendar"])

    if intent == "github":
        result = await db.execute(
            select(IntegrationAccount).where(
                IntegrationAccount.user_id == current_user.id,
                IntegrationAccount.provider == "github",
            )
        )
        account = result.scalar_one_or_none()
        if not account or not account.encrypted_access_token:
            return ChatResponse(
                thread_id=thread_id,
                intent=intent,
                response="GitHub is not connected. Connect it from Integrations first.",
            )

        decrypted = crypto_service.decrypt(account.encrypted_access_token)
        token_data = json.loads(decrypted) if decrypted.startswith("{") else {"access_token": decrypted}
        query = data.message.lower()
        try:
            if "pull request" in query or re.search(r"\bprs?\b", query):
                items = await fetch_github_prs(token_data)
                if not items:
                    response = "GitHub is connected, and I found no open pull requests involving you."
                else:
                    lines = "\n".join(
                        f"• **{item.get('repository') or 'Repository'} #{item.get('number')}** — {item.get('title') or 'Untitled pull request'}"
                        for item in items[:10]
                    )
                    response = f"I found {len(items)} open pull request{'s' if len(items) != 1 else ''}:\n\n{lines}"
            elif "issue" in query:
                items = await fetch_github_issues(token_data)
                if not items:
                    response = "GitHub is connected, and I found no open issues assigned to you."
                else:
                    lines = "\n".join(
                        f"• **{item.get('repository') or 'Repository'} #{item.get('number')}** — {item.get('title') or 'Untitled issue'}"
                        for item in items[:10]
                    )
                    response = f"I found {len(items)} assigned issue{'s' if len(items) != 1 else ''}:\n\n{lines}"
            else:
                repositories = await fetch_github_repositories(token_data, max_results=10)
                if not repositories:
                    response = f"GitHub is connected as **{account.account_email_or_id or 'your account'}**, but no repositories are visible to this connection."
                else:
                    lines = []
                    for repository in repositories:
                        visibility = "private" if repository["private"] else "public"
                        language = f", {repository['language']}" if repository.get("language") else ""
                        description = f" — {repository['description']}" if repository.get("description") else ""
                        lines.append(f"• **{repository['full_name']}** ({visibility}{language}){description}")
                    response = (
                        f"Yes — GitHub is connected as **{account.account_email_or_id or 'your account'}**. "
                        f"Here are your {len(repositories)} most recently updated visible repositories:\n\n"
                        + "\n".join(lines)
                    )
            if account.status != "connected" or account.error_message:
                account.status = "connected"
                account.error_message = None
                await db.commit()
            return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["github"])
        except GitHubConnectionError as exc:
            account.status = "needs_reauth"
            account.error_message = str(exc)
            await db.commit()
            return ChatResponse(
                thread_id=thread_id,
                intent=intent,
                response=str(exc),
                sources_used=["github"],
            )

    if intent == "discord":
        result = await db.execute(
            select(IntegrationAccount).where(
                IntegrationAccount.user_id == current_user.id,
                IntegrationAccount.provider == "discord",
            )
        )
        account = result.scalar_one_or_none()
        if not account or not account.encrypted_access_token:
            return ChatResponse(
                thread_id=thread_id,
                intent=intent,
                response="Discord is not connected. Connect a Discord bot from Integrations first.",
            )

        try:
            metadata = json.loads(account.metadata_json or "{}")
        except json.JSONDecodeError:
            metadata = {}
        selected_channels = metadata.get("selected_channels", []) if isinstance(metadata, dict) else []
        if not selected_channels:
            return ChatResponse(
                thread_id=thread_id,
                intent=intent,
                response="Discord is connected, but no channels are selected. Open Integrations, choose Configure on Discord, and select up to 10 channels.",
                sources_used=["discord"],
            )

        query = data.message.lower()
        named_channels = [channel for channel in selected_channels if str(channel.get("name", "")).lower() in query]
        channels_to_read = named_channels or selected_channels
        token = crypto_service.decrypt(account.encrypted_access_token) or ""
        try:
            messages = await fetch_discord_messages(token, channels_to_read, limit_per_channel=10)
            if not messages:
                response = "Discord is connected, but the selected channels returned no recent messages. Check Read Message History and Message Content permissions for the bot."
            elif any(phrase in query for phrase in ("latest", "newest", "most recent", "last message")):
                message = messages[0]
                content = message["content"] or (
                    f"Shared {message['attachment_count']} attachment(s)."
                    if message["attachment_count"] else "Message content is unavailable to the bot."
                )
                response = (
                    f"The latest Discord message I can read is in **{message['guild_name']} / #{message['channel_name']}**.\n\n"
                    f"**{message['author']}:** {content}"
                )
            else:
                lines = []
                for message in messages[:10]:
                    content = message["content"] or (
                        f"Shared {message['attachment_count']} attachment(s)."
                        if message["attachment_count"] else "Message content unavailable."
                    )
                    if len(content) > 240:
                        content = content[:237].rstrip() + "..."
                    lines.append(
                        f"• **{message['guild_name']} / #{message['channel_name']} — {message['author']}:** {content}"
                    )
                response = f"Here are the {len(lines)} most recent Discord messages from your selected channels:\n\n" + "\n".join(lines)
            if account.status != "connected" or account.error_message:
                account.status = "connected"
                account.error_message = None
                await db.commit()
            return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["discord"])
        except DiscordConnectionError as exc:
            account.status = "needs_reauth" if exc.requires_reauth else "connected"
            account.error_message = str(exc)
            await db.commit()
            return ChatResponse(
                thread_id=thread_id,
                intent=intent,
                response=str(exc),
                sources_used=["discord"],
            )

    if intent in ("meeting_prep", "morning_brief"):
        calendar = await get_today_calendar(current_user, db, data.timezone_offset_minutes)
        task_rows = await db.execute(select(Task).where(Task.user_id == current_user.id, Task.status.in_(["todo", "in_progress"])).order_by(Task.due_date.asc().nulls_last()).limit(5))
        tasks = task_rows.scalars().all()
        if intent == "meeting_prep":
            if not calendar.events:
                response = "There are no meetings available today. Connect Google Calendar to generate live meeting briefs."
            else:
                event = calendar.events[0]
                response = f"Your next meeting is **{event.summary}** at {event.start}.\n\nPurpose: {event.description or 'No agenda provided.'}\nAttendees: {', '.join(event.attendees) or 'No attendees listed.'}"
            return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["calendar"])
        due = "\n".join(f"• {task.title} ({task.priority})" for task in tasks) or "• No open tasks"
        response = f"**Today at a glance**\n\nOpen priorities:\n{due}\n\nMeetings today: {len(calendar.events)}."
        return ChatResponse(thread_id=thread_id, intent=intent, response=response, sources_used=["tasks", "calendar"])

    memory_rows = await db.execute(select(Memory).where(Memory.user_id == current_user.id, Memory.is_active.is_(True)).order_by(Memory.updated_at.desc()).limit(8))
    memories = list(memory_rows.scalars())
    context = "\n".join(f"- {item.fact}" for item in memories) or "No saved memories."
    try:
        model = await get_model_for_user(str(current_user.id), task_complexity="simple", temperature=0.2, db_session=db)
        reply = await model.ainvoke([
            SystemMessage(content=f"You are a concise personal productivity assistant. Only use the authenticated user's context below.\n{context}"),
            HumanMessage(content=data.message),
        ])
        content = reply.content if isinstance(reply.content, str) else str(reply.content)
        return ChatResponse(thread_id=thread_id, intent=intent, response=content, sources_used=["memories"] if memories else [])
    except Exception as exc:
        logger.warning("Assistant model request failed for user %s: %s", current_user.id, exc)
        return ChatResponse(thread_id=thread_id, intent=intent, response="I can still help with tasks, priorities, search, inbox, meetings, and memory. Configure an AI provider in Settings for open-ended conversation.")
