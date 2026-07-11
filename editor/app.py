import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flask import Flask, abort, jsonify, render_template, request

from coj.core.corpus import CorpusDocument
from coj.core.dictionary import Dictionary
from coj.xml.corpus_xml import utterance_to_tree_str

app = Flask(__name__)

DATA_XML  = Path(__file__).parent.parent / "data" / "xml"
DICT_PATH = DATA_XML / "dict" / "dictionary.xml"

_dict: Dictionary | None = None
_docs: dict[str, CorpusDocument] = {}

_ID_RE = re.compile(r"^[A-Z]\d{6}[a-z]?$")

_TEXT_DIR  = DATA_XML / "text"
_TREES_DIR = DATA_XML / "trees"


def get_dict() -> Dictionary:
    global _dict
    if _dict is None:
        _dict = Dictionary.from_file(str(DICT_PATH))
    return _dict


def get_doc(doc_id: str) -> CorpusDocument:
    if doc_id not in _docs:
        for directory in (_TEXT_DIR, _TREES_DIR):
            path = directory / f"{doc_id}.xml"
            if path.exists():
                _docs[doc_id] = CorpusDocument.from_file(str(path))
                break
        else:
            abort(404, description=f"Document '{doc_id}' not found")
    return _docs[doc_id]


def _list_doc_ids() -> list[str]:
    ids = []
    for directory in (_TEXT_DIR, _TREES_DIR):
        for p in sorted(directory.glob("*.xml")):
            ids.append(p.stem)
    return ids


def _sort_key(doc_id: str) -> tuple:
    m = re.match(r"^([A-Z]+)_?(\d*)$", doc_id)
    if m:
        return (m.group(1), int(m.group(2)) if m.group(2) else 0)
    return (doc_id, 0)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/documents")
def list_documents():
    result = []
    for doc_id in sorted(_list_doc_ids(), key=_sort_key):
        doc = get_doc(doc_id)
        result.append({
            "id":              doc_id,
            "label":           doc_id.replace("_", " "),
            "utterance_count": len(doc.utterances),
        })
    return jsonify(result)


@app.route("/api/documents/<doc_id>")
def document_index(doc_id: str):
    doc = get_doc(doc_id)
    return jsonify([
        {"sentence_id": utt.sentence_id or "", "header": utt.header.raw if utt.header else ""}
        for utt in doc.utterances
    ])


@app.route("/api/utterances/<doc_id>/<path:sentence_id>")
def utterance_detail(doc_id: str, sentence_id: str):
    doc = get_doc(doc_id)
    utt = doc.find_utterance(sentence_id)
    if utt is None:
        abort(404, description=f"Utterance '{sentence_id}' not found in '{doc_id}'")

    lines = []
    for cl in utt.corpus_lines():
        lines.append({
            "fields": cl.fields,
            "form":   cl.word_form,
            "phon":   cl.phon_tag,
            "lemma":  str(cl.lemma_id) if cl.lemma_id else None,
        })

    return jsonify({
        "sentence_id": utt.sentence_id or "",
        "header":      utt.header.raw if utt.header else "",
        "tree":        utterance_to_tree_str(utt),
        "lines":       lines,
    })


@app.route("/api/dictionary")
def search_dictionary():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    d = get_dict()
    hits: list = []

    if _ID_RE.match(q.upper()):
        entry = d.get(q.upper())
        if entry:
            hits = [entry]
    else:
        seen: set[str] = set()
        for entry in d.find_by_form(q):
            if str(entry.eid) not in seen:
                hits.append(entry)
                seen.add(str(entry.eid))
        for entry in d.find_by_gloss(q, exact=False):
            if str(entry.eid) not in seen:
                hits.append(entry)
                seen.add(str(entry.eid))

    hits = hits[:50]
    return jsonify([
        {
            "id":    str(e.eid),
            "gloss": e.get_first(".GLOSS") or "",
            "forms": e.get_all(".FORM"),
            "pos":   e.get_first(".POS") or "",
        }
        for e in hits
    ])


@app.route("/api/dictionary/<entry_id>")
def dictionary_entry(entry_id: str):
    d = get_dict()
    entry = d.get(entry_id)
    if entry is None:
        abort(404, description=f"Entry '{entry_id}' not found")

    fields = []
    for tag in entry.tags():
        value = entry.get(tag)
        if isinstance(value, list):
            for v in value:
                fields.append({"tag": tag, "value": v})
        else:
            fields.append({"tag": tag, "value": value or ""})

    return jsonify({"id": str(entry.eid), "fields": fields})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
