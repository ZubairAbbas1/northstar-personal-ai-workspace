import json
import logging
import os
from typing import Any

from langchain_groq import ChatGroq

from app.mcp_client import get_calendar_tools, get_gmail_tools
from app.models.meeting import MeetingPrepBrief
from app.state import AssistantState
from app.workflows.smart_inbox import parse_mcp_tool_result

logger = logging.getLogger(__name__)

MEETING_PREP_SYSTEM_PROMPT = """You are an executive meeting preparation assistant.

Given meeting details (title, time, attendees, description) and related email communications, generate a concise, strategic executive brief.

Guidelines:
1. Extract the primary purpose of the meeting.
2. Highlight recent context and past communications with attendees.
3. List concrete outstanding items / unconfirmed decisions.
4. Suggest 2-4 preparation steps.
5. Suggest 2-3 strategic, insightful questions to ask.
6. Do not fabricate facts. If no emails exist, base preparation on the meeting description and attendees.
"""


def format_meeting_brief(brief: MeetingPrepBrief) -> str:
    """Formats MeetingPrepBrief into an executive-level summary."""
    lines: list[str] = [
        "NEXT MEETING\n",
        f"**{brief.meeting_title}**",
        f"Time: {brief.time_range}\n",
    ]

    if brief.attendees:
        lines.append(f"Attendees:\n• " + "\n• ".join(brief.attendees) + "\n")

    lines.append(f"Purpose:\n{brief.purpose}\n")

    if brief.recent_context:
        lines.append("Recent Context:")
        for item in brief.recent_context:
            lines.append(f"• {item}")
        lines.append("")

    if brief.outstanding_items:
        lines.append("Outstanding Items:")
        for item in brief.outstanding_items:
            lines.append(f"• {item}")
        lines.append("")

    if brief.suggested_preparation:
        lines.append("Suggested Preparation:")
        for i, item in enumerate(brief.suggested_preparation, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    if brief.questions_worth_asking:
        lines.append("Questions Worth Asking:")
        for item in brief.questions_worth_asking:
            lines.append(f"• {item}")

    return "\n".join(lines).strip()


async def meeting_prep(
    state: AssistantState,
    llm: ChatGroq | None = None,
) -> dict[str, Any]:
    """LangGraph node for meeting preparation workflow."""
    try:
        # 1. Fetch next meeting from Calendar MCP
        calendar_tools = await get_calendar_tools()
        next_meeting_tool = next(
            (t for t in calendar_tools if t.name == "calendar_get_next_meeting"),
            None,
        )

        meeting_data = None
        if next_meeting_tool:
            raw_meeting = await next_meeting_tool.ainvoke({})
            parsed = parse_mcp_tool_result(raw_meeting)
            if isinstance(parsed, dict) and parsed:
                meeting_data = parsed
            elif isinstance(parsed, list) and parsed:
                meeting_data = parsed[0]

        if not meeting_data:
            return {
                "response": "No upcoming meetings found on your calendar. Enjoy your free time!",
            }

        # 2. Extract keywords and attendees for related email search
        meeting_title = meeting_data.get("summary", "Upcoming Meeting")
        attendees = meeting_data.get("attendees", [])
        organizer = meeting_data.get("organizer", "")

        search_query_terms = [meeting_title]
        if organizer:
            search_query_terms.append(organizer)
        for att in attendees[:3]:
            search_query_terms.append(att)

        combined_query = " OR ".join(f'"{term}"' for term in search_query_terms if term)

        # 3. Fetch related emails via Gmail MCP
        related_emails = []
        gmail_tools = await get_gmail_tools()
        gmail_search = next(
            (t for t in gmail_tools if t.name == "gmail_search"),
            None,
        )

        if gmail_search and combined_query:
            try:
                raw_emails = await gmail_search.ainvoke({
                    "query": combined_query,
                    "max_results": 5,
                })
                emails_list = parse_mcp_tool_result(raw_emails)
                related_emails = [
                    {
                        "from": e.get("from", ""),
                        "subject": e.get("subject", ""),
                        "date": e.get("date", ""),
                        "snippet": (e.get("snippet") or "")[:400],
                    }
                    for e in emails_list
                ]
            except Exception as err:
                logger.warning("Error searching related emails for meeting prep: %s", err)

        # 4. LLM Synthesis with Groq
        if llm is None:
            model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            llm = ChatGroq(
                model=model_name,
                temperature=0,
                max_retries=2,
            )

        structured_llm = llm.with_structured_output(MeetingPrepBrief)
        prompt_content = {
            "meeting": meeting_data,
            "related_emails": related_emails,
        }

        brief: MeetingPrepBrief = await structured_llm.ainvoke([
            ("system", MEETING_PREP_SYSTEM_PROMPT),
            ("human", f"Prepare briefing for this meeting:\n\n{json.dumps(prompt_content, ensure_ascii=False, indent=2)}"),
        ])

        formatted_response = format_meeting_brief(brief)
        return {
            "response": formatted_response,
        }

    except Exception as error:
        logger.exception("Meeting prep workflow error: %s", error)
        return {
            "error": str(error),
            "response": f"Meeting preparation was unable to complete: {error}",
        }
