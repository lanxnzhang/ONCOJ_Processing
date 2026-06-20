"""
Corpus model for ONCOJ text files.

Text format (one sentence / utterance)
---------------------------------------
=N(" kamu nusi papuri ra moromoro ... ")        ← utterance header
IP-MAT,IP-ARG,0@神主祝部等諸聞食登,*             ← comment line (tag ends with *)
IP-MAT,IP-ARG,C-NP,N,N,LOG,kamu                ← tree path (corpus) line
IP-MAT,IP-ARG,C-NP,N,N,L000006a,LOG,nu         ← tree path with lemma ID
ID,1_EN_01                                      ← sentence ID line
                                                ← blank line separating utterances

A corpus file is a sequence of utterances separated by blank lines.
The corpus can be loaded from and saved to both .txt (comma-path) and .xml format.

Classes
-------
CorpusLine   — one annotated tree-path line (mutable); dual-mode: field-list or XML-backed
CommentLine  — one non-tree line (header / comment / ID / special)
Utterance    — one sentence block: header + lines + sentence ID
CorpusDocument — a whole corpus file
"""

from __future__ import annotations

import io
import os
import re
import xml.etree.ElementTree as ET
from typing import Iterator

from oncoj.core.lemma_id import LemmaID
from oncoj.core.tags import PHON_TAGS, strip_disambig

# ── regexes ───────────────────────────────────────────────────────────────────

_LEMMA_RE    = re.compile(r'^[A-Za-z]\d+[a-z]*$')
_SYNCTAG_RE  = re.compile(r'^[A-Z][A-Z0-9\-]*(?:;@\d+)?$')   # e.g. NP, VB-STM, N;@2
# Root-level node names that begin with lowercase (multi-sentence, multi-clause)
_MULTIROOT_RE = re.compile(r'^multi-\w+')
_WORDFORM_RE = re.compile(r'^[A-Za-z]+$')

# Header pattern: =N(" ... ")  or  =N(...)
_HEADER_RE      = re.compile(r'^=\w+\(')
# Captures the inner word string from  =N(" words ")  or  =N("words")
_HEADER_INNER_RE = re.compile(r'^=\w+\(\s*"?\s*(.*?)\s*"?\s*\)\s*$')
# Sentence ID line: ID,<text>
_ID_LINE_RE  = re.compile(r'^ID,')


# ══════════════════════════════════════════════════════════════════════════════
#  CorpusLine
# ══════════════════════════════════════════════════════════════════════════════

