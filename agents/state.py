from typing import Any, Literal
from typing_extensions import TypedDict

Intent = Literal[
    "morning_brief",
    "what_next",
    "smart_inbox",
    "meeting_prep",
    "follow_up",
    "universal_search",
    "project_status",
    "tasks",
    "calendar",
    "github",
    "slack",
    "general",
]

ModelMode = Literal["fast", "balanced", "quality"]


class AssistantState(TypedDict, total=False):
    # Multi-user tenant identity & conversation tracking
    user_id: str
    thread_id: str

    # User input
    user_input: str

    # Routing
    intent: Intent

    # Model Configuration & Mode
    model_mode: ModelMode
    provider: str | None
    model_name: str | None

    # Context & Retrieved Data
    emails: list[dict[str, Any]]
    inbox_analysis: list[dict[str, Any]]
    calendar_events: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    github_items: list[dict[str, Any]]
    slack_messages: list[dict[str, Any]]
    search_results: list[dict[str, Any]]
    user_preferences: dict[str, Any]

    # Human-In-The-Loop Write Actions
    action_proposal: dict[str, Any]
    action_approved: bool | None

    # Observability & Citations
    sources_used: list[str]

    # Error information
    error: str | None

    # Final response
    response: str
