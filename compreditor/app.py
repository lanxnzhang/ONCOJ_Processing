from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, render_template
from werkzeug.exceptions import HTTPException

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from compreditor.routes.dictionary import bp as dictionary_bp
from compreditor.routes.documents import bp as documents_bp
from compreditor.routes.search import bp as search_bp
from compreditor.services.repository import WorkspaceRepository


def create_app(repository: WorkspaceRepository | None = None) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
    app.extensions["compreditor_repository"] = repository or WorkspaceRepository()
    app.register_blueprint(documents_bp)
    app.register_blueprint(dictionary_bp)
    app.register_blueprint(search_bp)

    @app.errorhandler(HTTPException)
    def json_error(error: HTTPException):
        return jsonify({"error": error.description}), error.code

    @app.get("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5002)

