"""
Dictionary model for the ONCOJ lexicon.

Text format (one entry)
-----------------------
---------------------------------------------------   ← ENTRY_SEP (51 dashes)
=== L000006a
.GLOSS  NEG
.MEANING    [negative]
.FORM   nu
.KANA   ヌ
.FORM   zu
.KANA   ズ
.POS    auxiliary
.NOTE   conclusive: -zu; ...
.COMPOUND   ref_target=L000006a  zu
                                    ← trailing blank line

Fields whose name appears more than once (e.g. .FORM / .KANA / .MEANING[1])
are stored as lists; all others are singular strings.

Multi-valued fields in the file may be written with explicit indices
(.MEANING[1], .MEANING[2]) or as repeated plain tags (.FORM twice).
Both are normalised to ordered lists in memory.

Classes
-------
DictEntry   — one lexicon entry (mutable)
Dictionary  — ordered collection of entries with lookup helpers
"""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import Iterator

from coj.core.kana import phonemic_to_kana
from coj.core.lemma_id import LemmaID
from coj.core.tags import MULTI_VALUE_FIELDS, REQUIRED_FIELDS

# ── file-format constants ──────────────────────────────────────────────────────

ENTRY_SEP = "-" * 51          # separator line between entries
_HEAD_RE  = re.compile(r'^=== ([A-Za-z]\d+[a-z]*)$')
_TAG_RE   = re.compile(r'^(\.[A-Z]+)(?:\[(\d+)\])?\t?(.*)')

# Required tags that every well-formed entry must contain, in canonical order
REQUIRED_TAGS = list(REQUIRED_FIELDS)

# Tags that are naturally multi-valued (repeated in the file)
_MULTI_TAGS = MULTI_VALUE_FIELDS


# ══════════════════════════════════════════════════════════════════════════════
#  DictEntry
# ══════════════════════════════════════════════════════════════════════════════

