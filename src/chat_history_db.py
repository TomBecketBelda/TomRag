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
            CREATE TABLE IF NOT EXISTS chat_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'Nuevo chat',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                conversation_id INTEGER
            )
            """
        )
        cols = conn.execute("PRAGMA table_info(chat_messages)").fetchall()
        col_names = {row["name"] for row in cols}
        if "conversation_id" not in col_names:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN conversation_id INTEGER")

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id_id
            ON chat_messages(conversation_id, id)
            """
        )
        _ensure_default_conversation(conn)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_default_conversation(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM chat_conversations ORDER BY id ASC LIMIT 1").fetchone()
    if row:
        default_id = int(row["id"])
    else:
        now = _utc_now_iso()
        cur = conn.execute(
            "INSERT INTO chat_conversations(title, created_at, updated_at) VALUES (?, ?, ?)",
            ("Chat 1", now, now),
        )
        default_id = int(cur.lastrowid)

    conn.execute(
        "UPDATE chat_messages SET conversation_id = ? WHERE conversation_id IS NULL",
        (default_id,),
    )
    return default_id


def create_conversation(title: Optional[str] = None) -> dict:
    now = _utc_now_iso()
    final_title = (title or "").strip() or "Nuevo chat"
    with db_conn() as conn:
        cur = conn.execute(
            "INSERT INTO chat_conversations(title, created_at, updated_at) VALUES (?, ?, ?)",
            (final_title, now, now),
        )
        conversation_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM chat_conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
    return dict(row) if row else {"id": conversation_id, "title": final_title, "created_at": now, "updated_at": now}


def list_conversations(limit: int = 100) -> list[dict]:
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.created_at,
                c.updated_at,
                COUNT(m.id) AS message_count,
                (
                    SELECT mm.content
                    FROM chat_messages mm
                    WHERE mm.conversation_id = c.id
                    ORDER BY mm.id DESC
                    LIMIT 1
                ) AS last_message
            FROM chat_conversations c
            LEFT JOIN chat_messages m ON m.conversation_id = c.id
            GROUP BY c.id, c.title, c.created_at, c.updated_at
            ORDER BY c.updated_at DESC, c.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_or_create_default_conversation_id() -> int:
    with db_conn() as conn:
        return _ensure_default_conversation(conn)


def _touch_conversation(conn: sqlite3.Connection, conversation_id: int) -> None:
    conn.execute(
        "UPDATE chat_conversations SET updated_at = ? WHERE id = ?",
        (_utc_now_iso(), conversation_id),
    )


def save_message(
    role: str,
    content: str,
    sources: Optional[List[str]] = None,
    conversation_id: Optional[int] = None,
) -> int:
    now = _utc_now_iso()
    payload = json.dumps(sources or [], ensure_ascii=False)
    with db_conn() as conn:
        if conversation_id is None:
            conversation_id = _ensure_default_conversation(conn)
        exists = conn.execute(
            "SELECT id FROM chat_conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if not exists:
            conversation_id = _ensure_default_conversation(conn)
        conn.execute(
            """
            INSERT INTO chat_messages(role, content, sources_json, created_at, conversation_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (role, content, payload, now, conversation_id),
        )
        _touch_conversation(conn, int(conversation_id))
    return int(conversation_id)


def load_history(conversation_id: Optional[int] = None, limit: int = 200) -> list[dict]:
    with db_conn() as conn:
        if conversation_id is None:
            conversation_id = _ensure_default_conversation(conn)
        rows = conn.execute(
            """
            SELECT id, role, content, sources_json, created_at, conversation_id
            FROM chat_messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
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
                "conversation_id": row["conversation_id"],
            }
        )
    return salida


def clear_history(conversation_id: Optional[int] = None) -> None:
    with db_conn() as conn:
        if conversation_id is None:
            conn.execute("DELETE FROM chat_messages")
            now = _utc_now_iso()
            conn.execute("UPDATE chat_conversations SET updated_at = ?", (now,))
            return
        conn.execute("DELETE FROM chat_messages WHERE conversation_id = ?", (conversation_id,))
        _touch_conversation(conn, int(conversation_id))
