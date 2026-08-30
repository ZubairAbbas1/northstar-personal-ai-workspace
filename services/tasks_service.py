from datetime import datetime, date
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "tasks.db"


def get_db_connection():
    """Initializes and returns a database connection (PostgreSQL if configured, SQLite fallback)."""
    pg_host = os.getenv("POSTGRES_HOST")
    pg_db = os.getenv("POSTGRES_DB")
    pg_user = os.getenv("POSTGRES_USER")
    pg_password = os.getenv("POSTGRES_PASSWORD")
    pg_port = os.getenv("POSTGRES_PORT", "5432")

    if pg_host and pg_db and pg_user and pg_host not in ("localhost", "127.0.0.1"):
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(
                host=pg_host,
                port=pg_port,
                dbname=pg_db,
                user=pg_user,
                password=pg_password,
            )
            return conn, "postgres"
        except Exception as e:
            logger.warning("PostgreSQL connection failed, falling back to SQLite: %s", e)

    # SQLite fallback
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


def init_db():
    """Ensures tasks table exists in database."""
    conn, dialect = get_db_connection()
    cursor = conn.cursor()
    try:
        if dialect == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    project VARCHAR(100),
                    priority VARCHAR(20) DEFAULT 'medium',
                    status VARCHAR(20) DEFAULT 'todo',
                    due_date TIMESTAMP,
                    estimated_minutes INTEGER DEFAULT 30,
                    source_type VARCHAR(50) DEFAULT 'manual',
                    source_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    project TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'todo',
                    due_date TEXT,
                    estimated_minutes INTEGER DEFAULT 30,
                    source_type TEXT DEFAULT 'manual',
                    source_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                );
            """)
        conn.commit()
    finally:
        conn.close()


init_db()


def row_to_dict(row: Any) -> dict[str, Any]:
    """Converts a sqlite3.Row or tuple to a clean dictionary."""
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def create_task(
    title: str,
    description: str | None = None,
    project: str | None = None,
    priority: str = "medium",
    due_date: str | None = None,
    estimated_minutes: int = 30,
    source_type: str = "manual",
    source_id: str | None = None,
) -> dict[str, Any]:
    """Creates a new task in the database."""
    conn, dialect = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    try:
        if dialect == "postgres":
            cursor.execute(
                """
                INSERT INTO tasks (title, description, project, priority, status, due_date, estimated_minutes, source_type, source_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'todo', %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (title, description, project, priority, due_date, estimated_minutes, source_type, source_id, now_str, now_str),
            )
            task_id = cursor.fetchone()[0]
        else:
            cursor.execute(
                """
                INSERT INTO tasks (title, description, project, priority, status, due_date, estimated_minutes, source_type, source_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'todo', ?, ?, ?, ?, ?, ?);
                """,
                (title, description, project, priority, due_date, estimated_minutes, source_type, source_id, now_str, now_str),
            )
            task_id = cursor.lastrowid
        conn.commit()
        return get_task(task_id) or {}
    finally:
        conn.close()


def get_task(task_id: int | str) -> dict[str, Any] | None:
    """Retrieves a single task by its ID."""
    conn, dialect = get_db_connection()
    cursor = conn.cursor()
    try:
        param = "%s" if dialect == "postgres" else "?"
        cursor.execute(f"SELECT * FROM tasks WHERE id = {param}", (int(task_id),))
        row = cursor.fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


def get_tasks(
    status: str | None = None,
    project: str | None = None,
    priority: str | None = None,
) -> list[dict[str, Any]]:
    """Lists tasks with optional status/project/priority filters."""
    conn, dialect = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        placeholder = "%s" if dialect == "postgres" else "?"

        if status:
            query += f" AND status = {placeholder}"
            params.append(status)
        if project:
            query += f" AND project = {placeholder}"
            params.append(project)
        if priority:
            query += f" AND priority = {placeholder}"
            params.append(priority)

        query += " ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, created_at DESC"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_today_tasks() -> list[dict[str, Any]]:
    """Retrieves all pending tasks due today or without a deadline."""
    today_str = date.today().isoformat()
    conn, dialect = get_db_connection()
    cursor = conn.cursor()
    try:
        placeholder = "%s" if dialect == "postgres" else "?"
        query = f"""
            SELECT * FROM tasks
            WHERE status != 'completed' AND status != 'cancelled'
            AND (due_date LIKE {placeholder} OR due_date IS NULL OR due_date = '')
            ORDER BY priority DESC, created_at ASC
        """
        cursor.execute(query, (f"{today_str}%",))
        rows = cursor.fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_overdue_tasks() -> list[dict[str, Any]]:
    """Retrieves all pending tasks with a due date prior to today."""
    today_str = date.today().isoformat()
    conn, dialect = get_db_connection()
    cursor = conn.cursor()
    try:
        placeholder = "%s" if dialect == "postgres" else "?"
        query = f"""
            SELECT * FROM tasks
            WHERE status != 'completed' AND status != 'cancelled'
            AND due_date IS NOT NULL AND due_date != '' AND due_date < {placeholder}
            ORDER BY due_date ASC
        """
        cursor.execute(query, (today_str,))
        rows = cursor.fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_upcoming_tasks(days_ahead: int = 7) -> list[dict[str, Any]]:
    """Retrieves active tasks due within the upcoming N days."""
    today_str = date.today().isoformat()
    conn, dialect = get_db_connection()
    cursor = conn.cursor()
    try:
        placeholder = "%s" if dialect == "postgres" else "?"
        query = f"""
            SELECT * FROM tasks
            WHERE status != 'completed' AND status != 'cancelled'
            AND due_date >= {placeholder}
            ORDER BY due_date ASC
            LIMIT 20
        """
        cursor.execute(query, (today_str,))
        rows = cursor.fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_task(
    task_id: int | str,
    title: str | None = None,
    description: str | None = None,
    project: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    due_date: str | None = None,
    estimated_minutes: int | None = None,
) -> dict[str, Any] | None:
    """Updates fields of an existing task."""
    conn, dialect = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    try:
        updates = []
        params = []
        placeholder = "%s" if dialect == "postgres" else "?"

        if title is not None:
            updates.append(f"title = {placeholder}")
            params.append(title)
        if description is not None:
            updates.append(f"description = {placeholder}")
            params.append(description)
        if project is not None:
            updates.append(f"project = {placeholder}")
            params.append(project)
        if priority is not None:
            updates.append(f"priority = {placeholder}")
            params.append(priority)
        if status is not None:
            updates.append(f"status = {placeholder}")
            params.append(status)
            if status == "completed":
                updates.append(f"completed_at = {placeholder}")
                params.append(now_str)
        if due_date is not None:
            updates.append(f"due_date = {placeholder}")
            params.append(due_date)
        if estimated_minutes is not None:
            updates.append(f"estimated_minutes = {placeholder}")
            params.append(estimated_minutes)

        updates.append(f"updated_at = {placeholder}")
        params.append(now_str)

        params.append(int(task_id))
        set_clause = ", ".join(updates)
        cursor.execute(f"UPDATE tasks SET {set_clause} WHERE id = {placeholder}", tuple(params))
        conn.commit()
        return get_task(task_id)
    finally:
        conn.close()


def complete_task(task_id: int | str) -> dict[str, Any] | None:
    """Marks a task as completed."""
    return update_task(task_id, status="completed")