class CorpusLine:
    """
    One corpus (tree-path) line.

    Dual-mode:
    - **Field-list mode** (default): backed by a flat ``list[str]``, identical
      to the original implementation.  Use ``CorpusLine(fields)`` or
      ``CorpusLine.parse(line)``.
    - **XML mode**: backed by a leaf ``ET.Element`` plus a list of ancestor
      elements from the syntactic-tree root down to the leaf's parent.  Use
      ``CorpusLine._from_elem(leaf_elem, ancestors)``.  All property reads and
      mutation methods propagate directly to the underlying XML attributes so
      that mutations are instantly visible in the enclosing ``CorpusDocument``
      element tree.

    The public API (``word_form``, ``phon_tag``, ``lemma_id``, ``synt_path``,
    ``insert_lemma``, ``replace_lemma``, ``remove_lemma``, ``fields``) behaves
    identically in both modes.
    """

    def __init__(self, fields: list[str]) -> None:
        self._fields_storage: list[str] | None = list(fields)
        self._leaf_elem: ET.Element | None = None
        self._ancestors: list[ET.Element] = []

    @classmethod
    def _from_elem(cls, leaf_elem: ET.Element,
                   ancestors: list[ET.Element]) -> "CorpusLine":
        """Create an XML-backed CorpusLine wrapping *leaf_elem*."""
        obj: CorpusLine = cls.__new__(cls)
        obj._fields_storage = None
        obj._leaf_elem = leaf_elem
        obj._ancestors = list(ancestors)
        return obj

    # ── parsing ───────────────────────────────────────────────────────────────

    @classmethod
    def parse(cls, line: str) -> "CorpusLine":
        fields = line.rstrip("\r\n").split(",")
        return cls(fields)

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_text(self) -> str:
        if self._fields_storage is not None:
            return ",".join(self._fields_storage)
        # XML mode: reconstruct comma-path from ancestors + leaf element
        parts: list[str] = []
        for anc in self._ancestors:
            raw_tag = anc.get("raw_tag") or anc.tag
            idx = anc.get("index")
            if idx and not anc.get("inferred_index"):
                raw_tag = f"{raw_tag};@{idx}"
            parts.append(raw_tag)
            emb_lemma = anc.get("lemma")
            if emb_lemma:
                parts.append(emb_lemma)
        # Leaf element tag
        leaf_raw_tag = self._leaf_elem.get("raw_tag") or self._leaf_elem.tag
        leaf_idx = self._leaf_elem.get("index")
        if leaf_idx and not self._leaf_elem.get("inferred_index"):
            leaf_raw_tag = f"{leaf_raw_tag};@{leaf_idx}"
        parts.append(leaf_raw_tag)
        # Leaf annotations
        leaf_lemma = self._leaf_elem.get("lemma")
        if leaf_lemma:
            parts.append(leaf_lemma)
        phon = self._leaf_elem.get("phon") or ""
        if phon:
            parts.append(phon)
        form = self._leaf_elem.get("form") or ""
        if form:
            parts.append(form)
        return ",".join(parts)

    def __str__(self) -> str:
        return self.to_text()

    def __repr__(self) -> str:
        return f"CorpusLine({self.fields!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CorpusLine):
            return self.fields == other.fields
        return NotImplemented

    # ── field access (read-only property in XML mode) ─────────────────────────

    @property
    def fields(self) -> list[str]:
        """The full field list. Mutable in field-list mode; computed in XML mode."""
        if self._fields_storage is not None:
            return self._fields_storage
        return self.to_text().split(",")

    # ── field inspection ──────────────────────────────────────────────────────

    @property
    def word_form(self) -> "str | None":
        """Last field if it is a pure-alphabetic word form, else None."""
        if self._leaf_elem is not None:
            form = self._leaf_elem.get("form") or ""
            return form if form else None
        last = self._fields_storage[-1] if self._fields_storage else ""
        return last if _WORDFORM_RE.match(last) else None

    @property
    def phon_tag(self) -> "str | None":
        """
        The writing-mode tag (LOG, PHON, NLOG, …) if the line has a word form.
        The raw tag (with any ;@N suffix) is returned; use ``strip_disambig``
        if you need the bare name.
        """
        if self._leaf_elem is not None:
            phon = self._leaf_elem.get("phon") or ""
            return phon if phon else None
        if self.word_form is None or len(self._fields_storage) < 2:
            return None
        tag = self._fields_storage[-2]
        return tag if strip_disambig(tag) in PHON_TAGS else None

    @property
    def lemma_id(self) -> "LemmaID | None":
        """The lemma ID if present, else None."""
        if self._leaf_elem is not None:
            lemma_str = self._leaf_elem.get("lemma")
            if lemma_str and _LEMMA_RE.match(lemma_str):
                return LemmaID.parse(lemma_str)
            return None
        if self.word_form is None or len(self._fields_storage) < 3:
            return None
        candidate = self._fields_storage[-3]
        if _LEMMA_RE.match(candidate):
            return LemmaID.parse(candidate)
        return None

    @property
    def synt_path(self) -> list[str]:
        """
        The syntactic path fields — everything before the lemma ID (or before
        the phon tag if no lemma ID is present).  Includes the leaf syntactic
        tag as the last element.  Does NOT include lemma, phon, or word form.
        """
        if self._leaf_elem is not None:
            parts: list[str] = []
            for anc in self._ancestors:
                raw_tag = anc.get("raw_tag") or anc.tag
                idx = anc.get("index")
                if idx and not anc.get("inferred_index"):
                    raw_tag = f"{raw_tag};@{idx}"
                parts.append(raw_tag)
                emb_lemma = anc.get("lemma")
                if emb_lemma:
                    parts.append(emb_lemma)
            leaf_raw_tag = self._leaf_elem.get("raw_tag") or self._leaf_elem.tag
            leaf_idx = self._leaf_elem.get("index")
            if leaf_idx and not self._leaf_elem.get("inferred_index"):
                leaf_raw_tag = f"{leaf_raw_tag};@{leaf_idx}"
            parts.append(leaf_raw_tag)
            return parts
        # Field-list mode
        if self.word_form is None:
            return list(self._fields_storage)
        end = -2   # before phon_tag and word_form
        if self.lemma_id is not None:
            end = -3
        return self._fields_storage[:end] if end < 0 else []

    @property
    def is_annotated(self) -> bool:
        """True if a lemma ID is already present."""
        return self.lemma_id is not None

    @property
    def is_annotatable(self) -> bool:
        """True if the line has a word form and is not yet annotated."""
        return self.word_form is not None and not self.is_annotated

    def preceding_synt_tag(self) -> "str | None":
        """Return the syntactic tag immediately before the lemma-ID slot."""
        path = self.synt_path
        return path[-1] if path else None

    # ── mutation ──────────────────────────────────────────────────────────────

    def insert_lemma(self, lemma_id: "str | LemmaID") -> None:
        """
        Insert *lemma_id* into the lemma-ID slot.
        Raises ``ValueError`` if already annotated or line has no word form.
        """
        if self._leaf_elem is not None:
            if self.word_form is None:
                raise ValueError("Cannot annotate a line with no word form")
            if self.is_annotated:
                raise ValueError(f"Line already annotated with {self.lemma_id}")
            self._leaf_elem.set("lemma", str(lemma_id))
            return
        if self.word_form is None:
            raise ValueError("Cannot annotate a line with no word form")
        if self.is_annotated:
            raise ValueError(f"Line already annotated with {self.lemma_id}")
        insert_at = len(self._fields_storage) - 2
        self._fields_storage.insert(insert_at, str(lemma_id))

    def replace_lemma(self, lemma_id: "str | LemmaID") -> None:
        """Replace an existing lemma ID in-place."""
        if self._leaf_elem is not None:
            if not self.is_annotated:
                raise ValueError("Line has no lemma ID to replace")
            self._leaf_elem.set("lemma", str(lemma_id))
            return
        if not self.is_annotated:
            raise ValueError("Line has no lemma ID to replace")
        self._fields_storage[len(self._fields_storage) - 3] = str(lemma_id)

    def remove_lemma(self) -> "LemmaID | None":
        """Remove and return the lemma ID. Returns None if not annotated."""
        if self._leaf_elem is not None:
            lemma_str = self._leaf_elem.get("lemma")
            if not lemma_str:
                return None
            del self._leaf_elem.attrib["lemma"]
            return LemmaID.parse(lemma_str)
        if not self.is_annotated:
            return None
        idx = len(self._fields_storage) - 3
        old = LemmaID.parse(self._fields_storage[idx])
        del self._fields_storage[idx]
        return old

    # ── querying helpers ──────────────────────────────────────────────────────

    def synt_tag_at(self, offset_from_end: int) -> "str | None":
        """Return the field at *offset_from_end* from end (0 = last)."""
        flds = self.fields
        idx = len(flds) - 1 - offset_from_end
        return flds[idx] if 0 <= idx < len(flds) else None

    def all_lemma_ids(self) -> list[LemmaID]:
        """Return all LemmaID-shaped tokens anywhere in the line."""
        return [LemmaID.parse(f) for f in self.fields if _LEMMA_RE.match(f)]


