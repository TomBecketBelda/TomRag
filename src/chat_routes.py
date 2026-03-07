from flask import jsonify, render_template, request

from .chat_history_db import (
    clear_history,
    create_conversation,
    create_user,
    delete_user,
    delete_conversation,
    get_or_create_default_conversation_id,
    is_conversation_llm_enabled,
    list_conversations,
    list_users,
    load_history,
    save_message,
    set_conversation_llm_enabled,
)
from .chat_rag import generar_respuesta


def register_chat_routes(app) -> None:
    """Registra todas las rutas web y API del chat en la app Flask."""
    @app.route("/")
    def index():
        """Renderiza la interfaz principal del chat."""
        return render_template("chat.html")

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        """Endpoint legacy: procesa pregunta y guarda mensaje + respuesta del asistente."""
        body = request.get_json(silent=True) or {}
        pregunta = body.get("pregunta", "")
        raw_conversation_id = body.get("conversation_id")
        raw_user_id = body.get("user_id")
        # Normaliza ids: cualquier valor no entero se trata como ausente.
        conversation_id = raw_conversation_id if isinstance(raw_conversation_id, int) else None
        user_id = raw_user_id if isinstance(raw_user_id, int) else None
        try:
            salida = generar_respuesta(pregunta)
            # Solo persistimos mensajes no vacíos para evitar ruido en historial.
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

    @app.route("/api/messages", methods=["POST"])
    def api_messages_create():
        """Crea un mensaje de usuario y opcionalmente genera respuesta del LLM."""
        body = request.get_json(silent=True) or {}
        content = (body.get("content") or "").strip()
        raw_conversation_id = body.get("conversation_id")
        raw_user_id = body.get("user_id")
        # En esta API exigimos tipos estrictos para mantener consistencia.
        conversation_id = raw_conversation_id if isinstance(raw_conversation_id, int) else None
        user_id = raw_user_id if isinstance(raw_user_id, int) else None

        if not content:
            return jsonify({"error": "El mensaje no puede estar vacío"}), 400
        if user_id is None:
            return jsonify({"error": "Debes seleccionar un usuario"}), 400

        conversation_id = save_message(
            "user",
            content,
            [],
            conversation_id=conversation_id,
            user_id=user_id,
        )
        llm_enabled = is_conversation_llm_enabled(conversation_id)
        if not llm_enabled:
            # Cuando LLM está apagado, el endpoint sigue siendo útil para guardar diálogo humano.
            return jsonify({
                "ok": True,
                "conversation_id": conversation_id,
                "llm_responded": False,
                "llm_enabled": False,
            }), 201

        try:
            # El autor de la respuesta automática siempre es el usuario reservado "LLM".
            llm_user = create_user("LLM")
            llm_user_id = llm_user.get("id") if isinstance(llm_user, dict) else None
            salida = generar_respuesta(content)
            respuesta = (salida.get("respuesta") or "").strip()
            if respuesta:
                conversation_id = save_message(
                    "assistant",
                    respuesta,
                    salida.get("fuentes", []),
                    conversation_id=conversation_id,
                    user_id=llm_user_id if isinstance(llm_user_id, int) else None,
                )
            return jsonify({
                "ok": True,
                "conversation_id": conversation_id,
                "llm_responded": bool(respuesta),
                "llm_enabled": True,
            }), 201
        except Exception as e:
            app.logger.exception("Fallo en respuesta LLM para /api/messages")
            # Guardamos la incidencia como mensaje para que quede trazabilidad en la conversación.
            save_message(
                "assistant",
                f"No se pudo generar respuesta del LLM: {e}",
                [],
                conversation_id=conversation_id,
            )
            return jsonify({
                "ok": True,
                "conversation_id": conversation_id,
                "llm_responded": False,
                "llm_enabled": True,
                "warning": str(e),
            }), 201

    @app.route("/api/history", methods=["GET"])
    def api_history():
        """Devuelve mensajes del historial para una conversación concreta."""
        raw_conversation_id = request.args.get("conversation_id", default=None, type=int)
        # Si no llega id, devolvemos/creamos la conversación por defecto para no romper la UI.
        conversation_id = raw_conversation_id or get_or_create_default_conversation_id()
        return jsonify({
            "conversation_id": conversation_id,
            "messages": load_history(conversation_id=conversation_id),
        })

    @app.route("/api/history", methods=["DELETE"])
    def api_history_delete():
        """Elimina el historial de una conversación o de todas si no se indica id."""
        raw_conversation_id = request.args.get("conversation_id", default=None, type=int)
        clear_history(conversation_id=raw_conversation_id)
        return jsonify({"ok": True, "conversation_id": raw_conversation_id})

    @app.route("/api/conversations", methods=["GET"])
    def api_conversations():
        """Lista las conversaciones disponibles para el panel lateral."""
        return jsonify({"conversations": list_conversations()})

    @app.route("/api/conversations", methods=["POST"])
    def api_conversations_create():
        """Crea una nueva conversación con título opcional."""
        body = request.get_json(silent=True) or {}
        title = body.get("title")
        conversation = create_conversation(title if isinstance(title, str) else None)
        return jsonify({"conversation": conversation}), 201

    @app.route("/api/conversations/<int:conversation_id>/llm", methods=["PATCH"])
    def api_conversations_llm_toggle(conversation_id: int):
        """Activa o desactiva el uso del LLM en una conversación."""
        body = request.get_json(silent=True) or {}
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            return jsonify({"ok": False, "error": "El campo 'enabled' debe ser booleano"}), 400

        conversation = set_conversation_llm_enabled(conversation_id, enabled)
        if not conversation:
            return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
        return jsonify({"ok": True, "conversation": conversation})

    @app.route("/api/users", methods=["GET"])
    def api_users():
        """Lista usuarios disponibles para asociar mensajes."""
        return jsonify({"users": list_users()})

    @app.route("/api/users", methods=["POST"])
    def api_users_create():
        """Crea un usuario nuevo validando que el nombre exista."""
        body = request.get_json(silent=True) or {}
        name = body.get("name")
        if not isinstance(name, str):
            return jsonify({"error": "El nombre de usuario es obligatorio"}), 400
        try:
            user = create_user(name)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"user": user}), 201

    @app.route("/api/users/<int:user_id>", methods=["DELETE"])
    def api_users_delete(user_id: int):
        """Elimina un usuario por id si es borrable."""
        try:
            deleted = delete_user(user_id)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        if not deleted:
            return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404
        return jsonify({"ok": True, "deleted_user_id": user_id})

    @app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
    def api_conversations_delete(conversation_id: int):
        """Elimina una conversación y devuelve cuál debe quedar seleccionada."""
        deleted = delete_conversation(conversation_id)
        if not deleted:
            return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404

        conversaciones = list_conversations(limit=1)
        # Tras borrar, el frontend necesita un siguiente chat seleccionado para mantener continuidad.
        if conversaciones:
            next_conversation_id = conversaciones[0]["id"]
        else:
            next_conversation_id = get_or_create_default_conversation_id()

        return jsonify({
            "ok": True,
            "deleted_conversation_id": conversation_id,
            "next_conversation_id": next_conversation_id,
        })
