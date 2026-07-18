from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter

from compreditor.services.xml_tools import iter_with_paths

LEMMA_RE = re.compile(r"^[A-Za-z]+\d{6}[a-z]*$")


def problem(severity: str, code: str, message: str, path: str = "") -> dict:
    return {"severity": severity, "code": code, "message": message, "path": path}


def validate_document(root: ET.Element, dictionary_ids: set[str] | None = None) -> list[dict]:
    problems = []
    dictionary_ids = dictionary_ids or set()
    if root.tag != "document":
        problems.append(problem("error", "root", "Root element must be <document>."))
    if not root.get("filename"):
        problems.append(problem("warning", "filename", "Document is missing its filename attribute."))

    sentence_ids = []
    for elem, path in iter_with_paths(root):
        depth = 0 if not path else len(path.split("."))
        if depth == 1 and elem.tag not in ("block", "comment"):
            problems.append(problem("error", "wrong-location", f"<{elem.tag}> must be inside a sentence block.", path))
        if elem.tag == "block":
            if depth != 1:
                problems.append(problem("error", "wrong-location", "Sentence blocks must be direct document children.", path))
            sentence_id = elem.get("id", "")
            if not sentence_id:
                problems.append(problem("error", "sentence-id", "Sentence is missing an id.", path))
            else:
                sentence_ids.append((sentence_id, path))
            if not elem.get("header"):
                problems.append(problem("warning", "header", "Sentence has no transcription header.", path))
        elif elem is not root and elem.tag != "comment" and len(elem) == 0:
            if "form" not in elem.attrib:
                problems.append(problem("error", "missing-form", "Leaf is missing a form attribute.", path))
            if "phon" not in elem.attrib:
                problems.append(problem("warning", "missing-phon", "Leaf is missing a phon attribute.", path))

        lemma = elem.get("lemma")
        if lemma:
            if not LEMMA_RE.fullmatch(lemma):
                problems.append(problem("error", "lemma-format", f"Invalid lemma ID {lemma!r}.", path))
            elif dictionary_ids and lemma not in dictionary_ids:
                problems.append(problem("warning", "unknown-lemma", f"Lemma {lemma} is absent from the dictionary.", path))

        if elem.tag == "comment" and elem.get("raw") is None:
            problems.append(problem("warning", "comment-raw", "Comment is missing its raw text.", path))
        if elem.tag == "comment" and depth == 1:
            problems.append(problem("warning", "wrong-location", "Document comments normally belong inside a sentence block.", path))

    counts = Counter(value for value, _ in sentence_ids)
    for value, path in sentence_ids:
        if counts[value] > 1:
            problems.append(problem("error", "duplicate-sentence", f"Duplicate sentence ID {value}.", path))
    return problems


def validate_dictionary_xml(root: ET.Element) -> list[dict]:
    problems = []
    if root.tag != "dictionary":
        return [problem("error", "dictionary-root", "Dictionary root must be <dictionary>.")]
    ids = [entry.get("id", "") for entry in root if entry.tag == "entry"]
    counts = Counter(ids)
    for index, entry in enumerate(root):
        if entry.tag != "entry":
            problems.append(problem("error", "dictionary-child", "Dictionary children must be entries.", str(index)))
            continue
        entry_id = entry.get("id", "")
        if not entry_id:
            problems.append(problem("error", "dictionary-id", "Dictionary entry is missing an ID.", str(index)))
        elif counts[entry_id] > 1:
            problems.append(problem("error", "duplicate-dictionary-id", f"Duplicate dictionary ID {entry_id}.", str(index)))
        if entry.find("forms") is None:
            problems.append(problem("warning", "dictionary-form", f"{entry_id or 'Entry'} has no forms container.", str(index)))
    return problems
