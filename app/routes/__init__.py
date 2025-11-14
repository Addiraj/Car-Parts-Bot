from flask import Flask
from .search import search_bp
from .webhook import whatsapp_bp
from .admin import admin_bp


def register_routes(app: Flask) -> None:
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.register_blueprint(whatsapp_bp, url_prefix="/webhook/whatsapp")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")