# ══════════════════════════════════════════════════════════════════════════════
#  CommentLine
# ══════════════════════════════════════════════════════════════════════════════

class CommentLine:
    """
    A non-tree line in a corpus file: utterance headers, inline comments
    (``0@…,*``), sentence ID lines (``ID,…``), or any other raw text.
    """

    def __init__(self, raw: str) -> None:
        self.raw: str = raw.rstrip("\r\n")

    @classmethod
    def parse(cls, line: str) -> "CommentLine":
        return cls(line)

    def to_text(self) -> str:
        return self.raw

    def __str__(self) -> str:
        return self.raw

    def __repr__(self) -> str:
        return f"CommentLine({self.raw!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CommentLine):
            return self.raw == other.raw
        return NotImplemented

    @property
    def is_header(self) -> bool:
        return bool(_HEADER_RE.match(self.raw))

    @property
    def is_id_line(self) -> bool:
        return bool(_ID_LINE_RE.match(self.raw))

    @property
    def sentence_id(self) -> "str | None":
        """The sentence ID string (e.g. '1_EN_01') if this is an ID line."""
        if self.is_id_line:
            return self.raw.split(",", 1)[1].strip()
        return None

    @property
    def is_inline_comment(self) -> bool:
        """True for lines like ``IP-MAT,0@神主祝部等,*``."""
        return self.raw.endswith(",*") and not self.is_header


# ══════════════════════════════════════════════════════════════════════════════
#  Utterance
# ══════════════════════════════════════════════════════════════════════════════

# A line in an utterance is either a CorpusLine or a CommentLine
AnyLine = "CorpusLine | CommentLine"


