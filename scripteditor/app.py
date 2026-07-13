from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
sys.path.insert(0, str(ROOT / "src"))

from coj.core.dictionary import Dictionary, DictEntry
from coj.core.corpus import CorpusDocument
from coj.core.kana import phonemic_to_kana
from coj.core.lemma_id import IDGenerator, LemmaID
from coj.core.tags import MULTI_VALUE_FIELDS

DICTIONARY_PATH = ROOT / "data" / "xml" / "dict" / "dictionary.xml"
_dictionary: Dictionary | None = None
_manual_id_reservations: dict[str, set[int]] = {}
DICT_SEARCH_FIELDS = {
    "form": (".FORM",),
    "gloss": (".GLOSS",),
    "meaning": (".MEANING",),
    "pos": (".POS",),
    "note": (".NOTE", ".NOTES"),
    "compound": (".COMPOUND",),
    "related": (".RELATED", ".MKTARGETNEW", ".DERIVATION", ".TRANSREL", ".PTR"),
}
PROCESSORS = {
    "compound_lemma_forgui": (HERE / "scripts" / "compound_lemma_forgui.py", "compound lemma"),
    "lemma_forgui": (HERE / "scripts" / "lemma_forgui.py", "lemma"),
    "mk_lemma_forgui": (HERE / "scripts" / "mk_lemma_forgui.py", "mk lemma"),
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


@app.errorhandler(HTTPException)
def json_http_error(error: HTTPException):
    return jsonify({"error": error.description}), error.code


def get_dictionary() -> Dictionary:
    global _dictionary
    if _dictionary is None:
        _dictionary = Dictionary.from_file(str(DICTIONARY_PATH))
    return _dictionary


def entry_payload(entry: DictEntry, *, complete: bool = True) -> dict:
    payload = {
        "id": str(entry.eid),
        "forms": entry.get_all(".FORM"),
        "gloss": entry.get_first(".GLOSS") or "",
        "pos": entry.get_all(".POS"),
    }
    if complete:
        payload["fields"] = [
            {
                "tag": tag,
                "label": tag.lstrip(".").replace("_", " ").title(),
                "values": entry.get_all(tag),
            }
            for tag in entry.tags()
        ]
    return payload


def _run_directory(run_id: str) -> Path:
    if not run_id.isalnum():
        abort(404)
    run_dir = RUNS / run_id
    if not run_dir.is_dir():
        abort(404, description="Run not found")
    return run_dir


def _entry_from_review(raw: dict) -> DictEntry:
    entry_id = str(raw.get("id", "")).strip()
    if not LemmaID.is_valid(entry_id):
        abort(400, description=f"Invalid lemma ID: {entry_id!r}")
    entry = DictEntry(entry_id)
    fields = raw.get("fields", [])
    if not isinstance(fields, list):
        abort(400, description="Dictionary fields must be a list")
    for field in fields:
        tag = str(field.get("tag", "")).strip().upper()
        if not re.fullmatch(r"\.[A-Z][A-Z0-9_]*", tag):
            abort(400, description=f"Invalid dictionary tag: {tag!r}")
        values = field.get("values", [])
        if not isinstance(values, list):
            abort(400, description=f"Values for {tag} must be a list")
        cleaned = [str(value).strip() for value in values]
        if tag in entry.tags():
            entry.remove(tag)
        entry.set(tag, cleaned if tag in MULTI_VALUE_FIELDS else (cleaned[0] if cleaned else ""))
    return entry


def _builtins() -> list[dict[str, str]]:
    return [
        {"id": script_id, "name": label, "source": "GUI processor"}
        for script_id, (_, label) in PROCESSORS.items()
    ]


def _script_path(script_id: str) -> Path:
    item = PROCESSORS.get(script_id)
    if item is None:
        abort(404, description="Unknown processor")
    return item[0]


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/scripts")
def scripts():
    return jsonify(_builtins())


@app.get("/api/documents")
def documents():
    xml_root = ROOT / "data" / "xml"
    groups = []
    for folder, label in (("text", "Texts under active editing"),
                          ("trees", "Uploaded syntax trees")):
        files = [
            {"id": f"{folder}/{path.name}", "name": path.name}
            for path in sorted((xml_root / folder).glob("*.xml"))
        ]
        groups.append({"id": folder, "label": label, "files": files})
    return jsonify(groups)


@app.get("/api/dictionary/search")
def dictionary_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    selected = request.args.getlist("field") or ["id", "form"]
    invalid = [field for field in selected if field != "id" and field not in DICT_SEARCH_FIELDS]
    if invalid:
        abort(400, description=f"Unknown dictionary search field: {invalid[0]}")

    needle = query.casefold()
    matches: list[tuple[int, DictEntry]] = []
    for entry in get_dictionary():
        score = 0
        values = []
        if "id" in selected:
            values.append(str(entry.eid))
        for field in selected:
            if field != "id":
                values.extend(value for tag in DICT_SEARCH_FIELDS[field]
                              for value in entry.get_all(tag))
        for value in values:
            folded = value.casefold()
            if folded == needle:
                score = max(score, 4 if value == str(entry.eid) else 3)
            elif folded.startswith(needle):
                score = max(score, 2)
            elif needle in folded:
                score = max(score, 1)
        if score:
            matches.append((score, entry))
    matches.sort(key=lambda match: (-match[0], str(match[1].eid)))
    return jsonify([entry_payload(entry, complete=False)
                    for _, entry in matches[:100]])


@app.get("/api/dictionary/<entry_id>")
def dictionary_entry(entry_id: str):
    entry = get_dictionary().get(entry_id)
    if entry is None:
        abort(404, description=f"Dictionary entry {entry_id!r} was not found")
    return jsonify(entry_payload(entry))


@app.post("/api/runs/<run_id>/dictionary/suggest-id")
def suggest_dictionary_id(run_id: str):
    run_dir = _run_directory(run_id)
    raw = request.get_json(silent=True) or {}
    form = str(raw.get("form", ""))
    dictionary = Dictionary.from_file(str(run_dir / "data" / "dict" / "dictionary.xml"))
    used = dictionary.used_numbers() | _manual_id_reservations.setdefault(run_id, set())
    for candidate in (run_dir / "output" / "dictionary_processed.xml",
                      run_dir / "output" / "dictionary.xml"):
        if candidate.exists():
            used |= Dictionary.from_file(str(candidate)).used_numbers()
            break
    generated = IDGenerator(existing=used, prefix="L", digits=6).next_id()
    _manual_id_reservations[run_id].add(generated.number)
    return jsonify({"id": str(generated), "form": form, "kana": phonemic_to_kana(form)})


@app.get("/api/runs/<run_id>/dictionary/check-id/<entry_id>")
def check_dictionary_id(run_id: str, entry_id: str):
    run_dir = _run_directory(run_id)
    if not LemmaID.is_valid(entry_id):
        return jsonify({"valid": False, "conflict": False, "message": "Use an ID such as L000001."})
    proposed = LemmaID.parse(entry_id)
    dictionary = Dictionary.from_file(str(run_dir / "data" / "dict" / "dictionary.xml"))
    conflicts = [str(entry.eid) for entry in dictionary if entry.eid.number == proposed.number]
    return jsonify({
        "valid": True,
        "conflict": bool(conflicts),
        "conflicts": conflicts,
        "message": (f"Numeric portion already used by {', '.join(conflicts)}."
                    if conflicts else "ID is available."),
    })


@app.post("/api/runs/<run_id>/finalize")
def finalize_run(run_id: str):
    run_dir = _run_directory(run_id)
    payload = request.get_json(force=True)
    reviewed_lines = payload.get("lines", [])
    reviewed_entries = payload.get("dictionary", [])
    if not isinstance(reviewed_lines, list) or not isinstance(reviewed_entries, list):
        abort(400, description="Reviewed lines and dictionary entries must be lists")

    final_dir = run_dir / "final"
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir()

    lines_by_file: dict[str, list[dict]] = {}
    for review in reviewed_lines:
        if review.get("confirmed"):
            lines_by_file.setdefault(str(review.get("file", "")), []).append(review)

    final_files = []
    for source in sorted((run_dir / "data" / "text").glob("*.xml")):
        doc = CorpusDocument.from_file(str(source))
        for review in lines_by_file.get(source.name, []):
            utterance = doc.find_utterance(str(review.get("utterance", "")))
            position = int(review.get("position", 0))
            if utterance is None or position < 1 or position > len(utterance.corpus_lines()):
                abort(400, description=f"Reviewed line no longer exists in {source.name}")
            line = utterance.corpus_lines()[position - 1]
            if review.get("before") and line.to_text() != review["before"]:
                abort(409, description=f"Reviewed line changed in {source.name}")
            lemma = str(review.get("lemma", ""))
            if not LemmaID.is_valid(lemma):
                abort(400, description=f"Invalid selected lemma ID: {lemma!r}")
            if line.is_annotated:
                line.replace_lemma(lemma)
            else:
                line.insert_lemma(lemma)
        destination = final_dir / source.name
        doc.to_file(str(destination))
        final_files.append(source.name)

    dictionary = Dictionary.from_file(str(run_dir / "data" / "dict" / "dictionary.xml"))
    used_numbers = dictionary.used_numbers()
    for raw in reviewed_entries:
        if not raw.get("confirmed"):
            continue
        entry = _entry_from_review(raw)
        existing = dictionary.get(entry.eid)
        category = raw.get("category", "added")
        if category == "added" and entry.eid.number in used_numbers:
            conflicts = [str(item.eid) for item in dictionary if item.eid.number == entry.eid.number]
            abort(409, description=f"Numeric ID conflict for {entry.eid}: {', '.join(conflicts)}")
        dictionary.add(entry, allow_update=existing is not None and category != "added")
        used_numbers.add(entry.eid.number)
    dictionary.to_file(str(final_dir / "dictionary.xml"))
    final_files.append("dictionary.xml")

    manifest = {
        "confirmed_lines": sum(bool(item.get("confirmed")) for item in reviewed_lines),
        "confirmed_dictionary_entries": sum(bool(item.get("confirmed")) for item in reviewed_entries),
        "files": final_files,
    }
    (final_dir / "review_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    final_files.append("review_manifest.json")
    return jsonify(manifest | {"files": final_files})


@app.get("/api/scripts/<script_id>/settings")
def script_settings(script_id: str):
    script = _script_path(script_id)
    proc = subprocess.run(
        [sys.executable, str(HERE / "worker.py"), "inspect", str(script)],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    if proc.returncode:
        return jsonify({"error": proc.stderr or proc.stdout}), 400
    return jsonify(json.loads(proc.stdout))


@app.post("/api/run")
def run_script():
    payload = request.get_json(force=True)
    script = _script_path(str(payload.get("script", "")))
    settings = payload.get("settings", {})
    if not isinstance(settings, dict):
        abort(400, description="settings must be an object")

    xml_root = ROOT / "data" / "xml"
    available = {
        f"{folder}/{path.name}": path
        for folder in ("text", "trees")
        for path in (xml_root / folder).glob("*.xml")
    }
    requested_files = payload.get("files")
    if requested_files is None:
        selected = sorted(available)
    elif not isinstance(requested_files, list):
        abort(400, description="files must be a list")
    else:
        selected = list(dict.fromkeys(str(name) for name in requested_files))
        if not selected:
            abort(400, description="Select at least one XML file")
        invalid = [name for name in selected if name not in available]
        if invalid:
            abort(400, description=f"Unknown XML file: {invalid[0]}")

    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS / run_id
    (run_dir / "data").mkdir(parents=True)
    run_text = run_dir / "data" / "text"
    run_text.mkdir()
    for name in selected:
        shutil.copy2(available[name], run_text / Path(name).name)
    shutil.copytree(ROOT / "data" / "xml" / "dict", run_dir / "data" / "dict")
    (run_dir / "output").mkdir()
    config = run_dir / "config.json"
    config.write_text(json.dumps(settings), encoding="utf-8")

    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / "worker.py"), "run", str(script),
             str(run_dir), str(config)],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        return jsonify({"error": "Processor exceeded the 120 second limit.",
                        "console": (exc.stdout or "")}), 408

    result_file = run_dir / "result.json"
    if not result_file.exists():
        return jsonify({"error": "Processor failed", "console": proc.stdout,
                        "details": proc.stderr}), 400
    result = json.loads(result_file.read_text(encoding="utf-8"))
    result["run_id"] = run_id
    result["processed_files"] = selected
    result["console"] = proc.stdout
    if proc.stderr:
        result["warnings"] = proc.stderr
    return jsonify(result), (200 if proc.returncode == 0 else 400)


@app.get("/api/runs/<run_id>/files/<path:name>")
def run_file(run_id: str, name: str):
    if not run_id.isalnum():
        abort(404)
    base = (RUNS / run_id / "output").resolve()
    path = (base / name).resolve()
    if base not in path.parents or not path.is_file():
        abort(404)
    return path.read_text(encoding="utf-8", errors="replace"), 200, {
        "Content-Type": "text/plain; charset=utf-8"
    }


@app.get("/api/runs/<run_id>/final/<path:name>")
def final_file(run_id: str, name: str):
    run_dir = _run_directory(run_id)
    base = (run_dir / "final").resolve()
    path = (base / name).resolve()
    if base not in path.parents or not path.is_file():
        abort(404)
    return path.read_text(encoding="utf-8", errors="replace"), 200, {
        "Content-Type": "text/plain; charset=utf-8"
    }


if __name__ == "__main__":
    RUNS.mkdir(exist_ok=True)
    app.run(debug=True, port=5001)
