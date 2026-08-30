import asyncio
import json
import logging
import os
from typing import Any

from langchain_groq import ChatGroq

from app.mcp_client import get_calendar_tools, get_gmail_tools, get_tasks_tools
from app.models.brief import MorningBriefData
from app.state import AssistantState
from app.workflows.smart_inbox import parse_mcp_tool_result

logger = logging.getLogger(__name__)

MORNING_BRIEF_SYSTEM_PROMPT = """You are an executive chief-of-staff AI assistant.

Your task is to synthesize the user's upcoming day by analyzing:
1. Today's Calendar Schedule
2. Urgent & Action-Needed Inbox Emails
3. Active & Overdue Tasks

Rules:
- Emphasize decisions, priorities, and action items over raw data dumping.
- Create a chronological schedule for today.
- Highlight the top 3-5 critical items needing attention across tasks, emails, and meetings.
- Propose a realistic focus timeline scheduling deep work in the free blocks between meetings.
- Be concise, professional, and crisp.
"""


def format_morning_brief(brief: MorningBriefData) -> str:
    """Formats MorningBriefData into a high-impact executive daily brief."""
    lines: list[str] = [
        f"MORNING BRIEF — {brief.date_header}\n",
        "TODAY'S SCHEDULE",
    ]

    if brief.today_schedule:
        for item in brief.today_schedule:
            detail_str = f" ({item.details})" if item.details else ""
            lines.append(f"• {item.time_str}: {item.title}{detail_str}")
    else:
        lines.append("• No scheduled meetings today. Full day available for deep work.")

    lines.append("\nNEEDS ATTENTION")
    if brief.needs_attention:
        for i, item in enumerate(brief.needs_attention, 1):
            lines.append(f"{i}. [{item.source_type.upper()}] {item.title}")
            lines.append(f"   Why: {item.reason}")
    else:
        lines.append("• No critical urgent items detected.")

    lines.append("\nSUGGESTED FOCUS TIMELINE")
    if brief.suggested_focus:
        for block in brief.suggested_focus:
            lines.append(f"• {block.time_slot}: {block.activity}")
    else:
        lines.append("• Focus on highest priority open tasks.")

    return "\n".join(lines).strip()


async def morning_brief(
    state: AssistantState,
    llm: ChatGroq | None = None,
) -> dict[str, Any]:
    """LangGraph node for Morning Brief workflow."""
    try:
        # 1. Parallel data retrieval across Calendar, Gmail, and Tasks
        calendar_events = []
        recent_emails = []
        active_tasks = []

        async def fetch_calendar():
            cal_tools = await get_calendar_tools()
            today_tool = next((t for t in cal_tools if t.name == "calendar_get_today_events"), None)
            if today_tool:
                try:
                    res = await today_tool.ainvoke({})
                    return parse_mcp_tool_result(res)
                except Exception as e:
                    logger.warning("Failed to fetch calendar events for brief: %s", e)
            return []

        async def fetch_emails():
            gmail_tools = await get_gmail_tools()
            search_tool = next((t for t in gmail_tools if t.name == "gmail_search"), None)
            if search_tool:
                try:
                    res = await search_tool.ainvoke({"query": "in:inbox newer_than:3d", "max_results": 10})
                    emails = parse_mcp_tool_result(res)
                    return [
                        {
                            "from": e.get("from", ""),
                            "subject": e.get("subject", ""),
                            "snippet": (e.get("snippet") or "")[:300],
                        }
                        for e in emails
                    ]
                except Exception as e:
                    logger.warning("Failed to fetch emails for brief: %s", e)
            return []

        async def fetch_tasks():
            task_tools = await get_tasks_tools()
            today_tasks_tool = next((t for t in task_tools if t.name == "tasks_get_today_tasks"), None)
            if today_tasks_tool:
                try:
                    res = await today_tasks_tool.ainvoke({})
                    return parse_mcp_tool_result(res)
                except Exception as e:
                    logger.warning("Failed to fetch tasks for brief: %s", e)
            return []

        cal_res, email_res, task_res = await asyncio.gather(
            fetch_calendar(),
            fetch_emails(),
            fetch_tasks(),
            return_exceptions=True,
        )

        calendar_events = cal_res if isinstance(cal_res, list) else []
        recent_emails = email_res if isinstance(email_res, list) else []
        active_tasks = task_res if isinstance(task_res, list) else []

        # 2. LLM Synthesis with Groq
        if llm is None:
            model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            llm = ChatGroq(
                model=model_name,
                temperature=0,
                max_retries=2,
            )

        structured_llm = llm.with_structured_output(MorningBriefData)
        input_payload = {
            "calendar_events": calendar_events,
            "recent_emails": recent_emails,
            "active_tasks": active_tasks,
        }

        brief_data: MorningBriefData = await structured_llm.ainvoke([
            ("system", MORNING_BRIEF_SYSTEM_PROMPT),
            ("human", f"Generate today's morning brief using this context:\n\n{json.dumps(input_payload, ensure_ascii=False, indent=2)}"),
        ])

        formatted_response = format_morning_brief(brief_data)
        return {
            "response": formatted_response,
        }

    except Exception as error:
        logger.exception("Morning brief workflow error: %s", error)
        return {
            "error": str(error),
            "response": f"Morning Brief was unable to complete: {error}",
        }
