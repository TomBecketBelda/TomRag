from __future__ import annotations

from typing import Optional

from .chat_history_db import db_conn, get_or_create_default_conversation_id
from .emotion_meter_graph import run_emotion_meter



def get_last_real_user_message(conversation_id: Optional[int] = None) -> Optional[dict]:
    with db_conn() as conn:
        if conversation_id is None:
            conversation_id = get_or_create_default_conversation_id()

        row = conn.execute(
            """
            SELECT
                m.id,
                m.content,
                m.created_at,
                m.conversation_id,
                m.user_id,
                u.name AS user_name
            FROM chat_messages m
            LEFT JOIN chat_users u ON u.id = m.user_id
            WHERE m.conversation_id = ?
              AND m.role = 'user'
              AND (u.name IS NULL OR lower(u.name) <> 'llm')
            ORDER BY m.id DESC
            LIMIT 1
            """,
            (conversation_id,),
        ).fetchone()

    if not row:
        return None
    return dict(row)



def build_last_message_emotion_meter(conversation_id: Optional[int] = None) -> dict:
    message = get_last_real_user_message(conversation_id=conversation_id)
    if not message:
        return {
            "ok": False,
            "error": "No hay mensajes de usuarios reales en la conversación",
            "conversation_id": conversation_id,
        }

    medidor = run_emotion_meter(message.get("content") or "")
    return {
        "ok": True,
        "conversation_id": int(message["conversation_id"]),
        "message": {
            "id": int(message["id"]),
            "content": message.get("content") or "",
            "created_at": message.get("created_at"),
            "user_id": message.get("user_id"),
            "user_name": message.get("user_name"),
        },
        "emotion_meter": medidor,
    }
