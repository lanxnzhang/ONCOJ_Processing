from __future__ import annotations

import xml.etree.ElementTree as ET

from flask import Blueprint, abort, current_app, jsonify, request

from coj.core.dictionary import Dictionary
from compreditor.services.editor import apply_operation, update_words
from compreditor.services.validation import validate_document

bp = Blueprint("documents", __name__, url_prefix="/api")


def repository():
    return current_app.extensions["compreditor_repository"]


def dictionary_ids() -> set[str]:
    dictionary = Dictionary.from_file(str(repository().dictionary_path))
    return {str(entry.eid) for entry in dictionary}


def response_payload(collection: str, name: str, selected_path: str = ""):
    payload = repository().payload(collection, name)
    root = repository().load(collection, name).getroot()
    payload["problems"] = validate_document(root, dictionary_ids())
    payload["selected_path"] = selected_path
    return payload


@bp.get("/outline")
def outline():
    return jsonify(repository().outline())


@bp.post("/documents")
def create_document():
    raw = request.get_json(force=True)
    collection = str(raw.get("collection", "text"))
    name = str(raw.get("name", "")).strip()
    if not name.endswith(".xml"):
        name += ".xml"
    try:
        repository().create(collection, name)
    except (ValueError, FileExistsError) as exc:
        abort(409 if isinstance(exc, FileExistsError) else 400, description=str(exc))
    return jsonify(response_payload(collection, name)), 201


@bp.get("/documents/<collection>/<name>")
def get_document(collection: str, name: str):
    try:
        return jsonify(response_payload(collection, name))
    except ValueError as exc:
        abort(400, description=str(exc))
    except FileNotFoundError:
        abort(404, description="Document not found")
    except ET.ParseError as exc:
        abort(422, description=f"Document XML is invalid: {exc}")


@bp.delete("/documents/<collection>/<name>")
def delete_document(collection: str, name: str):
    try:
        repository().delete(collection, name)
    except ValueError as exc:
        abort(400, description=str(exc))
    except FileNotFoundError:
        abort(404, description="Document not found")
    return jsonify({"deleted": True, "collection": collection, "name": name})


@bp.post("/documents/<collection>/<name>/nodes")
def edit_node(collection: str, name: str):
    raw = request.get_json(force=True)
    try:
        tree = repository().load(collection, name)
        selected = apply_operation(tree.getroot(), raw)
        repository().save(collection, name, tree)
        return jsonify(response_payload(collection, name, selected))
    except (ValueError, IndexError) as exc:
        abort(400, description=str(exc))
    except FileNotFoundError:
        abort(404, description="Document not found")


@bp.put("/documents/<collection>/<name>/words")
def edit_words(collection: str, name: str):
    raw = request.get_json(force=True)
    rows = raw.get("rows", [])
    if not isinstance(rows, list):
        abort(400, description="Word rows must be a list")
    try:
        tree = repository().load(collection, name)
        update_words(tree.getroot(), rows)
        repository().save(collection, name, tree)
        return jsonify(response_payload(collection, name))
    except (ValueError, IndexError) as exc:
        abort(400, description=str(exc))
    except FileNotFoundError:
        abort(404, description="Document not found")


@bp.get("/documents/<collection>/<name>/raw")
def raw_document(collection: str, name: str):
    try:
        return repository().visible_path(collection, name).read_text(encoding="utf-8"), 200, {
            "Content-Type": "application/xml; charset=utf-8"
        }
    except (ValueError, FileNotFoundError):
        abort(404, description="Document not found")


@bp.put("/documents/<collection>/<name>/raw")
def replace_raw_document(collection: str, name: str):
    xml_text = request.get_data(as_text=True)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return jsonify({
            "saved": False,
            "problems": [{"severity": "error", "code": "xml", "message": str(exc), "path": ""}],
        }), 422
    try:
        repository().save(collection, name, ET.ElementTree(root))
        return jsonify(response_payload(collection, name))
    except ValueError as exc:
        abort(400, description=str(exc))

