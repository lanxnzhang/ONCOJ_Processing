"""
Corpus model for ONCOJ text files.

Text format (one sentence / utterance)
---------------------------------------
=N(" kamu nusi papuri ra moromoro ... ")        ← utterance header
IP-MAT,IP-ARG,0@神主祝部等諸聞食登,*             ← comment line (tag ends with `)
IP-MAT,IP-ARG,C-NP,N,N,LOG,kamu                ← tree path (corpus) line
IP-MAT,IP-ARG,C-NP,N,N,L000006a,LOG,nu         ← tree path with lemma ID
ID,1_EN_01                                      ← sentence ID line
                                                ← blank line separating utterances

A corpus file is a sequence of utterances separated by blank lines.

Classes
-------
CorpusLine   — one annotated tree-path line (mutable)
CommentLine  — one non-tree line (header / comment / ID / special)
Utterance    — one sentence block: header + lines + sentence ID
CorpusDocument — a whole corpus file
"""

from __future__ import annotations

import re
from typing import Iterator

from oncoj.lemma_id import LemmaID
from oncoj.tags import PHON_TAGS, strip_disambig

# ── regexes ───────────────────────────────────────────────────────────────────

_LEMMA_RE    = re.compile(r'^[A-Za-z]\d+[a-z]*$')
_SYNCTAG_RE  = re.compile(r'^[A-Z][A-Z0-9\-]*(?:;@\d+)?$')   # e.g. NP, VB-STM, N;@2
_WORDFORM_RE = re.compile(r'^[A-Za-z]+$')

# Header pattern: =N(" ... ")  or  =N(...)
_HEADER_RE   = re.compile(r'^=\w+\(')
# Sentence ID line: ID,<text>
_ID_LINE_RE  = re.compile(r'^ID,')


# ══════════════════════════════════════════════════════════════════════════════
#  CorpusLine
# ══════════════════════════════════════════════════════════════════════════════