class DictEntry:
    """
    One dictionary entry.

    Fields are stored in insertion order as an ``OrderedDict`` mapping
    tag name (e.g. ``".FORM"``) to either:

    * ``str``   — for single-valued tags (.GLOSS, .POS, .NOTE, …)
    * ``list[str]`` — for multi-valued tags (.FORM, .KANA, .MEANING,
                       .COMPOUND, .RELATED)

    The distinction follows ``_MULTI_TAGS``; any tag not in that set is
    treated as singular (last write wins, which matches file semantics).
    """

    def __init__(self, eid: str | LemmaID,
                 fields: "OrderedDict[str, str | list[str]] | None" = None) -> None:
        self.eid: LemmaID = (
            LemmaID.parse(str(eid)) if not isinstance(eid, LemmaID) else eid
        )
        self._fields: OrderedDict[str, str | list[str]] = (
            OrderedDict(fields) if fields else OrderedDict()
        )

    # ── field access ──────────────────────────────────────────────────────────

    def get(self, tag: str) -> "str | list[str] | None":
        """
        Return the value(s) for *tag* (without leading dot, case-insensitive),
        or ``None`` if absent.

        Returns a ``str`` for singular tags, ``list[str]`` for multi-valued ones.
        """
        key = _normalise_tag(tag)
        return self._fields.get(key)

    def get_first(self, tag: str) -> "str | None":
        """Return the first (or only) value for *tag*, or ``None``."""
        val = self.get(tag)
        if val is None:
            return None
        return val[0] if isinstance(val, list) else val

    def get_all(self, tag: str) -> list[str]:
        """Always return a list of values for *tag* (empty if absent)."""
        val = self.get(tag)
        if val is None:
            return []
        return val if isinstance(val, list) else [val]

    def has(self, tag: str) -> bool:
        return _normalise_tag(tag) in self._fields

    def tags(self) -> list[str]:
        """Return tag names in insertion order."""
        return list(self._fields.keys())

    # ── mutation ──────────────────────────────────────────────────────────────

    def set(self, tag: str, value: "str | list[str]") -> None:
        """
        Set *tag* to *value*, replacing any existing value.
        For multi-valued tags, *value* may be a list.
        """
        key = _normalise_tag(tag)
        if key in _MULTI_TAGS:
            self._fields[key] = list(value) if isinstance(value, list) else [value]
        else:
            self._fields[key] = str(value)

    def append(self, tag: str, value: str) -> None:
        """Append *value* to a multi-valued *tag*; raises if tag is singular."""
        key = _normalise_tag(tag)
        if key not in _MULTI_TAGS:
            raise ValueError(f"{key} is a singular tag; use set() instead")
        existing = self._fields.get(key)
        if existing is None:
            self._fields[key] = [value]
        else:
            assert isinstance(existing, list)
            existing.append(value)

    def remove(self, tag: str) -> None:
        """Remove *tag* entirely. No-op if absent."""
        self._fields.pop(_normalise_tag(tag), None)

    def update(self, tag: str, value: str, index: int = 0) -> None:
        """
        Update a specific occurrence of a multi-valued *tag* at *index*.
        For singular tags, *index* is ignored.
        """
        key = _normalise_tag(tag)
        if key in _MULTI_TAGS:
            vals = self._fields.get(key)
            if vals is None:
                self._fields[key] = [value]
            else:
                assert isinstance(vals, list)
                if index >= len(vals):
                    vals.append(value)
                else:
                    vals[index] = value
        else:
            self._fields[key] = value

    # ── normalisation ─────────────────────────────────────────────────────────

    def normalise(self) -> list[str]:
        """
        Ensure all REQUIRED_TAGS are present in canonical order.
        Auto-fills .KANA from .FORM when blank.
        Returns a list of human-readable change descriptions.
        """
        changes: list[str] = []

        for tag in REQUIRED_TAGS:
            if not self.has(tag):
                if tag == ".KANA":
                    forms = self.get_all(".FORM")
                    kanas = [phonemic_to_kana(f) for f in forms]
                    self.set(tag, kanas or [""])
                    changes.append(f"added {tag} = {kanas}")
                else:
                    self.set(tag, "" if tag not in _MULTI_TAGS else [])
                    changes.append(f"added {tag} (blank)")
            elif tag == ".KANA":
                kanas = self.get_all(".KANA")
                forms = self.get_all(".FORM")
                new_kanas = []
                changed = False
                for i, k in enumerate(kanas):
                    if not k and i < len(forms):
                        new_kanas.append(phonemic_to_kana(forms[i]))
                        changed = True
                    else:
                        new_kanas.append(k)
                if changed:
                    self.set(".KANA", new_kanas)
                    changes.append(f"filled .KANA = {new_kanas}")

        # Reorder so REQUIRED_TAGS come first in canonical order
        reordered: OrderedDict[str, str | list[str]] = OrderedDict()
        for tag in REQUIRED_TAGS:
            if tag in self._fields:
                reordered[tag] = self._fields[tag]
        for tag, val in self._fields.items():
            if tag not in reordered:
                reordered[tag] = val
        self._fields = reordered

        return changes

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_text(self) -> str:
        """
        Serialise to the canonical on-disk format::

            ---------------------------------------------------
            === L000006a
            .GLOSS\\tNEG
            .FORM\\tnu
            .KANA\\tヌ
            ...
                                  ← trailing blank line
        """
        lines: list[str] = [ENTRY_SEP, f"=== {self.eid}"]
        for tag, val in self._fields.items():
            if isinstance(val, list):
                for item in val:
                    lines.append(f"{tag}\t{item}")
            else:
                lines.append(f"{tag}\t{val}")
        lines.append("")   # trailing blank line
        return "\n".join(lines) + "\n"

    # ── equality / repr ───────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DictEntry):
            return self.eid == other.eid and self._fields == other._fields
        return NotImplemented

    def __repr__(self) -> str:
        return f"DictEntry({self.eid!r}, fields={list(self._fields.keys())})"

    @classmethod
    def blank(cls, eid: "str | LemmaID", form: str = "") -> "DictEntry":
        """
        Create a minimal entry with all required tags blank-filled.
        If *form* is given, .FORM and .KANA are pre-filled.
        """
        entry = cls(eid)
        entry.set(".GLOSS", "")
        entry.set(".MEANING", [])
        if form:
            entry.set(".FORM", [form])
            entry.set(".KANA", [phonemic_to_kana(form)])
        else:
            entry.set(".FORM", [])
            entry.set(".KANA", [])
        entry.set(".POS", "")
        return entry


