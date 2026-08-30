from typing import Any, Literal
from typing_extensions import TypedDict

Intent = Literal[
    "morning_brief",
    "what_next",
    "smart_inbox",
    "meeting_prep",
    "follow_up",
    "universal_search",
    "general",
]


class AssistantState(TypedDict, total=False):
    # Original user request
    user_input: str

    # Router decision
    intent: Intent

    # Retrieved data
    emails: list[dict[str, Any]]
    inbox_analysis: list[dict[str, Any]]
    calendar_events: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    search_results: list[dict[str, Any]]

    # Write action requiring human approval
    action_proposal: dict[str, Any]

    # Error information
    error: str

    # Final response
    response: str