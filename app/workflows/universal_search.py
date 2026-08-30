import asyncio
import json
import logging
import os
from typing import Any

from langchain_groq import ChatGroq

from app.mcp_client import get_calendar_tools, get_gmail_tools, get_tasks_tools
from app.models.search import UniversalSearchReport
from app.state import AssistantState
from app.workflows.smart_inbox import parse_mcp_tool_result
from rag.retriever import query_vault

logger = logging.getLogger(__name__)

UNIVERSAL_SEARCH_SYSTEM_PROMPT = """You are an executive knowledge retriever for a personal AI productivity assistant.

Synthesize search results retrieved from multiple sources (Emails, Calendar, Tasks, Files/RAG) into a structured executive report.

Guidelines:
1. Summarize the most relevant findings under each source.
2. Deduplicate repetitive information.
3. Formulate a 1-2 sentence 'key_takeaway' summarizing recent developments or the current state of this topic.
4. If a source has no matches, leave that list empty.
"""


def format_universal_search_response(report: UniversalSearchReport) -> str:
    """Formats UniversalSearchReport into a structured summary."""
    lines: list[str] = [f"UNIVERSAL SEARCH: \"{report.query}\"\n"]

    if report.email_summary:
        lines.append("EMAILS")
        for item in report.email_summary:
            lines.append(f"• {item}")
        lines.append("")

    if report.calendar_summary:
        lines.append("CALENDAR")
        for item in report.calendar_summary:
            lines.append(f"• {item}")
        lines.append("")

    if report.tasks_summary:
        lines.append("TASKS")
        for item in report.tasks_summary:
            lines.append(f"• {item}")
        lines.append("")

    if report.files_summary:
        lines.append("FILES & DOCUMENTS")
        for item in report.files_summary:
            lines.append(f"• {item}")
        lines.append("")

    if report.key_takeaway:
        lines.append(f"KEY TAKEAWAYS\n{report.key_takeaway}")

    if not any([report.email_summary, report.calendar_summary, report.tasks_summary, report.files_summary]):
        lines.append("No matching records found across your emails, calendar, tasks, or documents.")

    return "\n".join(lines).strip()


async def universal_search(
    state: AssistantState,
    llm: ChatGroq | None = None,
) -> dict[str, Any]:
    """LangGraph node for universal cross-source search."""
    user_input = state.get("user_input", "")
    # Clean query string
    query = user_input.replace("search for", "").replace("find", "").replace("search", "").strip(" ?.\"'")
    if not query:
        query = user_input

    try:
        # 1. Parallel search across 4 sources
        async def search_gmail():
            g_tools = await get_gmail_tools()
            s_tool = next((t for t in g_tools if t.name == "gmail_search"), None)
            if s_tool:
                try:
                    res = await s_tool.ainvoke({"query": query, "max_results": 5})
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
                    logger.warning("Gmail search error: %s", e)
            return []

        async def search_cal():
            c_tools = await get_calendar_tools()
            s_tool = next((t for t in c_tools if t.name == "calendar_search_events"), None)
            if s_tool:
                try:
                    res = await s_tool.ainvoke({"query": query, "max_results": 5})
                    return parse_mcp_tool_result(res)
                except Exception as e:
                    logger.warning("Calendar search error: %s", e)
            return []

        async def search_tasks():
            t_tools = await get_tasks_tools()
            s_tool = next((t for t in t_tools if t.name == "tasks_get_tasks"), None)
            if s_tool:
                try:
                    res = await s_tool.ainvoke({})
                    all_tasks = parse_mcp_tool_result(res)
                    # Simple client-side filter
                    matched = [
                        t for t in all_tasks
                        if query.lower() in t.get("title", "").lower()
                        or query.lower() in (t.get("description") or "").lower()
                        or query.lower() in (t.get("project") or "").lower()
                    ]
                    return matched[:5]
                except Exception as e:
                    logger.warning("Tasks search error: %s", e)
            return []

        def search_rag():
            try:
                return query_vault(query, top_k=3)
            except Exception as e:
                logger.warning("RAG search error: %s", e)
                return []

        gmail_res, cal_res, tasks_res, rag_res = await asyncio.gather(
            search_gmail(),
            search_cal(),
            search_tasks(),
            asyncio.to_thread(search_rag),
            return_exceptions=True,
        )

        search_payload = {
            "query": query,
            "emails": gmail_res if isinstance(gmail_res, list) else [],
            "calendar": cal_res if isinstance(cal_res, list) else [],
            "tasks": tasks_res if isinstance(tasks_res, list) else [],
            "documents": rag_res if isinstance(rag_res, list) else [],
        }

        # 2. LLM synthesis with Groq
        if llm is None:
            model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            llm = ChatGroq(
                model=model_name,
                temperature=0,
                max_retries=2,
            )

        structured_llm = llm.with_structured_output(UniversalSearchReport)
        report: UniversalSearchReport = await structured_llm.ainvoke([
            ("system", UNIVERSAL_SEARCH_SYSTEM_PROMPT),
            ("human", f"Synthesize these search results:\n\n{json.dumps(search_payload, ensure_ascii=False, indent=2)}"),
        ])

        formatted_response = format_universal_search_response(report)
        return {
            "response": formatted_response,
        }

    except Exception as error:
        logger.exception("Universal search workflow error: %s", error)
        return {
            "error": str(error),
            "response": f"Universal search failed: {error}",
        }