# ══════════════════════════════════════════════════════════════════════════════
#  Dictionary
# ══════════════════════════════════════════════════════════════════════════════

class Dictionary:
    """
    Ordered collection of ``DictEntry`` objects with lookup helpers.

    Entries are stored in the order they appear in the source file, so
    round-tripping via ``from_text`` / ``to_text`` preserves that order.
    New entries added via ``add`` are appended at the end; ``sorted_entries``
    returns them in numeric ID order.
    """

    def __init__(self) -> None:
        self._entries: OrderedDict[str, DictEntry] = OrderedDict()

    # ── loading / saving ──────────────────────────────────────────────────────

    @classmethod
    def from_text(cls, text: str) -> "Dictionary":
        """Parse the full text of a dictionary file into a Dictionary."""
        d = cls()
        blocks = text.split(ENTRY_SEP)
        for block in blocks[1:]:          # first chunk is preamble
            entry = _parse_block(block)
            if entry is not None:
                d._entries[str(entry.eid)] = entry
        return d

    @classmethod
    def from_file(cls, path: str) -> "Dictionary":
        """
        Load a dictionary from *path*.  Detects format by extension:
        ``.xml`` → delegate to ``coj.xml.dictionary_xml``; anything else
        → parse comma-separated text.
        """
        import os
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xml":
            from coj.xml.dictionary_xml import dictionary_from_xml_file
            return dictionary_from_xml_file(path)
        with open(path, encoding="utf-8") as fh:
            return cls.from_text(fh.read())

    def to_text(self) -> str:
        """Serialise the whole dictionary to a single string."""
        return "".join(e.to_text() for e in self._entries.values())

    def to_file(self, path: str) -> None:
        """
        Write to *path*.  Detects format by extension:
        ``.xml`` → delegate to ``coj.xml.dictionary_xml``; anything else
        → comma-separated text.
        """
        import os
        ext = os.path.splitext(path)[1].lower()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if ext == ".xml":
            from coj.xml.dictionary_xml import dictionary_to_xml_file
            dictionary_to_xml_file(self, path)
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.to_text())

    # ── entry access ──────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, eid: "str | LemmaID") -> bool:
        return str(eid) in self._entries

    def __iter__(self) -> Iterator[DictEntry]:
        return iter(self._entries.values())

    def get(self, eid: "str | LemmaID") -> "DictEntry | None":
        return self._entries.get(str(eid))

    def __getitem__(self, eid: "str | LemmaID") -> DictEntry:
        key = str(eid)
        if key not in self._entries:
            raise KeyError(key)
        return self._entries[key]

    def sorted_entries(self) -> list[DictEntry]:
        """Return entries sorted in numeric ID order (then suffix)."""
        return sorted(self._entries.values(), key=lambda e: e.eid)

    # ── mutation ──────────────────────────────────────────────────────────────

    def add(self, entry: DictEntry, *, allow_update: bool = False) -> None:
        """
        Add *entry* to the dictionary.
        Raises ``KeyError`` if the ID already exists unless *allow_update* is True.
        """
        key = str(entry.eid)
        if key in self._entries and not allow_update:
            raise KeyError(f"Entry {key!r} already exists; use allow_update=True to replace")
        self._entries[key] = entry

    def delete(self, eid: "str | LemmaID") -> DictEntry:
        """Remove and return the entry for *eid*. Raises ``KeyError`` if absent."""
        key = str(eid)
        if key not in self._entries:
            raise KeyError(key)
        return self._entries.pop(key)

    def update_field(self, eid: "str | LemmaID", tag: str,
                     value: "str | list[str]") -> None:
        """Set *tag* on the entry identified by *eid*."""
        self[eid].set(tag, value)

    # ── querying ──────────────────────────────────────────────────────────────

    def find_by_form(self, form: str) -> list[DictEntry]:
        """Return all entries whose .FORM list contains *form* (exact match)."""
        return [e for e in self._entries.values()
                if form in e.get_all(".FORM")]

    def find_by_pos(self, pos: str, *, exact: bool = True) -> list[DictEntry]:
        """
        Return entries whose .POS field matches *pos*.
        With ``exact=False``, a substring match is used (case-insensitive).
        """
        if exact:
            return [e for e in self._entries.values()
                    if e.get_first(".POS") == pos]
        pos_up = pos.upper()
        return [e for e in self._entries.values()
                if pos_up in (e.get_first(".POS") or "").upper()]

    def find_by_gloss(self, gloss: str, *, exact: bool = True) -> list[DictEntry]:
        if exact:
            return [e for e in self._entries.values()
                    if e.get_first(".GLOSS") == gloss]
        g_up = gloss.upper()
        return [e for e in self._entries.values()
                if g_up in (e.get_first(".GLOSS") or "").upper()]

    def used_numbers(self) -> set[int]:
        """Return the set of all numeric parts of existing entry IDs."""
        return {e.eid.number for e in self._entries.values()}

    # ── normalisation ─────────────────────────────────────────────────────────

    def normalise_all(self) -> dict[str, list[str]]:
        """
        Call ``normalise()`` on every entry.
        Returns a dict mapping entry ID → list of change descriptions
        for entries that were actually changed.
        """
        report: dict[str, list[str]] = {}
        for entry in self._entries.values():
            changes = entry.normalise()
            if changes:
                report[str(entry.eid)] = changes
        return report

    def __repr__(self) -> str:
        return f"Dictionary({len(self)} entries)"


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _normalise_tag(tag: str) -> str:
    """Ensure the tag has a leading dot and is upper-cased, e.g. 'form' → '.FORM'."""
    tag = tag.strip()
    if not tag.startswith("."):
        tag = "." + tag
    return tag.upper()


