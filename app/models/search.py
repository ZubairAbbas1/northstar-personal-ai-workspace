from pydantic import BaseModel, Field


class UniversalSearchReport(BaseModel):
    query: str = Field(description="The search query.")
    email_summary: list[str] = Field(default_factory=list, description="Key matching emails or email threads.")
    calendar_summary: list[str] = Field(default_factory=list, description="Matching calendar events or upcoming meetings.")
    tasks_summary: list[str] = Field(default_factory=list, description="Matching open or completed tasks.")
    files_summary: list[str] = Field(default_factory=list, description="Matching document chunks or files found in RAG.")
    key_takeaway: str | None = Field(
        default=None,
        description="Concise synthesis explaining the current state or latest developments regarding the search topic.",
    )
