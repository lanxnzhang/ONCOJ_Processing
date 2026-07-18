from __future__ import annotations

import xml.etree.ElementTree as ET

from flask import Blueprint, abort, current_app, jsonify, request

from coj.core.dictionary import Dictionary
from compreditor.services.dictionary_service import (
    blank_entry,
    entry_from_payload,
    entry_payload,
    search_dictionary,
    suggest_id,
)
from compreditor.services.validation import validate_dictionary_xml

bp = Blueprint("dictionary", __name__, url_prefix="/api/dictionary")


def repository():
    return current_app.extensions["compreditor_repository"]


def load_dictionary() -> Dictionary:
    return Dictionary.from_file(str(repository().dictionary_path))


@bp.get("")
def search_entries():
    query = request.args.get("q", "").strip()
    limit = min(300, max(1, request.args.get("limit", 100, type=int)))
    if not query:
        return jsonify([])
    return jsonify(search_dictionary(load_dictionary(), query, limit))


@bp.get("/candidates")
def candidates():
    form = request.args.get("form", "").strip()
    entries = load_dictionary().find_by_form(form) if form else []
    return jsonify([entry_payload(entry) for entry in entries])


@bp.get("/suggest-id")
def new_id():
    dictionary = load_dictionary()
    start = max(1, request.args.get("start", 1, type=int))
    entry_id = suggest_id(dictionary, start)
    return jsonify(blank_entry(entry_id, request.args.get("form", "")))


@bp.get("/problems")
def problems():
    root = ET.parse(repository().dictionary_path).getroot()
    return jsonify(validate_dictionary_xml(root))


@bp.get("/<entry_id>")
def get_entry(entry_id: str):
    entry = load_dictionary().get(entry_id)
    if entry is None:
        abort(404, description="Dictionary entry not found")
    return jsonify(entry_payload(entry))


@bp.post("")
def create_entry():
    raw = request.get_json(force=True)
    try:
        dictionary = load_dictionary()
        entry = entry_from_payload(raw)
        if dictionary.get(entry.eid):
            abort(409, description="Dictionary ID already exists")
        if entry.eid.number in dictionary.used_numbers():
            abort(409, description="The numeric portion of this ID is already used")
        dictionary.add(entry)
        repository().save_dictionary(dictionary)
        return jsonify(entry_payload(entry)), 201
    except ValueError as exc:
        abort(400, description=str(exc))


@bp.put("/<entry_id>")
def update_entry(entry_id: str):
    raw = request.get_json(force=True)
    raw["id"] = entry_id
    try:
        dictionary = load_dictionary()
        if dictionary.get(entry_id) is None:
            abort(404, description="Dictionary entry not found")
        entry = entry_from_payload(raw)
        dictionary.add(entry, allow_update=True)
        repository().save_dictionary(dictionary)
        return jsonify(entry_payload(entry))
    except ValueError as exc:
        abort(400, description=str(exc))


@bp.delete("/<entry_id>")
def delete_entry(entry_id: str):
    dictionary = load_dictionary()
    try:
        dictionary.delete(entry_id)
    except KeyError:
        abort(404, description="Dictionary entry not found")
    repository().save_dictionary(dictionary)
    return jsonify({"deleted": True, "id": entry_id})

