from datetime import date, timedelta
from services.tasks_service import (
    complete_task,
    create_task,
    get_overdue_tasks,
    get_task,
    get_tasks,
    get_today_tasks,
    update_task,
)


def test_create_and_get_task():
    task = create_task(
        title="Review Q4 financial deck",
        description="Check gross margin calculations",
        project="Finance",
        priority="high",
        due_date=date.today().isoformat(),
        estimated_minutes=45,
    )

    assert task is not None
    assert task["title"] == "Review Q4 financial deck"
    assert task["priority"] == "high"
    assert task["status"] == "todo"

    fetched = get_task(task["id"])
    assert fetched is not None
    assert fetched["id"] == task["id"]


def test_get_today_and_overdue_tasks():
    today_str = date.today().isoformat()
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()

    t_today = create_task(title="Today Urgent Task", due_date=today_str, priority="urgent")
    t_overdue = create_task(title="Yesterday Overdue Task", due_date=yesterday_str, priority="high")

    today_list = get_today_tasks()
    assert any(t["id"] == t_today["id"] for t in today_list)

    overdue_list = get_overdue_tasks()
    assert any(t["id"] == t_overdue["id"] for t in overdue_list)


def test_update_and_complete_task():
    task = create_task(title="Temporary Task to complete")
    updated = update_task(task["id"], priority="urgent")
    assert updated["priority"] == "urgent"

    completed = complete_task(task["id"])
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None
