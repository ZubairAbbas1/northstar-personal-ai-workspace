import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.models.routing import IntentType, RouteDecision
from app.state import AssistantState
from app.workflows.follow_up import follow_up
from app.workflows.general import general
from app.workflows.meeting_prep import meeting_prep
from app.workflows.morning_brief import morning_brief
from app.workflows.smart_inbox import smart_inbox
from app.workflows.universal_search import universal_search
from app.workflows.what_next import what_next

load_dotenv()
logger = logging.getLogger(__name__)

# --------------------------------------------------
# LLM Initializer
# --------------------------------------------------

def get_router_llm() -> ChatGroq:
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    return ChatGroq(
        model=model_name,
        temperature=0,
        max_retries=2,
    )


# --------------------------------------------------
# Router Node
# --------------------------------------------------

ROUTER_SYSTEM_PROMPT = """You are the intent router for a personal AI productivity assistant.

Choose exactly one workflow that best addresses the user's input:

1. morning_brief:
   The user wants an overview of their day, schedule, important emails, tasks, deadlines, or daily priorities.

2. what_next:
   The user wants help deciding what they should work on right now, what task has highest priority, or what to do next.

3. smart_inbox:
   The user specifically wants to inspect, summarize, categorize, prioritize, or triage emails.

4. meeting_prep:
   The user wants briefing, background, or preparation for an upcoming meeting.

5. follow_up:
   The user wants to know who they need to reply to, who owes them a reply, or pending communications.

6. universal_search:
   The user wants to search across multiple domains (emails, calendar, tasks, notes, files).

7. general:
   General questions, memory queries, casual conversation, or requests not covered by the specialized workflows above.
"""


def route_intent(state: AssistantState) -> dict[str, Any]:
    """Routes user input to the appropriate specialized workflow."""
    user_input = state.get("user_input", "")
    lowered = user_input.lower()

    # Route common productivity intents deterministically. This keeps the app
    # useful offline and avoids spending an LLM request on obvious commands.
    if any(phrase in lowered for phrase in ("what should i", "what do i do", "work on right now", "do next", "highest priority")):
        return {"intent": "what_next"}
    if any(phrase in lowered for phrase in ("prepare me", "meeting prep", "next meeting")):
        return {"intent": "meeting_prep"}
    if any(word in lowered for word in ("inbox", "email", "emails")):
        return {"intent": "smart_inbox"}
    if any(phrase in lowered for phrase in ("morning brief", "brief my day", "plan my day")):
        return {"intent": "morning_brief"}
    if any(word in lowered for word in ("search", "find")):
        return {"intent": "universal_search"}

    try:
        llm = get_router_llm()
        router = llm.with_structured_output(RouteDecision)
        decision: RouteDecision = router.invoke([
            ("system", ROUTER_SYSTEM_PROMPT),
            ("human", user_input),
        ])
        return {"intent": decision.intent}
    except Exception as error:
        logger.exception("Router failed, defaulting to general: %s", error)
        return {"intent": "general"}


# --------------------------------------------------
# Conditional Routing Edge
# --------------------------------------------------

def choose_route(state: AssistantState) -> IntentType:
    return state.get("intent", "general")


# --------------------------------------------------
# Graph Definition with Persistence
# --------------------------------------------------

builder = StateGraph(AssistantState)

# Add Nodes
builder.add_node("router", route_intent)
builder.add_node("morning_brief", morning_brief)
builder.add_node("what_next", what_next)
builder.add_node("smart_inbox", smart_inbox)
builder.add_node("meeting_prep", meeting_prep)
builder.add_node("follow_up", follow_up)
builder.add_node("universal_search", universal_search)
builder.add_node("general", general)

# Connect Edges
builder.add_edge(START, "router")

builder.add_conditional_edges(
    "router",
    choose_route,
    {
        "morning_brief": "morning_brief",
        "what_next": "what_next",
        "smart_inbox": "smart_inbox",
        "meeting_prep": "meeting_prep",
        "follow_up": "follow_up",
        "universal_search": "universal_search",
        "general": "general",
    },
)

builder.add_edge("morning_brief", END)
builder.add_edge("what_next", END)
builder.add_edge("smart_inbox", END)
builder.add_edge("meeting_prep", END)
builder.add_edge("follow_up", END)
builder.add_edge("universal_search", END)
builder.add_edge("general", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)
