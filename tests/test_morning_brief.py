from app.models.brief import AttentionItem, FocusBlock, MorningBriefData, ScheduleItem
from app.workflows.morning_brief import format_morning_brief


def test_format_morning_brief():
    brief = MorningBriefData(
        date_header="Tuesday, Aug 26, 2026",
        today_schedule=[
            ScheduleItem(time_str="10:00 AM - 11:00 AM", title="Engineering Standup", details="Zoom"),
            ScheduleItem(time_str="03:30 PM - 04:00 PM", title="Client Demo", details="Sarah"),
        ],
        needs_attention=[
            AttentionItem(title="Client Proposal", source_type="Task", reason="Due today", priority="urgent"),
            AttentionItem(title="Sarah's Email", source_type="Email", reason="Awaiting confirmation", priority="high"),
        ],
        suggested_focus=[
            FocusBlock(time_slot="09:00 AM - 10:00 AM", activity="Finalize proposal deck", rationale="Deliver before meeting"),
            FocusBlock(time_slot="01:00 PM - 03:00 PM", activity="Implement authentication", rationale="Deep work block"),
        ],
    )

    formatted = format_morning_brief(brief)
    assert "MORNING BRIEF" in formatted
    assert "Engineering Standup" in formatted
    assert "[TASK] Client Proposal" in formatted
    assert "09:00 AM - 10:00 AM" in formatted
