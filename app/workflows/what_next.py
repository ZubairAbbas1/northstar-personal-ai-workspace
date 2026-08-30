import asyncio
import json
import logging
import os
from typing import Any

from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.mcp_client import get_calendar_tools, get_gmail_tools, get_tasks_tools
from app.state import AssistantState
from app.workflows.smart_inbox import parse_mcp_tool_result
from services.priority_scoring import score_tasks

logger = logging.getLogger(__name__)


class WhatNextExplanation(BaseModel):
    recommended_action: str = Field(description="The primary recommended action/task to work on.")
    project: str | None = Field(default=None, description="Associated project.")
    why_points: list[str] = Field(description="3-4 bullet points explaining why this is the highest priority.")
    time_guidance: str = Field(description="Guidance on estimated duration and available calendar slot.")
    alternatives: list[str] = Field(default_factory=list, description="1-2 alternative tasks if the user is blocked.")


WHAT_NEXT_SYSTEM_PROMPT = """You are an executive priority coach for a personal AI productivity assistant.

A deterministic scoring engine has evaluated the user's tasks, calendar gaps, and urgent communications, and ranked them.
Your job is to explain the top recommendation clearly and compellingly.

Guidelines:
1. State the recommended action directly.
2. Provide crisp, factual bullet points explaining why it is ranked #1 (due dates, urgency, client requests, free time fit).
3. Provide practical time guidance (e.g. "Estimated 60 min, you have 90 min before your next meeting").
4. List 1-2 secondary alternative actions.
5. Do not invent tasks not present in the input.
"""


def format_what_next_response(
    explanation: WhatNextExplanation,
    top_score: int,
) -> str:
    """Formats the recommendation and score into clean executive output."""
    lines: list[str] = [
        "RECOMMENDED FOCUS RIGHT NOW\n",
        f"**Action:** {explanation.recommended_action}",
    ]

    if explanation.project:
        lines.append(f"**Project:** {explanation.project}")

    lines.append(f"**Priority Score:** {top_score} / 100\n")

    lines.append("Why:")
    for pt in explanation.why_points:
        lines.append(f"• {pt}")
    lines.append("")

    lines.append(f"Time Guidance:\n• {explanation.time_guidance}\n")

    if explanation.alternatives:
        lines.append("Alternative Next Actions:")
        for alt in explanation.alternatives:
            lines.append(f"• {alt}")

    return "\n".join(lines).strip()


async def what_next(
    state: AssistantState,
    llm: ChatGroq | None = None,
) -> dict[str, Any]:
    """LangGraph node determining the highest priority next action."""
    try:
        # 1. Fetch tasks, calendar, and urgent emails in parallel
        async def fetch_tasks():
            t_tools = await get_tasks_tools()
            get_t_tool = next((t for t in t_tools if t.name == "tasks_get_tasks"), None)
            if get_t_tool:
                try:
                    res = await get_t_tool.ainvoke({"status": "todo"})
                    return parse_mcp_tool_result(res)
                except Exception as e:
                    logger.warning("Tasks fetch error: %s", e)
            return []

        async def fetch_cal():
            c_tools = await get_calendar_tools()
            today_tool = next((t for t in c_tools if t.name == "calendar_get_today_events"), None)
            if today_tool:
                try:
                    res = await today_tool.ainvoke({})
                    return parse_mcp_tool_result(res)
                except Exception as e:
                    logger.warning("Cal fetch error: %s", e)
            return []

        async def fetch_emails():
            g_tools = await get_gmail_tools()
            search_tool = next((t for t in g_tools if t.name == "gmail_search"), None)
            if search_tool:
                try:
                    res = await search_tool.ainvoke({"query": "in:inbox newer_than:3d", "max_results": 10})
                    return parse_mcp_tool_result(res)
                except Exception as e:
                    logger.warning("Gmail fetch error: %s", e)
            return []

        tasks_res, cal_res, emails_res = await asyncio.gather(
            fetch_tasks(),
            fetch_cal(),
            fetch_emails(),
            return_exceptions=True,
        )

        all_tasks = tasks_res if isinstance(tasks_res, list) else []
        cal_events = cal_res if isinstance(cal_res, list) else []
        recent_emails = emails_res if isinstance(emails_res, list) else []

        # 2. Score tasks deterministically
        if not all_tasks:
            # If no tasks in DB, provide helpful guidance based on inbox/calendar
            return {
                "response": "You currently have no pending tasks in your task list. Check your inbox or calendar to create new action items!"
            }

        scored = score_tasks(all_tasks, calendar_events=cal_events, urgent_emails=recent_emails)
        if not scored:
            return {
                "response": "All existing tasks are completed. You are all caught up!"
            }

        top_item = scored[0]
        top_task = top_item["task"]
        top_score = top_item["score"]
        alternatives = [s["task"]["title"] for s in scored[1:3]]

        # 3. LLM synthesis explaining the scored recommendation
        if llm is None:
            model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            llm = ChatGroq(
                model=model_name,
                temperature=0,
                max_retries=2,
            )

        structured_llm = llm.with_structured_output(WhatNextExplanation)
        payload = {
            "top_task": top_task,
            "score": top_score,
            "reasons": top_item["reasons"],
            "free_minutes_available": top_item["free_minutes_available"],
            "alternatives": alternatives,
        }

        explanation: WhatNextExplanation = await structured_llm.ainvoke([
            ("system", WHAT_NEXT_SYSTEM_PROMPT),
            ("human", f"Explain the following priority recommendation:\n\n{json.dumps(payload, ensure_ascii=False, indent=2)}"),
        ])

        formatted_response = format_what_next_response(explanation, top_score)
        return {
            "response": formatted_response,
        }

    except Exception as error:
        logger.exception("What Next workflow error: %s", error)
        return {
            "error": str(error),
            "response": f"Unable to calculate next action: {error}",
        }
