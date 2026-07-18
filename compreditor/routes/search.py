from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from coj.core.dictionary import Dictionary
from compreditor.services.dictionary_service import search_dictionary
from compreditor.services.search_service import search

bp = Blueprint("search", __name__, url_prefix="/api/search")


@bp.post("")
def search_all():
    repository = current_app.extensions["compreditor_repository"]
    raw = request.get_json(force=True)
    scope = str(raw.get("scope", "all"))
    results = []
    if scope in ("all", "dictionary"):
        query = str(raw.get("query", "")).strip()
        if query:
            dictionary = Dictionary.from_file(str(repository.dictionary_path))
            results.extend({"kind": "dictionary", **entry} for entry in search_dictionary(dictionary, query, 200))
    if scope != "dictionary":
        results.extend({"kind": "corpus", **item} for item in search(repository, raw))
    return jsonify(results)

