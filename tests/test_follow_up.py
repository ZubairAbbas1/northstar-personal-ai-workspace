from app.models.follow_up import FollowUpItem, FollowUpReport
from app.workflows.follow_up import format_follow_up_response


def test_format_follow_up_response():
    report = FollowUpReport(
        items=[
            FollowUpItem(
                contact="Sarah Connor",
                subject="Q4 Roadmap Proposal",
                date_str="2 days ago",
                category="needs_your_reply",
                reason="Sarah asked for feedback on Section 3 timeline and no reply was sent.",
            ),
            FollowUpItem(
                contact="David Smith",
                subject="Contract Agreement",
                date_str="5 days ago",
                category="waiting_on_them",
                reason="You sent the final contract for signature and are awaiting execution.",
            ),
        ]
    )

    formatted = format_follow_up_response(report)
    assert "FOLLOW-UP RADAR" in formatted
    assert "NEEDS YOUR REPLY" in formatted
    assert "Sarah Connor" in formatted
    assert "WAITING ON THEM" in formatted
    assert "David Smith" in formatted
