from datetime import datetime, date, timedelta
import logging
from typing import Any

logger = logging.getLogger(__name__)


def calculate_free_minutes_until_next_meeting(calendar_events: list[dict[str, Any]]) -> int:
    """Calculates available free minutes from now until the next scheduled meeting."""
    now = datetime.now()
    if not calendar_events:
        return 240  # Default to a generous 4-hour block if no meetings today

    for event in calendar_events:
        start_str = event.get("start", "")
        if not start_str:
            continue
        try:
            # Handle ISO formats
            clean_str = start_str.replace("Z", "+00:00")
            if "T" in clean_str:
                dt_part = clean_str.split("+")[0]
                event_start = datetime.fromisoformat(dt_part)
            else:
                event_start = datetime.fromisoformat(clean_str)

            if event_start > now:
                diff_minutes = int((event_start - now).total_seconds() / 60)
                return max(15, diff_minutes)
        except Exception:
            continue

    return 180  # Default 3 hours if all events are in the past


def score_tasks(
    tasks: list[dict[str, Any]],
    calendar_events: list[dict[str, Any]] | None = None,
    urgent_emails: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Deterministically computes a transparent 0-100 priority score for each task.
    """
    calendar_events = calendar_events or []
    urgent_emails = urgent_emails or []
    free_minutes = calculate_free_minutes_until_next_meeting(calendar_events)
    today = date.today()

    urgent_email_subjects = " ".join([e.get("subject", "").lower() for e in urgent_emails])
    urgent_email_senders = " ".join([e.get("from", "").lower() for e in urgent_emails])

    scored_tasks = []

    for task in tasks:
        if task.get("status") in ("completed", "cancelled"):
            continue

        score = 0
        reasons = []

        # 1. Base Priority Score (up to 30 pts)
        priority = task.get("priority", "medium").lower()
        if priority == "urgent":
            score += 30
            reasons.append("Task marked as urgent priority (+30)")
        elif priority == "high":
            score += 22
            reasons.append("Task marked as high priority (+22)")
        elif priority == "medium":
            score += 12
            reasons.append("Standard medium priority (+12)")
        else:
            score += 5

        # 2. Deadline Urgency (up to 35 pts)
        due_str = task.get("due_date")
        if due_str:
            try:
                due_date_clean = due_str.split("T")[0]
                due_d = date.fromisoformat(due_date_clean)

                if due_d < today:
                    score += 35
                    reasons.append("Overdue task past deadline (+35)")
                elif due_d == today:
                    score += 28
                    reasons.append("Due today (+28)")
                elif due_d == today + timedelta(days=1):
                    score += 18
                    reasons.append("Due tomorrow (+18)")
                elif due_d <= today + timedelta(days=3):
                    score += 10
                    reasons.append("Due within 3 days (+10)")
            except Exception:
                pass
        else:
            score += 5  # Small base for unscheduled items

        # 3. Time Fit in Free Calendar Window (up to 15 pts)
        estimated_min = task.get("estimated_minutes") or 30
        if estimated_min <= free_minutes:
            score += 15
            reasons.append(f"Estimated duration ({estimated_min}m) fits in available free window ({free_minutes}m) (+15)")
        else:
            reasons.append(f"Requires {estimated_min}m (exceeds current {free_minutes}m block)")

        # 4. Email Urgency Link (up to 20 pts)
        task_title_words = [w.lower() for w in task.get("title", "").split() if len(w) > 3]
        project_words = [w.lower() for w in (task.get("project") or "").split() if len(w) > 3]
        all_keywords = task_title_words + project_words

        has_email_match = any(kw in urgent_email_subjects or kw in urgent_email_senders for kw in all_keywords)
        if has_email_match:
            score += 20
            reasons.append("Active urgent email/client request matches this task or project (+20)")

        # Clamp score between 0 and 100
        final_score = min(100, max(0, score))

        scored_tasks.append({
            "task": task,
            "score": final_score,
            "reasons": reasons,
            "estimated_minutes": estimated_min,
            "free_minutes_available": free_minutes,
        })

    # Sort descending by priority score
    scored_tasks.sort(key=lambda x: x["score"], reverse=True)
    return scored_tasks