def _parse_block(block: str) -> "DictEntry | None":
    """Parse one raw block (text after a separator) into a DictEntry."""
    lines = block.lstrip("\r\n").splitlines()
    if not lines:
        return None

    header = lines[0].rstrip()
    m = _HEAD_RE.match(header)
    if not m:
        return None

    eid = LemmaID.parse(m.group(1))
    entry = DictEntry(eid)

    # Track insertion order for multi-valued tags with explicit indices
    # e.g. .MEANING[1], .MEANING[2] — gather all then set at the end
    indexed: dict[str, dict[int, str]] = {}

    for raw in lines[1:]:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        tm = _TAG_RE.match(line)
        if not tm:
            continue
        base_tag = tm.group(1).upper()
        index    = int(tm.group(2)) if tm.group(2) else None
        value    = tm.group(3).strip() if tm.group(3) else ""

        if index is not None:
            # Explicit-index form (.MEANING[1], .MEANING[2], …)
            indexed.setdefault(base_tag, {})[index] = value
        elif base_tag in _MULTI_TAGS:
            entry.append(base_tag, value)
        else:
            entry.set(base_tag, value)

    # Flush explicitly-indexed fields in index order
    for tag, idx_map in indexed.items():
        values = [idx_map[k] for k in sorted(idx_map)]
        existing = entry.get_all(tag)
        entry.set(tag, existing + values)

    return entry
