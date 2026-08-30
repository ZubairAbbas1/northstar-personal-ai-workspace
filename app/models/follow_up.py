from typing import Literal
from pydantic import BaseModel, Field

FollowUpCategory = Literal["needs_your_reply", "waiting_on_them"]


class FollowUpItem(BaseModel):
    contact: str = Field(description="Name or email address of the person.")
    subject: str = Field(description="Email subject line.")
    date_str: str = Field(description="Approximate timing or date (e.g. 2 days ago, Aug 24).")
    category: FollowUpCategory = Field(
        description="Category: 'needs_your_reply' (they asked and user owes response) or 'waiting_on_them' (user sent request and is awaiting reply)."
    )
    reason: str = Field(description="Clear explanation of the pending communication.")


class FollowUpReport(BaseModel):
    items: list[FollowUpItem] = Field(
        default_factory=list,
        description="List of detected follow-up items.",
    )
