import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_FILE = DATA_DIR / "chat_history.db"
LEGACY_DB_FILE = ROOT_DIR / "chat_history.db"


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db_path() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Migra la DB antigua si todavía existe en la raíz del proyecto.
    if LEGACY_DB_FILE.exists() and not DB_FILE.exists():
        LEGACY_DB_FILE.replace(DB_FILE)


def init_history_db() -> None:
    ensure_db_path()
    with db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
            """
        )


def save_message(role: str, content: str, sources: Optional[List[str]] = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(sources or [], ensure_ascii=False)
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages(role, content, sources_json, created_at) VALUES (?, ?, ?, ?)",
            (role, content, payload, now),
        )


def load_history(limit: int = 200) -> list[dict]:
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, sources_json, created_at
            FROM chat_messages
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    rows = list(reversed(rows))
    salida = []
    for row in rows:
        try:
            fuentes = json.loads(row["sources_json"] or "[]")
        except Exception:
            fuentes = []

        salida.append(
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "sources": fuentes if isinstance(fuentes, list) else [],
                "created_at": row["created_at"],
            }
        )
    return salida


def clear_history() -> None:
    with db_conn() as conn:
        conn.execute("DELETE FROM chat_messages")
