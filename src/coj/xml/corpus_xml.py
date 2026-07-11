"""
XML serialisation and deserialisation for ONCOJ corpus documents.

All heavy lifting lives in ``coj.core.corpus``; this module is thin wrappers
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

from coj.core.corpus import (
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


def utterance_to_tree_str(utt: Utterance) -> str:
    """Render an Utterance as a human-readable ASCII tree."""
    from coj.visual.ascii_tree import ascii_tree
    return ascii_tree(utt)
