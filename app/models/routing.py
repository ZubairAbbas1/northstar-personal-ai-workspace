from typing import Literal
from pydantic import BaseModel, Field

IntentType = Literal[
    "morning_brief",
    "what_next",
    "smart_inbox",
    "meeting_prep",
    "follow_up",
    "universal_search",
    "general",
]


class RouteDecision(BaseModel):
    intent: IntentType = Field(
        description="The assistant workflow that should handle the request."
    )
    reasoning: str | None = Field(
        default=None,
        description="Brief rationale for why this workflow was selected.",
    )
