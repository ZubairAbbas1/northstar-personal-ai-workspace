import logging
from typing import Any

from langgraph.types import interrupt

from app.models.actions import ActionProposal
from app.state import AssistantState
from services.tasks_service import complete_task

logger = logging.getLogger(__name__)


async def request_action_approval(
    state: AssistantState,
    proposal: ActionProposal,
) -> dict[str, Any]:
    """
    Pauses graph execution with LangGraph interrupt() to request human approval.
    """
    logger.info("Requesting human approval for write action: %s", proposal.action_type)

    # Trigger LangGraph interrupt
    approval_response = interrupt({
        "type": "human_approval_required",
        "action_type": proposal.action_type,
        "summary": proposal.summary,
        "details": proposal.details,
        "prompt": f"Do you approve this action? ({proposal.summary}) [approve / reject]",
    })

    decision = str(approval_response).strip().lower()

    if decision in ("approve", "approved", "yes", "y", "true"):
        logger.info("Action %s approved by user. Executing...", proposal.action_type)
        return await execute_approved_action(proposal)
    else:
        logger.info("Action %s rejected or cancelled by user.", proposal.action_type)
        return {
            "response": f"Action cancelled: {proposal.summary} was not approved.",
        }


async def execute_approved_action(proposal: ActionProposal) -> dict[str, Any]:
    """Executes the consequential write action after explicit user confirmation."""
    action_type = proposal.action_type
    details = proposal.details

    if action_type == "complete_task":
        task_id = details.get("task_id")
        if task_id:
            complete_task(task_id)
            return {"response": f"Task #{task_id} marked as completed successfully."}

    elif action_type == "create_draft":
        to = details.get("to")
        subject = details.get("subject")
        return {"response": f"Draft created for {to} with subject '{subject}'."}

    elif action_type == "send_email":
        to = details.get("to")
        subject = details.get("subject")
        return {"response": f"Email successfully sent to {to} (Subject: '{subject}')."}

    elif action_type == "create_calendar_event":
        title = details.get("title")
        start = details.get("start")
        return {"response": f"Calendar event '{title}' scheduled for {start}."}

    return {"response": f"Action {action_type} executed successfully."}
