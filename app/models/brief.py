from pydantic import BaseModel, Field


class ScheduleItem(BaseModel):
    time_str: str = Field(description="Time of the event (e.g. 10:00 AM - 11:00 AM).")
    title: str = Field(description="Summary title of the meeting or event.")
    details: str | None = Field(default=None, description="Key details, attendees, or video link.")


class AttentionItem(BaseModel):
    title: str = Field(description="Short title of the item needing attention.")
    source_type: str = Field(description="Source type: Email, Task, Calendar, or Deadline.")
    reason: str = Field(description="Why this item requires immediate attention today.")
    priority: str = Field(default="high", description="Urgency: urgent, high, or medium.")


class FocusBlock(BaseModel):
    time_slot: str = Field(description="Recommended time block (e.g. 09:00 AM – 10:30 AM).")
    activity: str = Field(description="Specific actionable focus work.")
    rationale: str = Field(description="Why this block should be done at this time.")


class MorningBriefData(BaseModel):
    date_header: str = Field(description="Date and day formatted header.")
    today_schedule: list[ScheduleItem] = Field(
        default_factory=list,
        description="Chronological calendar events for today.",
    )
    needs_attention: list[AttentionItem] = Field(
        default_factory=list,
        description="Top 3-5 items across emails, tasks, and deadlines that require attention.",
    )
    suggested_focus: list[FocusBlock] = Field(
        default_factory=list,
        description="Suggested daily timeline allocating focus blocks around scheduled meetings.",
    )