class Utterance:
    """
    One sentence block: a header, zero or more tree/comment lines, and
    an optional sentence-ID line.

    Dual-mode (mirrors ``CorpusLine``):
    - **Field-list mode**: ``self.lines`` holds a flat list of ``CorpusLine`` /
      ``CommentLine`` objects.  Use ``Utterance([...])`` or ``from_lines()``.
    - **XML mode**: ``self._block_elem`` is a ``<block>`` ET.Element.  Use
      ``Utterance._from_elem(block_elem)``.  All accessors walk the element
      tree on demand; mutations to corpus lines propagate instantly because
      they operate on the shared elements.
    """

    def __init__(self, lines: "list[AnyLine] | None" = None) -> None:
        self._lines_storage: list[AnyLine] = list(lines) if lines else []
        self._block_elem: ET.Element | None = None

    @classmethod
    def _from_elem(cls, block_elem: ET.Element) -> "Utterance":
        """Create an XML-backed Utterance wrapping *block_elem*."""
        obj: Utterance = cls.__new__(cls)
        obj._lines_storage = []
        obj._block_elem = block_elem
        return obj

    # ── parsing ───────────────────────────────────────────────────────────────

    @classmethod
    def from_lines(cls, raw_lines: list[str]) -> "Utterance":
        """Parse a block of raw text lines into an Utterance (field-list mode)."""
        parsed: list[AnyLine] = []
        for raw in raw_lines:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            parsed.append(_classify_line(line))
        obj = cls.__new__(cls)
        obj._lines_storage = parsed
        obj._block_elem = None
        return obj

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_text(self) -> str:
        """Serialise to a multi-line string (no trailing blank line)."""
        if self._block_elem is not None:
            return "\n".join(ln.to_text() for ln in self.lines)
        return "\n".join(ln.to_text() for ln in self._lines_storage)

    def __str__(self) -> str:
        return self.to_text()

    def __repr__(self) -> str:
        try:
            n_corpus = len(self.corpus_lines())
        except Exception:
            n_corpus = len(self._lines_storage)
        return f"Utterance(id={self.sentence_id!r}, corpus_lines={n_corpus})"

    # ── convenient accessors ──────────────────────────────────────────────────

    @property
    def header(self) -> "CommentLine | None":
        if self._block_elem is not None:
            header_raw = self._block_elem.get("header")
            return CommentLine(_wrap_header(header_raw)) if header_raw else None
        for ln in self._lines_storage:
            if isinstance(ln, CommentLine) and ln.is_header:
                return ln
        return None

    @property
    def sentence_id(self) -> "str | None":
        if self._block_elem is not None:
            return self._block_elem.get("id")
        for ln in self._lines_storage:
            if isinstance(ln, CommentLine) and ln.is_id_line:
                return ln.sentence_id
        return None

    @property
    def lines(self) -> list[AnyLine]:
        """All lines in source order (header, comments, corpus lines, ID line)."""
        if self._block_elem is not None:
            out: list[AnyLine] = []
            header_raw = self._block_elem.get("header")
            if header_raw:
                out.append(CommentLine(_wrap_header(header_raw)))
            for child in self._block_elem:
                if child.tag == "comment":
                    out.append(CommentLine(child.get("raw") or ""))
            for child in self._block_elem:
                if child.tag != "comment":
                    tmp: list[CorpusLine] = []
                    _collect_corpus_lines(child, [], tmp)
                    out.extend(tmp)
            sid = self._block_elem.get("id")
            if sid:
                out.append(CommentLine(f"ID,{sid}"))
            return out
        return list(self._lines_storage)

    def corpus_lines(self) -> list[CorpusLine]:
        if self._block_elem is not None:
            result: list[CorpusLine] = []
            for child in self._block_elem:
                if child.tag != "comment":
                    _collect_corpus_lines(child, [], result)
            return result
        return [ln for ln in self._lines_storage if isinstance(ln, CorpusLine)]

    def comment_lines(self) -> list[CommentLine]:
        if self._block_elem is not None:
            return [
                CommentLine(child.get("raw") or "")
                for child in self._block_elem
                if child.tag == "comment"
            ]
        return [ln for ln in self._lines_storage if isinstance(ln, CommentLine)]

    def unannotated_lines(self) -> list[CorpusLine]:
        return [ln for ln in self.corpus_lines() if ln.is_annotatable]

    def annotated_lines(self) -> list[CorpusLine]:
        return [ln for ln in self.corpus_lines() if ln.is_annotated]

    # ── querying ──────────────────────────────────────────────────────────────

    def find_by_form(self, form: str) -> list[CorpusLine]:
        return [ln for ln in self.corpus_lines() if ln.word_form == form]

    def find_by_lemma(self, lemma_id: "str | LemmaID") -> list[CorpusLine]:
        target = str(lemma_id)
        return [ln for ln in self.corpus_lines()
                if str(ln.lemma_id) == target]

    def all_lemma_ids(self) -> list[LemmaID]:
        result: list[LemmaID] = []
        for ln in self.corpus_lines():
            result.extend(ln.all_lemma_ids())
        return result

    # ── mutation ──────────────────────────────────────────────────────────────

    def append(self, line: AnyLine) -> None:
        if self._block_elem is not None:
            raise NotImplementedError("Use direct XML element manipulation for XML-backed Utterance")
        self._lines_storage.append(line)

    def insert(self, index: int, line: AnyLine) -> None:
        if self._block_elem is not None:
            raise NotImplementedError("Use direct XML element manipulation for XML-backed Utterance")
        self._lines_storage.insert(index, line)


