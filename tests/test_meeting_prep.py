from app.models.meeting import MeetingPrepBrief
from app.workflows.meeting_prep import format_meeting_brief


def test_format_meeting_brief():
    brief = MeetingPrepBrief(
        meeting_title="Q4 Product Roadmap Sync",
        time_range="3:00 PM - 4:00 PM",
        attendees=["Sarah Connor <sarah@acme.com>", "Michele <michele@acme.com>"],
        purpose="Align on mobile application timeline for Q4 release.",
        recent_context=["Sarah sent revised pricing structure yesterday."],
        outstanding_items=["Finalize QA sign-off date."],
        suggested_preparation=["Review new proposal deck."],
        questions_worth_asking=["Is mobile still planned for Phase 2?"],
    )

    formatted = format_meeting_brief(brief)
    assert "NEXT MEETING" in formatted
    assert "Q4 Product Roadmap Sync" in formatted
    assert "Sarah Connor" in formatted
    assert "Is mobile still planned for Phase 2?" in formatted
