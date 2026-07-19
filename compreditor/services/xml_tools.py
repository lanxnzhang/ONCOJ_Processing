from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from typing import Iterable

TAG_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
METADATA_TAGS = {"roundtrip-data", "comment", "raw-text", "sentence", "kanji", "transcription"}


def parse_path(value: str | None) -> tuple[int, ...]:
    if value in (None, ""):
        return ()
    try:
        path = tuple(int(item) for item in value.split("."))
    except ValueError as exc:
        raise ValueError("Node path must contain dot-separated indexes") from exc
    if any(index < 0 for index in path):
        raise ValueError("Node indexes cannot be negative")
    return path


def format_path(path: Iterable[int]) -> str:
    return ".".join(str(item) for item in path)


def element_at(root: ET.Element, path_value: str | None) -> ET.Element:
    current = root
    for index in parse_path(path_value):
        children = list(current)
        if index >= len(children):
            raise IndexError("Node path does not exist")
        current = children[index]
    return current


def parent_at(root: ET.Element, path_value: str) -> tuple[ET.Element, int]:
    path = parse_path(path_value)
    if not path:
        raise ValueError("The document root has no parent")
    return element_at(root, format_path(path[:-1])), path[-1]


def node_payload(elem: ET.Element, path: tuple[int, ...] = ()) -> dict:
    children = [
        node_payload(child, path + (index,))
        for index, child in enumerate(list(elem))
    ]
    layer = (
        "document" if not path else
        "sentence" if elem.tag == "block" else
        "annotation" if elem.tag in METADATA_TAGS else
        "word" if elem.get("form") is not None else
        "branch"
    )
    label = elem.get("form") or elem.get("id") or elem.get("raw") or elem.tag
    return {
        "path": format_path(path),
        "tag": elem.tag,
        "attributes": dict(elem.attrib),
        "text": (elem.text or "").strip(),
        "label": label,
        "layer": layer,
        "leaf": not children,
        "children": children,
    }


def payload_to_element(raw: dict) -> ET.Element:
    tag = str(raw.get("tag", "")).strip()
    if not TAG_RE.fullmatch(tag):
        raise ValueError(f"Invalid XML tag: {tag!r}")
    attributes = raw.get("attributes", {})
    if not isinstance(attributes, dict):
        raise ValueError("Node attributes must be an object")
    elem = ET.Element(tag, {str(key): str(value) for key, value in attributes.items()})
    elem.text = str(raw.get("text", "")) or None
    children = raw.get("children", [])
    if not isinstance(children, list):
        raise ValueError("Node children must be a list")
    for child in children:
        elem.append(payload_to_element(child))
    return elem


def clone_payload(elem: ET.Element) -> dict:
    return node_payload(deepcopy(elem))


def sentence_for_path(root: ET.Element, path_value: str | None) -> tuple[str, str]:
    path = parse_path(path_value)
    current = root
    for index in path:
        if current.tag == "block":
            return current.get("id", ""), current.get("header", "")
        current = list(current)[index]
    if current.tag == "block":
        return current.get("id", ""), current.get("header", "")
    return "", ""


def iter_with_paths(root: ET.Element):
    stack = [(root, ())]
    while stack:
        elem, path = stack.pop()
        yield elem, format_path(path)
        children = list(elem)
        for index in range(len(children) - 1, -1, -1):
            stack.append((children[index], path + (index,)))


def word_rows(root: ET.Element) -> list[dict]:
    rows = []
    for elem, path in iter_with_paths(root):
        if elem.get("form") is not None:
            sentence_id, sentence = sentence_for_path(root, path)
            rows.append({
                "path": path,
                "tag": elem.tag,
                "form": elem.get("form", ""),
                "phon": elem.get("phon", ""),
                "lemma": elem.get("lemma", ""),
                "sentence_id": sentence_id,
                "sentence": sentence,
                "attributes": dict(elem.attrib),
            })
    return rows