# ══════════════════════════════════════════════════════════════════════════════
#  XML helpers — tree construction (building XML from corpus lines)
# ══════════════════════════════════════════════════════════════════════════════

def _split_disambig_xml(raw_tag: str) -> tuple[str, str | None]:
    """Split 'N;@2' → ('N', '2').  Plain 'N' → ('N', None)."""
    if ";@" in raw_tag:
        clean, idx = raw_tag.split(";@", 1)
        return clean, idx
    return raw_tag, None


def _sanitize_xml_name(name: str) -> str:
    """Replace characters invalid in XML element names with underscores."""
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)
    if not sanitized or not (sanitized[0].isalpha() or sanitized[0] == "_"):
        sanitized = "_" + sanitized
    return sanitized or "_"


def _effective_path_len(cl: CorpusLine) -> int:
    """
    Return the number of syntactic-path fields the tree builder must account for.

    When a line has a word form but no phon tag (e.g. ``ADJ,ACP-ADN,ki``),
    ``CorpusLine.synt_path`` stops one field early because the leaf syntactic
    tag sits where the phon-tag slot would be.  Adding 1 here makes the builder
    treat that line as one level deeper, correctly placing the extra tag.
    """
    n = len(cl.synt_path)
    if cl.word_form is not None and cl.phon_tag is None:
        n += 1
    return n


def _node_key(cl: CorpusLine, depth: int) -> tuple[str, str | None]:
    """
    Return the (raw_tag, embedded_lemma_or_None) identity of the node at
    *depth* in *cl*'s syntactic path.

    An embedded lemma is a lemma-ID-shaped field immediately after the syntactic
    tag at *depth* (e.g. ``…,VB-ADC,L031257a,VB-STM,…`` → the ``VB-ADC`` node
    carries lemma ``L031257a``).
    """
    path = cl.synt_path
    raw_tag = path[depth]
    next_depth = depth + 1
    if next_depth < len(path) and _LEMMA_RE.match(path[next_depth]):
        return raw_tag, path[next_depth]
    return raw_tag, None


def _make_leaf_elem(cl: CorpusLine) -> ET.Element:
    """Build an XML leaf element from a CorpusLine.

    When a CorpusLine has no phon tag (e.g. ``ADJ,ACP-ADN,ki``), the leaf
    syntactic tag is ``fields[-2]`` and is not captured by ``synt_path``.
    """
    phon = cl.phon_tag
    if phon is None and cl.word_form is not None and len(cl.fields) >= 2:
        raw_tag = cl.fields[-2]
    else:
        path = cl.synt_path
        raw_tag = path[-1] if path else "_"

    clean_tag, idx = _split_disambig_xml(raw_tag)
    xml_tag = _sanitize_xml_name(clean_tag)

    elem = ET.Element(xml_tag)
    if idx:
        elem.set("index", idx)
    if xml_tag != clean_tag:
        elem.set("raw_tag", clean_tag)
    if cl.lemma_id is not None:
        elem.set("lemma", str(cl.lemma_id))
    elem.set("phon", strip_disambig(phon) if phon else "")
    elem.set("form", cl.word_form or "")
    return elem


