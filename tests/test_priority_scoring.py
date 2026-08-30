from datetime import date, timedelta
from services.priority_scoring import calculate_free_minutes_until_next_meeting, score_tasks


def test_free_minutes_calculation():
    events = [
        {"summary": "Standup", "start": "2026-08-26T10:00:00Z"},
    ]
    minutes = calculate_free_minutes_until_next_meeting(events)
    assert minutes >= 15


def test_score_tasks_deterministic():
    today_str = date.today().isoformat()
    yesterday_str = (date.today() - timedelta(days=2)).isoformat()

    tasks = [
        {
            "id": 1,
            "title": "Fix critical production database bug",
            "project": "Infra",
            "priority": "urgent",
            "due_date": yesterday_str,
            "estimated_minutes": 30,
            "status": "todo",
        },
        {
            "id": 2,
            "title": "Clean desktop downloads folder",
            "project": "Personal",
            "priority": "low",
            "due_date": None,
            "estimated_minutes": 15,
            "status": "todo",
        },
    ]

    scored = score_tasks(tasks, calendar_events=[], urgent_emails=[])

    assert len(scored) == 2
    # Urgent + overdue task must score higher than low priority task
    assert scored[0]["task"]["id"] == 1
    assert scored[0]["score"] > scored[1]["score"]
    assert scored[0]["score"] >= 80
