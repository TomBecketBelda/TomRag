from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .chat_history_db import (
    clear_history,
    create_user,
    create_conversation,
    delete_conversation,
    get_or_create_default_conversation_id,
    list_users,
    list_conversations,
    load_history,
    save_message,
)
from .chat_rag import generar_respuesta

ROOT_DIR = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(ROOT_DIR / "templates"),
    static_folder=str(ROOT_DIR / "static"),
)


@app.route("/")
def index():
    return render_template("chat.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(silent=True) or {}
    pregunta = body.get("pregunta", "")
    raw_conversation_id = body.get("conversation_id")
    raw_user_id = body.get("user_id")
    conversation_id = raw_conversation_id if isinstance(raw_conversation_id, int) else None
    user_id = raw_user_id if isinstance(raw_user_id, int) else None
    try:
        salida = generar_respuesta(pregunta)
        if (pregunta or "").strip():
            conversation_id = save_message("user", pregunta.strip(), [], conversation_id, user_id=user_id)
        if (salida.get("respuesta") or "").strip():
            conversation_id = save_message(
                "assistant",
                salida["respuesta"].strip(),
                salida.get("fuentes", []),
                conversation_id,
            )
        salida["conversation_id"] = conversation_id
        return jsonify(salida)
    except Exception as e:
        app.logger.exception("Fallo en /api/chat")
        return jsonify({
            "error": str(e),
            "respuesta": f"Error interno del chat: {e}",
            "fuentes": [],
        }), 500


@app.route("/api/history", methods=["GET"])
def api_history():
    raw_conversation_id = request.args.get("conversation_id", default=None, type=int)
    conversation_id = raw_conversation_id or get_or_create_default_conversation_id()
    return jsonify({
        "conversation_id": conversation_id,
        "messages": load_history(conversation_id=conversation_id),
    })


@app.route("/api/history", methods=["DELETE"])
def api_history_delete():
    raw_conversation_id = request.args.get("conversation_id", default=None, type=int)
    clear_history(conversation_id=raw_conversation_id)
    return jsonify({"ok": True, "conversation_id": raw_conversation_id})


@app.route("/api/conversations", methods=["GET"])
def api_conversations():
    return jsonify({"conversations": list_conversations()})


@app.route("/api/conversations", methods=["POST"])
def api_conversations_create():
    body = request.get_json(silent=True) or {}
    title = body.get("title")
    conversation = create_conversation(title if isinstance(title, str) else None)
    return jsonify({"conversation": conversation}), 201


@app.route("/api/users", methods=["GET"])
def api_users():
    return jsonify({"users": list_users()})


@app.route("/api/users", methods=["POST"])
def api_users_create():
    body = request.get_json(silent=True) or {}
    name = body.get("name")
    if not isinstance(name, str):
        return jsonify({"error": "El nombre de usuario es obligatorio"}), 400
    try:
        user = create_user(name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"user": user}), 201


@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
def api_conversations_delete(conversation_id: int):
    deleted = delete_conversation(conversation_id)
    if not deleted:
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404

    conversaciones = list_conversations(limit=1)
    if conversaciones:
        next_conversation_id = conversaciones[0]["id"]
    else:
        next_conversation_id = get_or_create_default_conversation_id()

    return jsonify({
        "ok": True,
        "deleted_conversation_id": conversation_id,
        "next_conversation_id": next_conversation_id,
    })