def _build_children(lines: list[CorpusLine], depth: int) -> list[ET.Element]:
    """
    Recursively group a flat list of corpus lines into nested XML elements.

    At each depth level the shared prefix tag determines the parent element;
    lines that terminate at this depth become leaf elements.

    Embedded lemma IDs: when a syntactic tag is immediately followed by a
    lemma-ID-shaped field in the path (e.g. ``VB-ADC,L031257a``), that ID
    becomes a ``lemma`` attribute on the internal node.

    Index inference: if a base tag appears without a ``@N`` suffix at this
    depth but a sibling carries ``N;@2`` or higher, the no-suffix occurrence
    gets ``index="1"`` marked as inferred (so round-trip does not add ``;@1``).
    """
    suffixed_bases: set[str] = set()
    for cl in lines:
        if depth < len(cl.synt_path):
            raw = cl.synt_path[depth]
            if ";@" in raw:
                base, _ = raw.split(";@", 1)
                suffixed_bases.add(base)

    results: list[ET.Element] = []
    i = 0
    while i < len(lines):
        cl = lines[i]
        if depth >= len(cl.synt_path):
            results.append(_make_leaf_elem(cl))
            i += 1
            continue

        raw_tag, emb_lemma = _node_key(cl, depth)
        child_depth = depth + (2 if emb_lemma is not None else 1)
        is_leaf = (child_depth > _effective_path_len(cl) - 1)

        if is_leaf:
            leaf = _make_leaf_elem(cl)
            if leaf.get("index") is None:
                clean_tag, _ = _split_disambig_xml(raw_tag)
                if clean_tag in suffixed_bases:
                    leaf.set("index", "1")
                    leaf.set("inferred_index", "1")
            results.append(leaf)
            i += 1
        else:
            run: list[CorpusLine] = []
            while i < len(lines):
                next_cl = lines[i]
                if depth >= len(next_cl.synt_path):
                    break
                if _node_key(next_cl, depth) != (raw_tag, emb_lemma):
                    break
                next_child_depth = depth + (2 if emb_lemma is not None else 1)
                if next_child_depth > _effective_path_len(next_cl) - 1:
                    break
                run.append(next_cl)
                i += 1

            if not run:
                results.append(_make_leaf_elem(cl))
                i += 1
                continue

            clean_tag, idx = _split_disambig_xml(raw_tag)
            inferred = False
            if idx is None and clean_tag in suffixed_bases:
                idx = "1"
                inferred = True
            xml_tag = _sanitize_xml_name(clean_tag)
            elem = ET.Element(xml_tag)
            if idx:
                elem.set("index", idx)
            if inferred:
                elem.set("inferred_index", "1")
            if xml_tag != clean_tag:
                elem.set("raw_tag", clean_tag)
            if emb_lemma:
                elem.set("lemma", emb_lemma)
            for child in _build_children(run, child_depth):
                elem.append(child)
            results.append(elem)

    return results


def _strip_header_wrapper(raw: str) -> str:
    """Extract the inner word string from ``=N(" words ")`` for XML storage."""
    m = _HEADER_INNER_RE.match(raw)
    return m.group(1).strip() if m else raw


def _wrap_header(words: str) -> str:
    """Reconstruct the ``=N(" words ")`` txt format from a stored word string."""
    if _HEADER_RE.match(words):
        return words  # already wrapped (field-list mode passthrough)
    return f'=N(" {words} ")'


def _utterance_to_elem(utt: Utterance) -> ET.Element:
    """Convert an Utterance to an XML <block> element."""
    elem = ET.Element("block")
    sid = utt.sentence_id
    if sid:
        elem.set("id", sid)
    hdr = utt.header
    if hdr:
        elem.set("header", _strip_header_wrapper(hdr.raw))

    for cl in utt.comment_lines():
        if cl.is_inline_comment:
            c = ET.SubElement(elem, "comment")
            c.set("raw", cl.raw)

    for child in _build_children(utt.corpus_lines(), 0):
        elem.append(child)

    return elem


# ══════════════════════════════════════════════════════════════════════════════
#  XML helpers — tree parsing (restoring corpus lines from XML)
# ══════════════════════════════════════════════════════════════════════════════

def _collect_corpus_lines(
    elem: ET.Element,
    ancestors: list[ET.Element],
    result: list[CorpusLine],
) -> None:
    """
    Recursively walk *elem*, collecting XML-backed ``CorpusLine`` objects.

    Each leaf element (one with a ``form`` attribute and no non-comment children)
    becomes a ``CorpusLine._from_elem(leaf, ancestors)`` where *ancestors* is
    the path from the first syntactic element below ``<block>`` down to the
    leaf's direct parent.
    """
    children = [c for c in elem if c.tag != "comment"]
    if not children:
        if elem.get("form") is not None:
            result.append(CorpusLine._from_elem(elem, ancestors))
        return
    for child in children:
        _collect_corpus_lines(child, ancestors + [elem], result)


