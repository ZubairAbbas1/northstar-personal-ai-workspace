from app.workflows.action_execution import request_action_approval
from app.workflows.follow_up import follow_up
from app.workflows.general import general
from app.workflows.meeting_prep import meeting_prep
from app.workflows.morning_brief import morning_brief
from app.workflows.smart_inbox import smart_inbox
from app.workflows.universal_search import universal_search
from app.workflows.what_next import what_next

__all__ = [
    "smart_inbox",
    "meeting_prep",
    "morning_brief",
    "what_next",
    "follow_up",
    "universal_search",
    "general",
    "request_action_approval",
]
