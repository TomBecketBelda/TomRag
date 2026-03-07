from pathlib import Path

from flask import Flask

from .chat_routes import register_chat_routes

ROOT_DIR = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(ROOT_DIR / "templates"),
    static_folder=str(ROOT_DIR / "static"),
)
register_chat_routes(app)
