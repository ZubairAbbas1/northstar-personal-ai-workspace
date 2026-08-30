from mcp_servers.tasks_server import (
    tasks_complete_task,
    tasks_create_task,
    tasks_get_overdue_tasks,
    tasks_get_task,
    tasks_get_tasks,
    tasks_get_today_tasks,
    tasks_update_task,
)


def test_tasks_mcp_tools():
    # 1. Create task via MCP tool
    created = tasks_create_task(
        title="Test MCP Task",
        project="MCP Testing",
        priority="urgent",
        estimated_minutes=25,
    )
    assert created is not None
    task_id = created["id"]

    # 2. Get task via MCP tool
    fetched = tasks_get_task(task_id)
    assert fetched is not None
    assert fetched["title"] == "Test MCP Task"

    # 3. Update task
    updated = tasks_update_task(task_id=task_id, priority="high")
    assert updated["priority"] == "high"

    # 4. List tasks
    all_t = tasks_get_tasks(project="MCP Testing")
    assert any(t["id"] == task_id for t in all_t)

    # 5. Complete task
    completed = tasks_complete_task(task_id)
    assert completed["status"] == "completed"