def _reconstruct_lines(
    elem: ET.Element,
    path: list[str],
    out: list[CorpusLine],
) -> None:
    """
    Recursively walk an XML element tree and append reconstructed field-list
    CorpusLines to *out*.

    Round-trip invariants:
    - ``index`` is only re-attached as ``;@N`` when ``inferred_index`` is absent.
    - Leaves with no phon tag (``phon=""``) omit the phon field entirely.
    """
    raw_tag = elem.get("raw_tag") or elem.tag
    idx = elem.get("index")
    if idx and not elem.get("inferred_index"):
        raw_tag = f"{raw_tag};@{idx}"

    node_path = path + [raw_tag]
    emb_lemma = elem.get("lemma")

    children = [c for c in elem if c.tag != "comment"]
    if not children:
        phon = elem.get("phon") or ""
        form = elem.get("form") or ""
        fields: list[str] = list(node_path)
        if emb_lemma:
            fields.append(emb_lemma)
        if phon:
            fields.append(phon)
        if form:
            fields.append(form)
        out.append(CorpusLine(fields))
    else:
        child_prefix = node_path + ([emb_lemma] if emb_lemma else [])
        for child in children:
            _reconstruct_lines(child, child_prefix, out)


def _utterance_from_elem(elem: ET.Element) -> Utterance:
    """Convert a <block> XML element back to a field-list-mode Utterance."""
    lines: list[AnyLine] = []

    header_raw = elem.get("header")
    if header_raw:
        lines.append(CommentLine(_wrap_header(header_raw)))

    for child in elem:
        if child.tag == "comment":
            lines.append(CommentLine(child.get("raw") or ""))

    corpus_lines: list[CorpusLine] = []
    for child in elem:
        if child.tag != "comment":
            _reconstruct_lines(child, [], corpus_lines)
    lines.extend(corpus_lines)

    sid = elem.get("id")
    if sid:
        lines.append(CommentLine(f"ID,{sid}"))

    return Utterance(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  CorpusDocument
# ══════════════════════════════════════════════════════════════════════════════

class CorpusDocument:
    """
    A whole corpus text file: an ordered list of ``Utterance`` objects.

    Dual-mode:
    - **Field-list mode**: ``self._utterances`` holds ``Utterance`` objects.
    - **XML mode**: ``self._doc_elem`` is a ``<document>`` ET.Element; the
      ``utterances`` property yields XML-backed ``Utterance`` objects on demand.

    ``from_file(path)`` and ``to_file(path)`` auto-detect format by extension
    (``.xml`` or ``.txt``).
    """

    def __init__(self, utterances: "list[Utterance] | None" = None,
                 filename: str = "") -> None:
        self._utterances: list[Utterance] = list(utterances) if utterances else []
        self.filename = filename
        self._doc_elem: ET.Element | None = None

    @classmethod
    def _from_elem(cls, doc_elem: ET.Element) -> "CorpusDocument":
        """Create an XML-backed CorpusDocument wrapping *doc_elem*."""
        obj: CorpusDocument = cls.__new__(cls)
        obj._utterances = []
        obj.filename = doc_elem.get("filename") or ""
        obj._doc_elem = doc_elem
        return obj

    # ── utterances property ───────────────────────────────────────────────────

    @property
    def utterances(self) -> list[Utterance]:
        if self._doc_elem is not None:
            return [Utterance._from_elem(blk)
                    for blk in self._doc_elem if blk.tag == "block"]
        return self._utterances

    # ── parsing ───────────────────────────────────────────────────────────────

    @classmethod
    def from_text(cls, text: str, filename: str = "") -> "CorpusDocument":
        """
        Parse the full text of a corpus file and build an XML-backed
        CorpusDocument (so that ``to_file(xml_path)`` works without a separate
        conversion step).
        """
        # Split into blocks (utterances) separated by blank lines
        blocks: list[list[str]] = []
        current: list[str] = []
        for raw in text.splitlines():
            if raw.strip() == "":
                if current:
                    blocks.append(current)
                    current = []
            else:
                current.append(raw)
        if current:
            blocks.append(current)

        doc_elem = ET.Element("document")
        doc_elem.set("filename", filename)
        for block in blocks:
            utt = Utterance.from_lines(block)
            if utt.lines:
                doc_elem.append(_utterance_to_elem(utt))

        obj = cls.__new__(cls)
        obj._utterances = []
        obj.filename = filename
        obj._doc_elem = doc_elem
        return obj

    @classmethod
    def from_file(cls, path: str) -> "CorpusDocument":
        """
        Load a corpus document from *path*.  Detects format by extension:
        ``.xml`` → parse XML directly; anything else → parse comma-path text.
        """
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xml":
            tree = ET.parse(path)
            root = tree.getroot()
            obj = cls._from_elem(root)
            # Override filename from the file path if not in the XML attribute
            if not obj.filename:
                obj.filename = os.path.basename(path)
            return obj
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        return cls.from_text(text, filename=os.path.basename(path))

    # ── serialisation ─────────────────────────────────────────────────────────

    def _get_doc_elem(self) -> ET.Element:
        """Return or build the underlying ET.Element root."""
        if self._doc_elem is not None:
            return self._doc_elem
        root = ET.Element("document")
        root.set("filename", self.filename)
        for utt in self._utterances:
            root.append(_utterance_to_elem(utt))
        return root

    def to_text(self) -> str:
        """
        Serialise back to the canonical comma-path format: utterances separated
        by a single blank line, with a trailing newline.
        """
        if self._doc_elem is not None:
            parts = [
                Utterance._from_elem(blk).to_text()
                for blk in self._doc_elem if blk.tag == "block"
            ]
            return "\n\n".join(parts) + "\n"
        return "\n\n".join(utt.to_text() for utt in self._utterances) + "\n"

    def to_file(self, path: str) -> None:
        """
        Write to *path*.  Detects format by extension:
        ``.xml`` → indented XML with declaration; anything else → comma-path text.
        """
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xml":
            root = self._get_doc_elem()
            ET.indent(root, space="  ")
            buf = io.BytesIO()
            ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(buf.getvalue().decode("utf-8"))
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.to_text())

    # ── access ────────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self.utterances)

    def __iter__(self) -> Iterator[Utterance]:
        return iter(self.utterances)

    def __getitem__(self, idx: int) -> Utterance:
        return self.utterances[idx]

    def __repr__(self) -> str:
        return f"CorpusDocument({self.filename!r}, {len(self)} utterances)"

    # ── querying ──────────────────────────────────────────────────────────────

    def all_corpus_lines(self) -> list[CorpusLine]:
        result: list[CorpusLine] = []
        for utt in self.utterances:
            result.extend(utt.corpus_lines())
        return result

    def find_utterance(self, sentence_id: str) -> "Utterance | None":
        for utt in self.utterances:
            if utt.sentence_id == sentence_id:
                return utt
        return None

    def find_by_form(self, form: str) -> list[tuple[Utterance, CorpusLine]]:
        result = []
        for utt in self.utterances:
            for ln in utt.find_by_form(form):
                result.append((utt, ln))
        return result

    def find_by_lemma(self, lemma_id: "str | LemmaID") -> list[tuple[Utterance, CorpusLine]]:
        result = []
        for utt in self.utterances:
            for ln in utt.find_by_lemma(lemma_id):
                result.append((utt, ln))
        return result

    def all_lemma_ids(self) -> set[LemmaID]:
        result: set[LemmaID] = set()
        for utt in self.utterances:
            result.update(utt.all_lemma_ids())
        return result

    def unannotated_forms(self) -> dict[str, list[CorpusLine]]:
        result: dict[str, list[CorpusLine]] = {}
        for utt in self.utterances:
            for ln in utt.unannotated_lines():
                form = ln.word_form
                if form:
                    result.setdefault(form, []).append(ln)
        return result

    # ── mutation ──────────────────────────────────────────────────────────────

    def append(self, utt: Utterance) -> None:
        if self._doc_elem is not None:
            self._doc_elem.append(_utterance_to_elem(utt))
        else:
            self._utterances.append(utt)


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _is_corpus_line(line: str) -> bool:
    """
    Heuristic: a line is a corpus (tree-path) line if it starts with a
    syntactic-category token, is NOT a header or ID line, and does NOT end
    with ``*`` (which marks inline original-script comments).
    """
    if _HEADER_RE.match(line) or _ID_LINE_RE.match(line):
        return False
    parts = line.split(",")
    if parts[-1] == "*":
        return False
    return bool(_SYNCTAG_RE.match(parts[0]) or _MULTIROOT_RE.match(parts[0]))


def _classify_line(line: str) -> AnyLine:
    if _is_corpus_line(line):
        return CorpusLine.parse(line)
    return CommentLine.parse(line)
