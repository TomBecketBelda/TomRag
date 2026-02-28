from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .chat_history_db import clear_history, load_history, save_message
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
    try:
        salida = generar_respuesta(pregunta)
        if (pregunta or "").strip():
            save_message("user", pregunta.strip(), [])
        if (salida.get("respuesta") or "").strip():
            save_message("assistant", salida["respuesta"].strip(), salida.get("fuentes", []))
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
    return jsonify({"messages": load_history()})


@app.route("/api/history", methods=["DELETE"])
def api_history_delete():
    clear_history()
    return jsonify({"ok": True})
