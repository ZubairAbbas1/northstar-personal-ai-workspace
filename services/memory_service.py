from datetime import datetime
import logging
from pathlib import Path
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DB = BASE_DIR / "memory.db"


def init_memory_db():
    conn = sqlite3.connect(str(MEMORY_DB))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT,
            fact TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


init_memory_db()


def store_fact(category: str, fact: str, key: str | None = None) -> dict[str, Any]:
    """Stores a durable context fact."""
    conn = sqlite3.connect(str(MEMORY_DB))
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT INTO memory_facts (category, key, fact, created_at) VALUES (?, ?, ?, ?)",
            (category, key, fact, now_str),
        )
        conn.commit()
        fact_id = cursor.lastrowid
        return {"id": fact_id, "category": category, "key": key, "fact": fact, "created_at": now_str}
    finally:
        conn.close()


def get_facts(category: str | None = None) -> list[dict[str, Any]]:
    """Retrieves stored facts, optionally filtered by category."""
    conn = sqlite3.connect(str(MEMORY_DB))
    cursor = conn.cursor()
    try:
        if category:
            cursor.execute("SELECT id, category, key, fact, created_at FROM memory_facts WHERE category = ? ORDER BY created_at DESC", (category,))
        else:
            cursor.execute("SELECT id, category, key, fact, created_at FROM memory_facts ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [{"id": r[0], "category": r[1], "key": r[2], "fact": r[3], "created_at": r[4]} for r in rows]
    finally:
        conn.close()


def search_facts(query: str) -> list[dict[str, Any]]:
    """Searches memory facts matching a keyword."""
    conn = sqlite3.connect(str(MEMORY_DB))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, category, key, fact, created_at FROM memory_facts WHERE fact LIKE ? OR key LIKE ? ORDER BY created_at DESC",
            (f"%{query}%", f"%{query}%"),
        )
        rows = cursor.fetchall()
        return [{"id": r[0], "category": r[1], "key": r[2], "fact": r[3], "created_at": r[4]} for r in rows]
    finally:
        conn.close()


def delete_fact(fact_id: int) -> bool:
    """Deletes a stored fact by ID."""
    conn = sqlite3.connect(str(MEMORY_DB))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM memory_facts WHERE id = ?", (fact_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
