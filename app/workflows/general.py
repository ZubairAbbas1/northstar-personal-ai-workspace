import json
import logging
import os
from typing import Any

from langchain_groq import ChatGroq

from app.state import AssistantState
from services.memory_service import get_facts, search_facts, store_fact

logger = logging.getLogger(__name__)

GENERAL_SYSTEM_PROMPT = """You are an executive personal AI productivity assistant.

You have access to persistent memory facts regarding the user's projects, preferences, and important contacts.

Instructions:
- If the user asks you to remember, save, or store a fact (e.g. "Remember that Project Alpha is high priority"), acknowledge that you have stored it into persistent memory.
- If the user asks a question, answer concisely, politely, and use any relevant long-term memory context provided.
"""


async def general(
    state: AssistantState,
    llm: ChatGroq | None = None,
) -> dict[str, Any]:
    """LangGraph node for general conversation and explicit memory storage."""
    user_input = state.get("user_input", "")

    # Check for explicit memory store requests: "Remember that ...", "Save fact ...", "Note that ..."
    lower_input = user_input.lower().strip()
    if lower_input.startswith("remember that ") or lower_input.startswith("remember: ") or lower_input.startswith("note that "):
        fact_text = user_input.split("that", 1)[-1] if "that" in user_input else user_input.split(":", 1)[-1]
        fact_text = fact_text.strip()
        store_fact(category="user_preference", fact=fact_text)
        return {
            "response": f"I've saved this to long-term memory: \"{fact_text}\". I will keep this in mind for future briefings and decisions.",
        }

    # Retrieve relevant memory facts
    relevant_facts = search_facts(user_input[:50]) or get_facts()[:5]

    if llm is None:
        model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        llm = ChatGroq(
            model=model_name,
            temperature=0.3,
            max_retries=2,
        )

    context_str = "\n".join([f"• [{f['category']}] {f['fact']}" for f in relevant_facts]) if relevant_facts else "None"

    response = await llm.ainvoke([
        ("system", f"{GENERAL_SYSTEM_PROMPT}\n\nRelevant Context & Facts:\n{context_str}"),
        ("human", user_input),
    ])

    return {
        "response": response.content,
    }
