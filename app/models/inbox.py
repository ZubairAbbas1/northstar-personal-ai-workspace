from typing import Literal
from pydantic import BaseModel, Field

InboxCategory = Literal[
    "urgent",
    "action_needed",
    "fyi",
    "ignore",
]


class InboxItem(BaseModel):
    email_id: str = Field(
        description="The unique Gmail message ID corresponding to the classified email."
    )
    category: InboxCategory = Field(
        description="Classification category: urgent (immediate critical deadline/blocker/change), "
                    "action_needed (user must respond, decide, or act), "
                    "fyi (useful contextual information requiring no direct action), "
                    "ignore (marketing, newsletters, automated noise)."
    )
    reason: str = Field(
        description="Concise 1-sentence explanation for this classification."
    )
    suggested_action: str | None = Field(
        default=None,
        description="Concrete, actionable next step for the user, or None if no action required."
    )


class InboxAnalysis(BaseModel):
    items: list[InboxItem] = Field(
        default_factory=list,
        description="List of classified inbox email items."
    )
