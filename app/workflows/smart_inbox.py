import json
import logging
import os
from typing import Any

from langchain_groq import ChatGroq

from app.mcp_client import get_gmail_tools
from app.models.inbox import InboxAnalysis, InboxCategory, InboxItem
from app.state import AssistantState

logger = logging.getLogger(__name__)

SMART_INBOX_SYSTEM_PROMPT = """You are an executive Smart Inbox classifier for a personal AI productivity assistant.

Analyze each email based strictly on the metadata and snippet provided, then classify it into exactly one category:

1. urgent:
   Requires immediate same-day attention. Examples: imminent deadlines (within 24-48 hours), emergency alerts, meeting cancellations/changes today, critical project blockers, or security alerts.

2. action_needed:
   Direct request requiring the user's action, decision, review, or reply. Examples: client questions, pending invitations, documents waiting for feedback, assigned tasks.

3. fyi:
   Informative, relevant context that requires no immediate reply or action. Examples: project status updates, general announcements, useful reference materials.

4. ignore:
   Low-value automated noise, marketing, promotions, generic newsletters, social notifications, or spam.

Classification Guidelines:
- Be conservative: do NOT mark newsletters, promotional emails, or general notices as urgent or action_needed.
- Do not invent facts or extrapolate beyond the provided email snippets.
- Keep the 'reason' concise and professional (1 sentence).
- If action is needed or urgent, provide a concrete 'suggested_action'. If FYI or ignore, set suggested_action to null.
- Ensure the exact email_id matches each input email.
"""


def parse_mcp_tool_result(raw_result: Any) -> list[dict[str, Any]]:
    """Robustly parses MCP tool output across multiple adapter formats."""
    if isinstance(raw_result, str):
        try:
            return json.loads(raw_result)
        except json.JSONDecodeError:
            logger.warning("Failed to decode MCP string result as JSON: %s", raw_result[:200])
            return []
    if isinstance(raw_result, list):
        if not raw_result:
            return []
        if isinstance(raw_result[0], dict) and "text" in raw_result[0]:
            try:
                return json.loads(raw_result[0]["text"])
            except json.JSONDecodeError:
                logger.warning("Failed to decode text payload from MCP result: %s", raw_result[0]["text"][:200])
                return []
        return raw_result
    return []


def format_inbox_response(
    analysis: InboxAnalysis,
    emails_by_id: dict[str, dict[str, Any]],
) -> str:
    """Formats structured InboxAnalysis into a clean executive summary."""
    category_order: dict[InboxCategory, int] = {
        "urgent": 0,
        "action_needed": 1,
        "fyi": 2,
        "ignore": 3,
    }

    counts: dict[InboxCategory, int] = {
        "urgent": 0,
        "action_needed": 0,
        "fyi": 0,
        "ignore": 0,
    }

    for item in analysis.items:
        counts[item.category] = counts.get(item.category, 0) + 1

    sorted_items = sorted(
        analysis.items,
        key=lambda item: category_order.get(item.category, 99)
    )

    lines: list[str] = [
        "SMART INBOX",
        f"Urgent: {counts['urgent']} | Action needed: {counts['action_needed']} | FYI: {counts['fyi']} | Ignore: {counts['ignore']}\n"
    ]

    actionable_items = [item for item in sorted_items if item.category != "ignore"]

    if not actionable_items:
        lines.append("All recent messages are marketing or noise. No urgent action required.")
        return "\n".join(lines)

    for item in actionable_items:
        original = emails_by_id.get(item.email_id, {})
        sender = original.get("from", "Unknown sender")
        subject = original.get("subject", "(No subject)")

        label = {
            "urgent": "URGENT",
            "action_needed": "ACTION NEEDED",
            "fyi": "FYI",
        }.get(item.category, item.category.upper())

        lines.append(f"[{label}] {subject}")
        lines.append(f"From: {sender}")
        lines.append(f"Why: {item.reason}")
        if item.suggested_action:
            lines.append(f"Next: {item.suggested_action}")
        lines.append("")

    return "\n".join(lines).strip()


async def smart_inbox(
    state: AssistantState,
    llm: ChatGroq | None = None,
) -> dict[str, Any]:
    """LangGraph node for Smart Inbox email categorization and triage."""
    try:
        # 1. Fetch Gmail tools from MCP client
        tools = await get_gmail_tools()
        search_tool = next(
            (tool for tool in tools if tool.name in ("gmail_search", "gmail_recent_emails")),
            None,
        )

        if not search_tool:
            return {
                "error": "Gmail search tool is unavailable on MCP server.",
                "response": "Gmail search is currently unavailable. Please verify the Gmail MCP server.",
            }

        # 2. Query recent inbox messages (last 7 days, up to 15 emails)
        if search_tool.name == "gmail_search":
            raw_result = await search_tool.ainvoke({
                "query": "in:inbox newer_than:7d",
                "max_results": 15,
            })
        else:
            raw_result = await search_tool.ainvoke({
                "max_results": 15,
            })

        emails = parse_mcp_tool_result(raw_result)

        if not emails:
            return {
                "emails": [],
                "inbox_analysis": [],
                "response": "I couldn't find any recent emails in your inbox for the past 7 days.",
            }

        # 3. Privacy & token-safe preparation: metadata + short snippets only
        email_data = [
            {
                "email_id": email.get("id", ""),
                "from": email.get("from", ""),
                "subject": email.get("subject", ""),
                "date": email.get("date", ""),
                "snippet": (email.get("snippet") or "")[:500],
            }
            for email in emails
            if email.get("id")
        ]

        if not email_data:
            return {
                "emails": emails,
                "inbox_analysis": [],
                "response": "No readable messages found to analyze.",
            }

        # 4. LLM structured classification with Groq
        if llm is None:
            model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            llm = ChatGroq(
                model=model_name,
                temperature=0,
                max_retries=2,
            )

        structured_llm = llm.with_structured_output(InboxAnalysis)
        analysis: InboxAnalysis = await structured_llm.ainvoke([
            ("system", SMART_INBOX_SYSTEM_PROMPT),
            ("human", f"Please categorize these inbox emails:\n\n{json.dumps(email_data, ensure_ascii=False, indent=2)}"),
        ])

        # 5. Build lookup and formatted executive summary
        emails_by_id = {email["id"]: email for email in emails if "id" in email}
        analysis_items = [item.model_dump() for item in analysis.items]
        response_text = format_inbox_response(analysis, emails_by_id)

        return {
            "emails": emails,
            "inbox_analysis": analysis_items,
            "response": response_text,
        }

    except Exception as error:
        logger.exception("Error executing Smart Inbox workflow: %s", error)
        return {
            "error": str(error),
            "response": f"Smart Inbox was unable to complete: {error}",
        }
