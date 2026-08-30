from typing import Any, Literal
from pydantic import BaseModel, Field

ActionType = Literal[
    "send_email",
    "create_draft",
    "create_calendar_event",
    "update_calendar_event",
    "complete_task",
    "delete_task",
]


class ActionProposal(BaseModel):
    action_type: ActionType = Field(description="The type of consequential write action.")
    summary: str = Field(description="Human-readable 1-sentence summary of the action.")
    details: dict[str, Any] = Field(default_factory=dict, description="Payload / arguments for the action.")
    requires_approval: bool = Field(default=True, description="Whether human approval is required.")