class CorpusLine:
    """
    One corpus (tree-path) line.

    The line is stored as an ordered list of fields split on commas.
    The class provides structured accessors for the fields that carry
    linguistic information (syntactic path, lemma ID, phonetic tag, word form)
    and mutation helpers for the annotation workflow.

    A well-formed annotated line has the shape::

        <path...>, [<lemma_id>], <phon_tag>, <word_form>

    where the lemma ID is optional (absent on unannotated lines).
    """

    def __init__(self, fields: list[str]) -> None:
        self.fields: list[str] = list(fields)

    # ── parsing ───────────────────────────────────────────────────────────────

    @classmethod
    def parse(cls, line: str) -> "CorpusLine":
        fields = line.rstrip("\r\n").split(",")
        return cls(fields)

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_text(self) -> str:
        return ",".join(self.fields)

    def __str__(self) -> str:
        return self.to_text()

    def __repr__(self) -> str:
        return f"CorpusLine({self.fields!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CorpusLine):
            return self.fields == other.fields
        return NotImplemented

    # ── field inspection ──────────────────────────────────────────────────────

    @property
    def word_form(self) -> "str | None":
        """Last field if it is a pure-alphabetic word form, else None."""
        last = self.fields[-1] if self.fields else ""
        return last if _WORDFORM_RE.match(last) else None

    @property
    def phon_tag(self) -> "str | None":
        """
        The writing-mode tag (LOG, PHON, NLOG, PHON-ON, BPHON, …) if the line
        has a word form, else None.  The raw tag (with any ;@N suffix) is
        returned; use ``strip_disambig`` if you need the bare name.
        """
        if self.word_form is None or len(self.fields) < 2:
            return None
        tag = self.fields[-2]
        return tag if strip_disambig(tag) in PHON_TAGS else None

    @property
    def lemma_id(self) -> "LemmaID | None":
        """
        The lemma ID inserted between the syntactic path and the phon tag,
        if present. Returns None on unannotated lines.
        """
        if self.word_form is None or len(self.fields) < 3:
            return None
        candidate = self.fields[-3]
        if _LEMMA_RE.match(candidate):
            return LemmaID.parse(candidate)
        return None

    @property
    def synt_path(self) -> list[str]:
        """
        Return the syntactic path fields — everything before the lemma ID
        (or before the phon tag if no lemma ID is present).
        """
        if self.word_form is None:
            return list(self.fields)
        end = -2   # before phon_tag and word_form
        if self.lemma_id is not None:
            end = -3
        return self.fields[:end] if end < 0 else []

    @property
    def is_annotated(self) -> bool:
        """True if a lemma ID is already present."""
        return self.lemma_id is not None

    @property
    def is_annotatable(self) -> bool:
        """True if the line has a word form and is not yet annotated."""
        return self.word_form is not None and not self.is_annotated

    def preceding_synt_tag(self) -> "str | None":
        """
        Return the syntactic tag immediately before the lemma-ID slot
        (i.e. the last element of the syntactic path).
        """
        path = self.synt_path
        return path[-1] if path else None

    # ── mutation ──────────────────────────────────────────────────────────────

    def insert_lemma(self, lemma_id: "str | LemmaID") -> None:
        """
        Insert *lemma_id* into the lemma-ID slot (between path and phon tag).
        Raises ``ValueError`` if already annotated or line has no word form.
        """
        if self.word_form is None:
            raise ValueError("Cannot annotate a line with no word form")
        if self.is_annotated:
            raise ValueError(f"Line already annotated with {self.lemma_id}")
        # Insert before the phon tag (index -2 from end)
        insert_at = len(self.fields) - 2
        self.fields.insert(insert_at, str(lemma_id))

    def replace_lemma(self, lemma_id: "str | LemmaID") -> None:
        """
        Replace an existing lemma ID in-place.
        Raises ``ValueError`` if the line is not annotated.
        """
        if not self.is_annotated:
            raise ValueError("Line has no lemma ID to replace")
        idx = len(self.fields) - 3
        self.fields[idx] = str(lemma_id)

    def remove_lemma(self) -> "LemmaID | None":
        """Remove and return the lemma ID. Returns None if not annotated."""
        if not self.is_annotated:
            return None
        idx = len(self.fields) - 3
        old = LemmaID.parse(self.fields[idx])
        del self.fields[idx]
        return old

    # ── querying helpers ──────────────────────────────────────────────────────

    def synt_tag_at(self, offset_from_end: int) -> "str | None":
        """
        Return the field at *offset_from_end* positions before the end
        (0 = last field).  Returns None if out of range.
        """
        idx = len(self.fields) - 1 - offset_from_end
        return self.fields[idx] if 0 <= idx < len(self.fields) else None

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

    Lines are stored as a flat list of ``CorpusLine`` / ``CommentLine``
    objects in the order they appear in the file.
    """

    def __init__(self, lines: "list[AnyLine] | None" = None) -> None:
        self.lines: list[AnyLine] = list(lines) if lines else []

    # ── parsing ───────────────────────────────────────────────────────────────

    @classmethod
    def from_lines(cls, raw_lines: list[str]) -> "Utterance":
        """
        Parse a block of raw text lines (stripped of trailing newlines)
        into an Utterance.
        """
        parsed: list[AnyLine] = []
        for raw in raw_lines:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            parsed.append(_classify_line(line))
        return cls(parsed)

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_text(self) -> str:
        """Serialise to a multi-line string (no trailing blank line)."""
        return "\n".join(ln.to_text() for ln in self.lines)

    def __str__(self) -> str:
        return self.to_text()

    def __repr__(self) -> str:
        n_corpus = sum(1 for ln in self.lines if isinstance(ln, CorpusLine))
        return f"Utterance(id={self.sentence_id!r}, corpus_lines={n_corpus})"

    # ── convenient accessors ──────────────────────────────────────────────────

    @property
    def header(self) -> "CommentLine | None":
        for ln in self.lines:
            if isinstance(ln, CommentLine) and ln.is_header:
                return ln
        return None

    @property
    def sentence_id(self) -> "str | None":
        for ln in self.lines:
            if isinstance(ln, CommentLine) and ln.is_id_line:
                return ln.sentence_id
        return None

    def corpus_lines(self) -> list[CorpusLine]:
        return [ln for ln in self.lines if isinstance(ln, CorpusLine)]

    def comment_lines(self) -> list[CommentLine]:
        return [ln for ln in self.lines if isinstance(ln, CommentLine)]

    def unannotated_lines(self) -> list[CorpusLine]:
        return [ln for ln in self.corpus_lines() if ln.is_annotatable]

    def annotated_lines(self) -> list[CorpusLine]:
        return [ln for ln in self.corpus_lines() if ln.is_annotated]

    # ── querying ──────────────────────────────────────────────────────────────

    def find_by_form(self, form: str) -> list[CorpusLine]:
        """Return corpus lines whose word form equals *form*."""
        return [ln for ln in self.corpus_lines() if ln.word_form == form]

    def find_by_lemma(self, lemma_id: "str | LemmaID") -> list[CorpusLine]:
        """Return corpus lines that carry *lemma_id*."""
        target = str(lemma_id)
        return [ln for ln in self.corpus_lines()
                if str(ln.lemma_id) == target]

    def all_lemma_ids(self) -> list[LemmaID]:
        """Return all lemma IDs appearing in any corpus line (with duplicates)."""
        result: list[LemmaID] = []
        for ln in self.corpus_lines():
            result.extend(ln.all_lemma_ids())
        return result

    # ── mutation ──────────────────────────────────────────────────────────────

    def append(self, line: AnyLine) -> None:
        self.lines.append(line)

    def insert(self, index: int, line: AnyLine) -> None:
        self.lines.insert(index, line)


# ══════════════════════════════════════════════════════════════════════════════
#  CorpusDocument
# ══════════════════════════════════════════════════════════════════════════════

class CorpusDocument:
    """
    A whole corpus text file: an ordered list of ``Utterance`` objects.

    Utterances in the file are separated by blank lines.
    """

    def __init__(self, utterances: "list[Utterance] | None" = None,
                 filename: str = "") -> None:
        self.utterances: list[Utterance] = list(utterances) if utterances else []
        self.filename = filename

    # ── parsing ───────────────────────────────────────────────────────────────

    @classmethod
    def from_text(cls, text: str, filename: str = "") -> "CorpusDocument":
        """Parse the full text of a corpus file."""
        doc = cls(filename=filename)
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

        for block in blocks:
            utt = Utterance.from_lines(block)
            if utt.lines:
                doc.utterances.append(utt)
        return doc

    @classmethod
    def from_file(cls, path: str) -> "CorpusDocument":
        import os
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        return cls.from_text(text, filename=os.path.basename(path))

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_text(self) -> str:
        """
        Serialise back to the canonical file format: utterances separated by
        a single blank line, with a trailing newline.
        """
        return "\n\n".join(utt.to_text() for utt in self.utterances) + "\n"

    def to_file(self, path: str) -> None:
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
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
        """Return (utterance, line) pairs where the word form equals *form*."""
        result = []
        for utt in self.utterances:
            for ln in utt.find_by_form(form):
                result.append((utt, ln))
        return result

    def find_by_lemma(self, lemma_id: "str | LemmaID") -> list[tuple[Utterance, CorpusLine]]:
        """Return (utterance, line) pairs that carry *lemma_id*."""
        result = []
        for utt in self.utterances:
            for ln in utt.find_by_lemma(lemma_id):
                result.append((utt, ln))
        return result

    def all_lemma_ids(self) -> set[LemmaID]:
        """Return the set of all distinct LemmaIDs present anywhere in the document."""
        result: set[LemmaID] = set()
        for utt in self.utterances:
            result.update(utt.all_lemma_ids())
        return result

    def unannotated_forms(self) -> dict[str, list[CorpusLine]]:
        """
        Return a mapping from word-form string to all unannotated corpus lines
        that carry that form.
        """
        result: dict[str, list[CorpusLine]] = {}
        for utt in self.utterances:
            for ln in utt.unannotated_lines():
                form = ln.word_form
                if form:
                    result.setdefault(form, []).append(ln)
        return result

    # ── mutation ──────────────────────────────────────────────────────────────

    def append(self, utt: Utterance) -> None:
        self.utterances.append(utt)


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _is_corpus_line(line: str) -> bool:
    """
    Heuristic: a line is a corpus (tree-path) line if it starts with an
    uppercase syntactic-category token, is NOT a header or ID line, and
    does NOT end with ``*`` (which marks inline original-script comments).
    """
    if _HEADER_RE.match(line) or _ID_LINE_RE.match(line):
        return False
    parts = line.split(",")
    if parts[-1] == "*":
        return False
    return bool(_SYNCTAG_RE.match(parts[0]))


def _classify_line(line: str) -> AnyLine:
    if _is_corpus_line(line):
        return CorpusLine.parse(line)
    return CommentLine.parse(line)
