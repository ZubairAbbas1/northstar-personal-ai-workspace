from pydantic import BaseModel, Field


class MeetingPrepBrief(BaseModel):
    meeting_title: str = Field(description="Title or subject of the meeting.")
    time_range: str = Field(description="Scheduled time range (e.g. 3:00 PM - 4:00 PM).")
    attendees: list[str] = Field(default_factory=list, description="Names or emails of attendees.")
    purpose: str = Field(description="Summary purpose of the meeting.")
    recent_context: list[str] = Field(
        default_factory=list,
        description="Key recent context points discovered from recent email threads or messages with attendees.",
    )
    outstanding_items: list[str] = Field(
        default_factory=list,
        description="Pending deliverables, unconfirmed decisions, or active requests.",
    )
    suggested_preparation: list[str] = Field(
        default_factory=list,
        description="Numbered actionable preparation steps the user should take before the meeting.",
    )
    questions_worth_asking: list[str] = Field(
        default_factory=list,
        description="Strategic, insightful questions worth asking during the meeting.",
    )
