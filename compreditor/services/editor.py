from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from compreditor.services.xml_tools import (
    TAG_RE,
    element_at,
    parent_at,
    payload_to_element,
)

ATTRIBUTE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")


def _clean_attributes(raw) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("Attributes must be an object")
    result = {}
    for key, value in raw.items():
        name = str(key).strip()
        if not ATTRIBUTE_RE.fullmatch(name):
            raise ValueError(f"Invalid attribute name: {name!r}")
        result[name] = str(value)
    return result


def apply_operation(root: ET.Element, payload: dict) -> str:
    operation = str(payload.get("operation", "")).lower()
    path = str(payload.get("path", ""))

    if operation == "update":
        elem = element_at(root, path)
        tag = str(payload.get("tag", elem.tag)).strip()
        if not TAG_RE.fullmatch(tag):
            raise ValueError(f"Invalid XML tag: {tag!r}")
        elem.tag = tag
        if "attributes" in payload:
            elem.attrib.clear()
            elem.attrib.update(_clean_attributes(payload["attributes"]))
        if "text" in payload:
            elem.text = str(payload["text"]) or None
        return path

    if operation == "add":
        parent = element_at(root, path)
        tag = str(payload.get("tag", "branch")).strip()
        if not TAG_RE.fullmatch(tag):
            raise ValueError(f"Invalid XML tag: {tag!r}")
        child = ET.Element(tag, _clean_attributes(payload.get("attributes", {})))
        child.text = str(payload.get("text", "")) or None
        index = payload.get("index")
        if index is None:
            parent.append(child)
            index = len(parent) - 1
        else:
            index = max(0, min(int(index), len(parent)))
            parent.insert(index, child)
        return f"{path}.{index}" if path else str(index)

    if operation == "paste":
        parent = element_at(root, path)
        child = payload_to_element(payload.get("node", {}))
        parent.append(child)
        index = len(parent) - 1
        return f"{path}.{index}" if path else str(index)

    if operation == "delete":
        parent, index = parent_at(root, path)
        if index >= len(parent):
            raise IndexError("Node path does not exist")
        parent.remove(list(parent)[index])
        return ""

    if operation == "move":
        parent, index = parent_at(root, path)
        direction = str(payload.get("direction", "up"))
        target_index = index - 1 if direction == "up" else index + 1
        if target_index < 0 or target_index >= len(parent):
            return path
        children = list(parent)
        node = children[index]
        parent.remove(node)
        parent.insert(target_index, node)
        prefix = path.rsplit(".", 1)[0] if "." in path else ""
        return f"{prefix}.{target_index}" if prefix else str(target_index)

    if operation == "reparent":
        source_parent, source_index = parent_at(root, path)
        node = list(source_parent)[source_index]
        target_path = str(payload.get("target_path", ""))
        if target_path == path or target_path.startswith(path + "."):
            raise ValueError("A node cannot be moved inside itself")
        target = element_at(root, target_path)
        source_parent.remove(node)
        target.append(node)
        index = len(target) - 1
        return f"{target_path}.{index}" if target_path else str(index)

    raise ValueError(f"Unknown edit operation: {operation!r}")


def update_words(root: ET.Element, rows: list[dict]) -> None:
    for row in rows:
        elem = element_at(root, str(row.get("path", "")))
        tag = str(row.get("tag", elem.tag)).strip()
        if not TAG_RE.fullmatch(tag):
            raise ValueError(f"Invalid XML tag: {tag!r}")
        elem.tag = tag
        if "text" in row:
            elem.text = str(row.get("text", "")) or None
        for attribute in ("form", "phon", "lemma"):
            value = str(row.get(attribute, "")).strip()
            if value:
                elem.set(attribute, value)
            else:
                elem.attrib.pop(attribute, None)
