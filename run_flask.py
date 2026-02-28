from src.app_flask import app
from src.chat_history_db import init_history_db
from src.chat_rag import inicializar_modelos


if __name__ == "__main__":
    init_history_db()
    inicializar_modelos()
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False, threaded=False)
