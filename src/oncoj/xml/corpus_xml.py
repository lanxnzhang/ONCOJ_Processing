"""
XML serialisation and deserialisation for ONCOJ corpus documents.

All heavy lifting lives in ``oncoj.core.corpus``; this module is thin wrappers
that expose a stable public API.

Public API
----------
corpus_to_xml(doc)              → XML string for a full CorpusDocument
corpus_to_xml_file(doc, path)
utterance_to_xml(utt)           → XML string for one Utterance
utterance_to_tree_str(utt)      → ASCII tree string for one Utterance

corpus_from_xml(xml_str)        → CorpusDocument
corpus_from_xml_file(path)      → CorpusDocument
utterance_from_xml(xml_str)     → Utterance
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET

from oncoj.core.corpus import (
    CorpusDocument,
    Utterance,
    _utterance_to_elem,
    _utterance_from_elem,
)


# ── Public API ─────────────────────────────────────────────────────────────────


def corpus_to_xml(doc: CorpusDocument) -> str:
    """Serialise a CorpusDocument to an XML string."""
    root = doc._get_doc_elem()
    ET.indent(root, space="  ")
    buf = io.BytesIO()
    ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


def corpus_to_xml_file(doc: CorpusDocument, path: str) -> None:
    """Write corpus XML to *path*."""
    doc.to_file(path if path.endswith(".xml") else path + ".xml")


def utterance_to_xml(utt: Utterance) -> str:
    """Serialise a single Utterance to an XML string."""
    elem = _utterance_to_elem(utt)
    ET.indent(elem, space="  ")
    return ET.tostring(elem, encoding="unicode")


def corpus_from_xml(xml_str: str) -> CorpusDocument:
    """Parse an XML string back into a CorpusDocument."""
    root = ET.fromstring(xml_str)
    return CorpusDocument._from_elem(root)


def corpus_from_xml_file(path: str) -> CorpusDocument:
    """Read an XML file and return a CorpusDocument."""
    return CorpusDocument.from_file(path)


def utterance_from_xml(xml_str: str) -> Utterance:
    """Parse an XML string containing a single <block> element into an Utterance."""
    elem = ET.fromstring(xml_str)
    return _utterance_from_elem(elem)


# ── ASCII tree rendering ───────────────────────────────────────────────────────


def _elem_to_tree_lines(
    elem: ET.Element,
    prefix: str = "",
    is_last: bool = True,
) -> list[str]:
    """Recursively render an XML element as ASCII tree lines."""
    connector = "└── " if is_last else "├── "
    children = list(elem)

    if not children:
        parts: list[str] = []
        idx = elem.get("index")
        if idx:
            parts.append(f"index={idx}")
        for attr in ("lemma", "phon", "form"):
            val = elem.get(attr)
            if val:
                parts.append(f"{attr}={val}")
        attr_str = "  [" + "  ".join(parts) + "]" if parts else ""
        return [prefix + connector + elem.tag + attr_str]

    lines = [prefix + connector + elem.tag]
    child_prefix = prefix + ("    " if is_last else "│   ")

    comment_elems = [c for c in children if c.tag == "comment"]
    tree_elems = [c for c in children if c.tag != "comment"]
    all_ordered = comment_elems + tree_elems

    for i, child in enumerate(all_ordered):
        child_is_last = (i == len(all_ordered) - 1)
        if child.tag == "comment":
            conn2 = "└── " if child_is_last else "├── "
            lines.append(child_prefix + conn2 + "# " + (child.get("raw") or ""))
        else:
            lines.extend(_elem_to_tree_lines(child, child_prefix, child_is_last))

    return lines


def utterance_to_tree_str(utt: Utterance) -> str:
    """Render an Utterance as a human-readable ASCII tree."""
    if utt._block_elem is not None:
        elem = utt._block_elem
        sid = elem.get("id") or ""
        hdr = elem.get("header") or ""
    else:
        elem = _utterance_to_elem(utt)
        sid = utt.sentence_id or ""
        hdr = utt.header.raw if utt.header else ""

    header_line = f"block  id={sid}  {hdr}" if sid else f"block  {hdr}"
    lines = [header_line]
    children = list(elem)
    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        if child.tag == "comment":
            connector = "└── " if is_last else "├── "
            lines.append(connector + "# " + (child.get("raw") or ""))
        else:
            lines.extend(_elem_to_tree_lines(child, "", is_last))
    return "\n".join(lines)
