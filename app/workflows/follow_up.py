import asyncio
import json
import logging
import os
from typing import Any

from langchain_groq import ChatGroq

from app.mcp_client import get_gmail_tools
from app.models.follow_up import FollowUpReport
from app.state import AssistantState
from app.workflows.smart_inbox import parse_mcp_tool_result

logger = logging.getLogger(__name__)

FOLLOW_UP_SYSTEM_PROMPT = """You are an executive follow-up tracking specialist.

Analyze the provided email messages (both received inbox messages and sent messages) to detect pending follow-up communications.

You must categorize detected items into exactly two types:
1. needs_your_reply:
   An important contact/client/colleague sent an inquiry, question, or request, and there is no record of a subsequent reply.

2. waiting_on_them:
   The user sent an inquiry, question, or document requesting confirmation/action, and the recipient has not replied.

Rules:
- Be conservative. Do not flag automated newsletters, marketing receipts, or trivial messages.
- Extract the contact name/email, subject line, approximate timing, and clear 1-sentence reason.
- If no follow-ups are needed, return an empty items list.
"""


def format_follow_up_response(report: FollowUpReport) -> str:
    """Formats FollowUpReport into an executive summary."""
    needs_reply = [item for item in report.items if item.category == "needs_your_reply"]
    waiting_on = [item for item in report.items if item.category == "waiting_on_them"]

    lines: list[str] = ["FOLLOW-UP RADAR\n"]

    lines.append("NEEDS YOUR REPLY")
    if needs_reply:
        for item in needs_reply:
            lines.append(f"• **{item.contact}** ({item.date_str})")
            lines.append(f"  Subject: {item.subject}")
            lines.append(f"  Reason: {item.reason}\n")
    else:
        lines.append("• You are all caught up! No pending replies owed.\n")

    lines.append("WAITING ON THEM")
    if waiting_on:
        for item in waiting_on:
            lines.append(f"• **{item.contact}** ({item.date_str})")
            lines.append(f"  Subject: {item.subject}")
            lines.append(f"  Reason: {item.reason}\n")
    else:
        lines.append("• No pending responses you are actively waiting on.")

    return "\n".join(lines).strip()


async def follow_up(
    state: AssistantState,
    llm: ChatGroq | None = None,
) -> dict[str, Any]:
    """LangGraph node for follow-up detection."""
    try:
        gmail_tools = await get_gmail_tools()
        search_tool = next((t for t in gmail_tools if t.name == "gmail_search"), None)

        if not search_tool:
            return {
                "response": "Gmail tool is currently unavailable for follow-up detection.",
            }

        # 1. Fetch recent inbox and sent messages in parallel
        async def fetch_inbox():
            try:
                res = await search_tool.ainvoke({"query": "in:inbox newer_than:14d", "max_results": 15})
                return parse_mcp_tool_result(res)
            except Exception:
                return []

        async def fetch_sent():
            try:
                res = await search_tool.ainvoke({"query": "in:sent newer_than:14d", "max_results": 15})
                return parse_mcp_tool_result(res)
            except Exception:
                return []

        inbox_raw, sent_raw = await asyncio.gather(fetch_inbox(), fetch_sent())

        # 2. Prepare sanitized message metadata
        email_data = {
            "received_messages": [
                {
                    "from": e.get("from", ""),
                    "subject": e.get("subject", ""),
                    "date": e.get("date", ""),
                    "snippet": (e.get("snippet") or "")[:400],
                }
                for e in inbox_raw
            ],
            "sent_messages": [
                {
                    "to": e.get("to") or e.get("from", ""),
                    "subject": e.get("subject", ""),
                    "date": e.get("date", ""),
                    "snippet": (e.get("snippet") or "")[:400],
                }
                for e in sent_raw
            ],
        }

        # 3. LLM analysis with Groq
        if llm is None:
            model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            llm = ChatGroq(
                model=model_name,
                temperature=0,
                max_retries=2,
            )

        structured_llm = llm.with_structured_output(FollowUpReport)
        report: FollowUpReport = await structured_llm.ainvoke([
            ("system", FOLLOW_UP_SYSTEM_PROMPT),
            ("human", f"Analyze these messages for follow-ups:\n\n{json.dumps(email_data, ensure_ascii=False, indent=2)}"),
        ])

        formatted_response = format_follow_up_response(report)
        return {
            "response": formatted_response,
        }

    except Exception as error:
        logger.exception("Follow-up workflow error: %s", error)
        return {
            "error": str(error),
            "response": f"Unable to detect follow-ups: {error}",
        }
