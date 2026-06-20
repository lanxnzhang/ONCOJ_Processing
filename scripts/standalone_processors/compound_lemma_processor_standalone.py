# Version: 2.0.0
# Changes from 1.0.1: new group-detection algorithm; layered binary pairing
# for 3+ components; optional NP expansion.
"""
compound_lemma_processor.py
============================
Detects compound nouns in corpus text files, inserts shared lemma IDs,
and creates/refines dictionary entries.

Algorithm:
1. Find every bare 'N' tag (no lemma after it) whose next fields form
   a sequence of component nouns (N, N;@2, N;@3, …).
2. For 3+ component nouns: pair in layers (binary tree from left).
3. Optional NP-expansion: detect NPs whose ALL immediate direct children
   are N / N;@2 / N;@3 …, insert a grouping N before them, then apply (1).
"""

import os
import re
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# USER SETTINGS
# ──────────────────────────────────────────────────────────────────────────────

TEXT_FOLDER       = "input_texts"
DICT_FILE         = "dictionary.txt"
OUTPUT_FOLDER     = "output_files"

DICT_SEARCH       = True    # look up compound form in dictionary
DICT_REFINE       = True    # add missing .COMPOUND lines to an existing entry
DICT_ENTRY_CREATE = True    # create a new entry when the compound is new

NP_EXPANSION      = True    # detect NP-grouped N;@N siblings and insert marker N

SAVE_REVISED      = True    # write all_revised_lines.txt
OVERWRITE_SOURCE  = False   # overwrite source files; False → OUTPUT_FOLDER

LEMMA_PREFIX      = "L"
LEMMA_DIGITS      = 6
LEMMA_START       = 50001


# ──────────────────────────────────────────────────────────────────────────────
# KANA CONVERSION
# ──────────────────────────────────────────────────────────────────────────────

_KANA_RAW: list[tuple[str, str]] = [
    ("pye", "ヘ"), ("pwi", "ヒ"),
    ("bye", "ベ"), ("bwi", "ビ"),
    ("kye", "ケ"), ("kwi", "キ"), ("kwo", "コ"),
    ("gye", "ゲ"), ("gwi", "ギ"), ("gwo", "ゴ"),
    ("mye", "メ"), ("mwi", "ミ"), ("mwo", "モ"),
    ("two", "ト"), ("dwo", "ド"),
    ("swo", "ソ"), ("zwo", "ゾ"),
    ("nwo", "ノ"), ("ywo", "ヨ"), ("rwo", "ロ"),
    ("pa", "ハ"), ("pi", "ヒ"), ("pu", "フ"), ("pe", "ヘ"), ("po", "ホ"),
    ("ba", "バ"), ("bi", "ビ"), ("bu", "ブ"), ("be", "ベ"), ("bo", "ボ"),
    ("ka", "カ"), ("ki", "キ"), ("ku", "ク"), ("ke", "ケ"), ("ko", "コ"),
    ("ga", "ガ"), ("gi", "ギ"), ("gu", "グ"), ("ge", "ゲ"), ("go", "ゴ"),
    ("ma", "マ"), ("mi", "ミ"), ("mu", "ム"), ("me", "メ"), ("mo", "モ"),
    ("ta", "タ"), ("ti", "チ"), ("tu", "ツ"), ("te", "テ"), ("to", "ト"),
    ("da", "ダ"), ("di", "ヂ"), ("du", "ヅ"), ("de", "デ"), ("do", "ド"),
    ("sa", "サ"), ("si", "シ"), ("su", "ス"), ("se", "セ"), ("so", "ソ"),
    ("za", "ザ"), ("zi", "ジ"), ("zu", "ズ"), ("ze", "ゼ"), ("zo", "ゾ"),
    ("na", "ナ"), ("ni", "ニ"), ("nu", "ヌ"), ("ne", "ネ"), ("no", "ノ"),
    ("ya", "ヤ"), ("yu", "ユ"), ("yo", "ヨ"),
    ("ra", "ラ"), ("ri", "リ"), ("ru", "ル"), ("re", "レ"), ("ro", "ロ"),
    ("wa", "ワ"), ("we", "ヱ"),
    ("ye", "エ"), ("wi", "ヰ"), ("wo", "ヲ"),
    ("a", "ア"), ("i", "イ"), ("u", "ウ"), ("o", "オ"), ("e", "エ"),
]
_KANA_TABLE = sorted(_KANA_RAW, key=lambda x: -len(x[0]))


def phonemic_to_kana(form: str) -> str:
    result: list[str] = []
    pos = 0
    low = form.lower()
    while pos < len(low):
        matched = False
        for phon, kana in _KANA_TABLE:
            if low.startswith(phon, pos):
                result.append(kana)
                pos += len(phon)
                matched = True
                break
        if not matched:
            result.append(f"⟨{low[pos]}⟩")
            pos += 1
    return "".join(result)


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS / REGEX
# ──────────────────────────────────────────────────────────────────────────────

SEPARATOR = "-" * 51
LEMMA_PAT = re.compile(r'^[A-Za-z]\d+[a-z]*$')
PHON_TAGS = {"PHON", "LOG", "PHON-KUN", "PHON-ON", "BPHON", "PLOG",
             "NLOG", "ILL", "ORDLOG", "NLPOG"}

# Matches  N;@2  N;@3  etc. (any ;@N suffix)
N_AT_PAT  = re.compile(r'^N(;@\d+)?$')


def _fields(line: str) -> list[str]:
    return line.rstrip("\r\n").split(",")


def _join(fields: list[str]) -> str:
    return ",".join(fields)


# ──────────────────────────────────────────────────────────────────────────────
# DICTIONARY PARSING
# ──────────────────────────────────────────────────────────────────────────────

def parse_dictionary(dict_path: str) -> dict:
    """
    Returns {lemma_id: {'raw_lines': [...], 'fields': {'.FORM': [...], ...}}}
    raw_lines does NOT include trailing blank lines.
    """
    entries: dict = {}
    current_id    = None
    current_lines: list[str] = []

    def flush():
        if current_id:
            stripped = list(current_lines)
            while stripped and stripped[-1].strip() == "":
                stripped.pop()
            fields = _parse_fields(stripped)
            entries[current_id] = {"raw_lines": stripped, "fields": fields}

    if not os.path.isfile(dict_path):
        return entries

    with open(dict_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"^===\s+([A-Za-z]\d+[a-z]*)\s*$", line)
            if m:
                flush()
                current_id    = m.group(1)
                current_lines = [line]
            elif current_id is not None:
                current_lines.append(line)
    flush()
    return entries


def _parse_fields(lines: list) -> dict:
    fields: dict = {}
    for line in lines[1:]:
        m = re.match(r"^(\.\w+)\s*(.*)", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            fields.setdefault(key, []).append(val)
    return fields


def all_numeric_ids(entries: dict) -> set:
    nums: set = set()
    for lid in entries:
        m = re.search(r'\d+', lid)
        if m:
            nums.add(int(m.group()))
    return nums


def get_first_field(entries: dict, lid: str, field: str) -> str:
    vals = entries.get(lid, {}).get("fields", {}).get(field, [])
    return vals[0].strip() if vals else ""


# ──────────────────────────────────────────────────────────────────────────────
# ID GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

class IDGenerator:
    def __init__(self, used_nums: set):
        self._used: set = set(used_nums)
        self._next: int = LEMMA_START

    def next_id(self) -> str:
        while self._next in self._used:
            self._next += 1
        n = self._next
        self._used.add(n)
        self._next += 1
        return f"{LEMMA_PREFIX}{str(n).zfill(LEMMA_DIGITS)}"

    def reserve(self, n: int) -> None:
        self._used.add(n)


# ──────────────────────────────────────────────────────────────────────────────
# DICTIONARY LOOKUP
# ──────────────────────────────────────────────────────────────────────────────

def _pos_priority(pos_value: str) -> int:
    p = pos_value.lower().strip()
    if p == "noun":
        return 0
    if "noun" in p:
        return 1
    return 100


def find_compound_in_dict(form: str, entries: dict) -> str | None:
    candidates = []
    for lid, data in entries.items():
        for f in data["fields"].get(".FORM", []):
            token = f.split()[0] if f else ""
            if token == form:
                pos_vals = data["fields"].get(".POS", [])
                pos = pos_vals[0] if pos_vals else ""
                candidates.append((lid, _pos_priority(pos)))
                break
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


# ──────────────────────────────────────────────────────────────────────────────
# DICTIONARY ENTRY BUILDING
# ──────────────────────────────────────────────────────────────────────────────

def build_new_entry(new_id: str,
                    comp1_id: str, comp1_text_form: str,
                    comp2_id: str, comp2_text_form: str,
                    entries: dict) -> list[str]:
    """
    Build raw_lines for a new compound entry.

    .FORM is the concatenation of text forms (as they appear in corpus lines).
    .COMPOUND ref_target uses the dictionary .FORM (not the corpus form), per spec.
    """
    gloss1 = get_first_field(entries, comp1_id, ".GLOSS")
    gloss2 = get_first_field(entries, comp2_id, ".GLOSS")
    mean1  = get_first_field(entries, comp1_id, ".MEANING")
    mean2  = get_first_field(entries, comp2_id, ".MEANING")
    kana1  = get_first_field(entries, comp1_id, ".KANA")
    kana2  = get_first_field(entries, comp2_id, ".KANA")
    # Dictionary .FORM for .COMPOUND ref_target
    dict_form1 = get_first_field(entries, comp1_id, ".FORM") or comp1_text_form
    dict_form2 = get_first_field(entries, comp2_id, ".FORM") or comp2_text_form

    compound_form  = comp1_text_form + comp2_text_form
    compound_kana  = kana1 + kana2 if (kana1 or kana2) else phonemic_to_kana(compound_form)
    compound_gloss = (gloss1 + " " + gloss2).strip()
    compound_mean  = (mean1 + " " + mean2).strip()

    return [
        f"=== {new_id}",
        f".GLOSS\t{compound_gloss}",
        f".MEANING\t{compound_mean}",
        f".FORM\t{compound_form}",
        f".KANA\t{compound_kana}",
        ".POS\tnoun",
        f".COMPOUND\tref_target={comp1_id}\t{dict_form1}",
        f".COMPOUND\tref_target={comp2_id}\t{dict_form2}",
    ]


def compound_ref_lines(comp1_id: str, dict_form1: str,
                        comp2_id: str, dict_form2: str) -> list[str]:
    return [
        f".COMPOUND\tref_target={comp1_id}\t{dict_form1}",
        f".COMPOUND\tref_target={comp2_id}\t{dict_form2}",
    ]


# ──────────────────────────────────────────────────────────────────────────────
# ENTRY REGISTRATION  (add to entries dict)
# ──────────────────────────────────────────────────────────────────────────────

def register_entry(entries: dict, new_id: str, raw_lines: list[str]) -> None:
    entries[new_id] = {
        "raw_lines": list(raw_lines),
        "fields": _parse_fields(raw_lines),
    }


# ──────────────────────────────────────────────────────────────────────────────
# COMPOUND RESOLUTION  (lookup or create; handles layered pairing)
# ──────────────────────────────────────────────────────────────────────────────

def resolve_compound(comp1_id: str, comp1_text_form: str,
                     comp2_id: str, comp2_text_form: str,
                     entries: dict,
                     id_gen: IDGenerator,
                     dict_changes: dict,
                     new_dict_entries: dict) -> tuple[str, bool]:
    """
    Return (compound_lemma_id, was_new).
    Looks up, refines, or creates a dictionary entry as needed.
    """
    compound_form = comp1_text_form + comp2_text_form
    new_id = None
    was_new = False

    if DICT_SEARCH:
        new_id = find_compound_in_dict(compound_form, entries)
        if new_id and DICT_REFINE:
            existing_compound = entries[new_id]["fields"].get(".COMPOUND", [])
            if not existing_compound:
                dict_form1 = get_first_field(entries, comp1_id, ".FORM") or comp1_text_form
                dict_form2 = get_first_field(entries, comp2_id, ".FORM") or comp2_text_form
                ref_lines  = compound_ref_lines(comp1_id, dict_form1,
                                                comp2_id, dict_form2)
                entries[new_id]["raw_lines"].extend(ref_lines)
                entries[new_id]["fields"].setdefault(".COMPOUND", []).extend(
                    [f"ref_target={comp1_id}\t{dict_form1}",
                     f"ref_target={comp2_id}\t{dict_form2}"]
                )
                dict_changes[new_id] = list(entries[new_id]["raw_lines"])

    if new_id is None:
        new_id  = id_gen.next_id()
        was_new = True
        if DICT_ENTRY_CREATE:
            raw = build_new_entry(new_id,
                                  comp1_id, comp1_text_form,
                                  comp2_id, comp2_text_form,
                                  entries)
            register_entry(entries, new_id, raw)
            new_dict_entries[new_id] = list(raw)

    return new_id, was_new


# ──────────────────────────────────────────────────────────────────────────────
# GROUP DETECTION  (find blocks of consecutive lines sharing a common prefix
#                   that contain a bare-N compound marker)
# ──────────────────────────────────────────────────────────────────────────────

def _strip_disambig(tag: str) -> str:
    """Strip ;@N suffix."""
    return tag.split(";")[0]


def _is_n_at(tag: str) -> bool:
    """True for N, N;@2, N;@3, …"""
    return bool(N_AT_PAT.match(tag))


def _at_number(tag: str) -> int:
    """Return the @N number from a tag like N;@3, or 1 for plain N."""
    m = re.search(r';@(\d+)', tag)
    return int(m.group(1)) if m else 1


def get_word_form(fields: list[str]) -> str | None:
    """Return the word form (last field) if the line ends with a word."""
    if not fields:
        return None
    last = fields[-1]
    if re.match(r'^[A-Za-z]+$', last):
        return last
    return None


def get_component_lemma(fields: list[str]) -> str | None:
    """Return the component lemma (third-from-last field) on an annotated line."""
    if len(fields) >= 3 and LEMMA_PAT.match(fields[-3]):
        return fields[-3]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# COMPOUND GROUP SCANNER
# ──────────────────────────────────────────────────────────────────────────────

def _common_prefix_depth(f1: list[str], f2: list[str]) -> int:
    """Number of leading fields that are identical between two lines."""
    n = min(len(f1), len(f2))
    for i in range(n):
        if f1[i] != f2[i]:
            return i
    return n


def find_compound_groups(lines: list[str]) -> list[dict]:
    """
    Scan all lines for compound groups.

    A compound group is a maximal consecutive sequence of lines where:
    - The "marker N" field (the N without a following lemma ID) sits at the
      same column index across all lines in the group.
    - Lines 1..n each have an N-at tag (N, N;@2, …) at the marker position.
    - The first line has a plain N (no ;@N) at the marker position.

    Each group is:
        {
          'start': int,        # first line index
          'end':   int,        # last line index (inclusive)
          'marker_col': int,   # column index of the marker N
          'lines': [int,...],  # line indices
          'components': [      # one per line in the group
               {'line_idx': int,
                'at_tag': str,      # the N / N;@2 tag
                'comp_id': str,     # component lemma ID (already on line)
                'text_form': str,   # word form from corpus
               }
          ]
        }

    A group is only returned if:
    1. Every line has a component lemma ID in the expected position.
    2. The marker column has NO lemma ID already (i.e. needs insertion).
    """
    groups: list[dict] = []
    n = len(lines)
    i = 0
    while i < n:
        f = _fields(lines[i])
        # Look for a bare N (no lemma ID immediately following) that can be a
        # compound marker — meaning field[-2] is a PHON tag and field[-1] is
        # a word form (component lemma is at field[-3]).
        # We identify the marker column by finding an N-at tag that is NOT
        # immediately preceded by a lemma ID (i.e. the slot before N has no ID).
        marker_col = _find_marker_col(f)
        if marker_col is None:
            i += 1
            continue

        # The N at marker_col must be a plain N (no ;@) — it's the group opener.
        if f[marker_col] != "N":
            i += 1
            continue

        # Already has compound lemma at marker_col+1?  Skip.
        if len(f) > marker_col + 1 and LEMMA_PAT.match(f[marker_col + 1]):
            i += 1
            continue

        # Collect component info for the first line
        comp0 = _component_from_fields(f, marker_col)
        if comp0 is None:
            i += 1
            continue

        group_lines  = [i]
        components   = [{"line_idx": i, "at_tag": f[marker_col], **comp0}]

        # Extend group: look ahead for N;@2, N;@3, …
        j = i + 1
        while j < n:
            fj = _fields(lines[j])
            # Must share prefix up to marker_col
            if len(fj) <= marker_col:
                break
            if fj[:marker_col] != f[:marker_col]:
                break
            at_tag = fj[marker_col]
            if not _is_n_at(at_tag) or at_tag == "N":
                break
            # The tag at marker_col must NOT already be followed by a lemma
            if len(fj) > marker_col + 1 and LEMMA_PAT.match(fj[marker_col + 1]):
                break
            compj = _component_from_fields(fj, marker_col)
            if compj is None:
                break
            group_lines.append(j)
            components.append({"line_idx": j, "at_tag": at_tag, **compj})
            j += 1

        if len(group_lines) < 2:
            i += 1
            continue

        groups.append({
            "start"     : i,
            "end"       : j - 1,
            "marker_col": marker_col,
            "lines"     : group_lines,
            "components": components,
        })
        i = j   # advance past the whole group

    return groups


def _find_marker_col(fields: list[str]) -> int | None:
    """
    Find the column of a bare compound-marker N.

    Pattern on each component line:
        [...prefix..., N or N;@k, comp_lemma, PHON_TAG, word_form]
                        ^marker_col

    We want the *outermost* N-at tag that has no lemma immediately before it.
    Scan right to left to find the rightmost N-at tag whose left neighbour
    is NOT a lemma ID (i.e. the slot is empty / contains a syntactic tag).
    """
    n = len(fields)
    # Need at least: marker_N, comp_lemma, phon_tag, word_form → 4 fields min
    if n < 4:
        return None
    # The word form must be at [-1], phon tag at [-2], comp lemma at [-3]
    if not re.match(r'^[A-Za-z]+$', fields[-1]):
        return None
    if fields[-2] not in PHON_TAGS:
        return None
    if not LEMMA_PAT.match(fields[-3]):
        return None

    # Now find the N-at tag at position -4 or further left
    # We want the first (leftmost) N-at that has NO lemma to its immediate left.
    for col in range(n - 4, -1, -1):
        tag = fields[col]
        if not _is_n_at(tag):
            continue
        # Check: position col-1 must NOT be a lemma ID
        if col > 0 and LEMMA_PAT.match(fields[col - 1]):
            continue
        return col

    return None


def _component_from_fields(fields: list[str], marker_col: int) -> dict | None:
    """
    Given fields and the marker column, extract component info:
        comp_id:   lemma ID at marker_col+1 (after possible inline N-expansion)
                   or at the standard -3 position.
        text_form: word form at -1.
    After marker_col the pattern should be:
        [N-at-tag, comp_lemma, phon_tag, word_form]
    i.e. positions marker_col+1 should be the comp_lemma (or N-at then comp_lemma
    for nested compounds — but at this layer we only look one level in).
    """
    n = len(fields)
    # Standard: -3 is comp_lemma
    comp_id   = fields[-3] if n >= 3 and LEMMA_PAT.match(fields[-3]) else None
    text_form = fields[-1] if n >= 1 else None
    if comp_id is None or text_form is None:
        return None
    return {"comp_id": comp_id, "text_form": text_form}


# ──────────────────────────────────────────────────────────────────────────────
# LAYERED PAIRING
# ──────────────────────────────────────────────────────────────────────────────

def pair_components_layered(components: list[dict],
                             entries: dict,
                             id_gen: IDGenerator,
                             dict_changes: dict,
                             new_dict_entries: dict) -> list[tuple[str, str, int]]:
    """
    For a group of k components, pair them left-to-right in layers.

    Layer 0: (comp0, comp1) → intermediate_id_01
             (comp2)        → stays as-is
             (comp3)        → stays as-is
    Layer 1: (intermediate_id_01, comp2) → intermediate_id_012
             (comp3)        → stays as-is
    …until only one element remains (the outermost compound ID).

    Returns a list of (compound_id, compound_text_form, layer) tuples,
    one per intermediate result — the last entry is the outermost compound.
    Assumes components is sorted by @N order (already the case from scan).
    """
    # Each slot: (id, text_form)
    slots = [(c["comp_id"], c["text_form"]) for c in components]

    results: list[tuple[str, str, int]] = []
    layer = 0
    while len(slots) > 1:
        new_slots = []
        k = 0
        while k < len(slots):
            if k + 1 < len(slots):
                id1, form1 = slots[k]
                id2, form2 = slots[k + 1]
                cid, was_new = resolve_compound(
                    id1, form1, id2, form2,
                    entries, id_gen, dict_changes, new_dict_entries
                )
                new_slots.append((cid, form1 + form2))
                results.append((cid, form1 + form2, layer))
                k += 2
            else:
                new_slots.append(slots[k])
                k += 1
        slots = new_slots
        layer += 1

    return results


# ──────────────────────────────────────────────────────────────────────────────
# LINE INSERTION
# ──────────────────────────────────────────────────────────────────────────────

def insert_compound_id_into_line(line: str, marker_col: int,
                                  compound_id: str) -> str:
    """Insert compound_id at marker_col+1 (after the N-at tag)."""
    f = _fields(line)
    f.insert(marker_col + 1, compound_id)
    return _join(f)


# ──────────────────────────────────────────────────────────────────────────────
# NP EXPANSION  (optional: insert grouping N before N;@2 siblings under NP)
# ──────────────────────────────────────────────────────────────────────────────

def np_expand(lines: list[str]) -> tuple[list[str], list[tuple]]:
    """
    Detect consecutive line-groups where:
    - All lines share a common prefix ending in NP.
    - Their immediate direct child tags are all N-at (N, N;@2, N;@3, …).
    - None of these lines already has a marker N (i.e. no N immediately
      before the N-at tag in the fields).

    For such groups, insert N before each N-at tag, converting e.g.:
        ...,NP,N,<comp_id>,LOG,form
        ...,NP,N;@2,<comp_id>,LOG,form
    to:
        ...,NP,N,N,<comp_id>,LOG,form
        ...,NP,N,N;@2,<comp_id>,LOG,form

    Returns (new_lines, expansion_log) where expansion_log is a list of
    (line_idx, original_line, new_line).
    """
    new_lines = list(lines)
    expansion_log: list[tuple] = []
    n = len(lines)
    i = 0
    while i < n:
        f = _fields(lines[i])
        # Find the NP position: look for a field 'NP' such that the next
        # field is an N-at tag (N or N;@k) with NO marker N before it.
        np_col = _find_np_expansion_col(f)
        if np_col is None:
            i += 1
            continue

        # Verify line[i] starts a group: N-at tag at np_col+1 == 'N' (plain)
        at_col = np_col + 1
        if at_col >= len(f) or f[at_col] != "N":
            i += 1
            continue

        # Check no marker N already sitting before the N-at
        if at_col > 0 and f[at_col - 1] == "N":
            i += 1
            continue

        # Check it really needs expansion: must have comp_lemma at at_col+1
        if at_col + 1 >= len(f) or not LEMMA_PAT.match(f[at_col + 1]):
            i += 1
            continue

        # Collect the group: consecutive lines sharing prefix[0..np_col]
        group_idxs = [i]
        j = i + 1
        while j < n:
            fj = _fields(lines[j])
            if fj[:np_col + 1] != f[:np_col + 1]:
                break
            at_tag = fj[np_col + 1] if len(fj) > np_col + 1 else ""
            if not _is_n_at(at_tag) or at_tag == "N":
                break
            # Also must have comp_lemma right after the N-at tag
            if np_col + 2 >= len(fj) or not LEMMA_PAT.match(fj[np_col + 2]):
                break
            # Must not already have a marker N before N-at
            if np_col > 0 and fj[np_col] == "N":
                break
            group_idxs.append(j)
            j += 1

        if len(group_idxs) < 2:
            i += 1
            continue

        # All members confirmed — insert N before each N-at tag
        for idx in group_idxs:
            orig = new_lines[idx]
            fld  = _fields(orig)
            # Insert N at at_col (before the existing N-at tag)
            fld.insert(at_col, "N")
            new_line = _join(fld)
            new_lines[idx] = new_line
            expansion_log.append((idx, orig, new_line))

        i = j

    return new_lines, expansion_log


def _find_np_expansion_col(fields: list[str]) -> int | None:
    """
    Find a column col such that fields[col] == 'NP' and fields[col+1] is an
    N-at tag that is NOT already preceded by a marker N.
    Returns the rightmost such col, or None.
    """
    n = len(fields)
    for col in range(n - 2, -1, -1):
        if fields[col] != "NP":
            continue
        at_tag = fields[col + 1]
        if not _is_n_at(at_tag):
            continue
        # Must have a comp_lemma after the N-at
        if col + 2 >= n or not LEMMA_PAT.match(fields[col + 2]):
            continue
        return col
    return None


# ──────────────────────────────────────────────────────────────────────────────
# PROCESS A SINGLE TEXT FILE
# ──────────────────────────────────────────────────────────────────────────────

def process_text_file(path: str,
                      entries: dict,
                      id_gen: IDGenerator,
                      dict_changes: dict,
                      new_dict_entries: dict) -> tuple:
    """
    Returns (new_lines, revised_log, stats).
    revised_log: list of (group_start_line_1based, original_lines[], new_lines[])
    """
    with open(path, encoding="utf-8") as f:
        orig_lines = f.read().splitlines()

    working = list(orig_lines)
    revised_log: list[tuple] = []

    stats = {
        "groups_detected": 0,
        "new_ids_created": 0,
        "dict_entries_added": 0,
        "np_expansions": 0,
    }

    # Step 0: optional NP expansion
    if NP_EXPANSION:
        working, expansion_log = np_expand(working)
        stats["np_expansions"] += len(expansion_log)
        for idx, orig, new in expansion_log:
            revised_log.append((idx + 1, [orig], [new], "np_expansion"))

    # Step 1: iterative compound detection (repeat until no new groups found)
    # because inserting compound IDs at one layer enables the next layer.
    max_iterations = 20
    for iteration in range(max_iterations):
        groups = find_compound_groups(working)
        if not groups:
            break

        made_changes = False

        for group in groups:
            marker_col = group["marker_col"]
            components = group["components"]

            # Pair components in layers to get the outermost compound ID
            layer_results = pair_components_layered(
                components, entries, id_gen, dict_changes, new_dict_entries
            )
            if not layer_results:
                continue

            # The outermost compound ID (last layer result)
            outermost_id = layer_results[-1][0]

            # Count new IDs created
            for cid, _, layer in layer_results:
                if cid in new_dict_entries:
                    stats["dict_entries_added"] += 1
                stats["new_ids_created"] += (1 if cid in new_dict_entries else 0)

            # Insert the outermost compound ID into every line in the group
            orig_group_lines  = [working[idx] for idx in group["lines"]]
            new_group_lines   = []
            for idx in group["lines"]:
                new_line = insert_compound_id_into_line(
                    working[idx], marker_col, outermost_id
                )
                working[idx] = new_line
                new_group_lines.append(new_line)

            revised_log.append((
                group["start"] + 1,
                orig_group_lines,
                new_group_lines,
                f"compound layer {iteration}",
            ))
            stats["groups_detected"] += 1
            made_changes = True

        if not made_changes:
            break

    return working, revised_log, stats


# ──────────────────────────────────────────────────────────────────────────────
# DICTIONARY SERIALISATION
# ──────────────────────────────────────────────────────────────────────────────

def _entry_block(raw_lines: list) -> str:
    clean = [l for l in raw_lines
             if l.strip() != "" and not re.match(r"^-{10,}$", l.strip())]
    return SEPARATOR + "\n" + "\n".join(clean) + "\n\n"


def serialise_dict(entries: dict, original_path: str) -> str:
    original_order = []
    if os.path.isfile(original_path):
        with open(original_path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^===\s+([A-Za-z]\d+[a-z]*)\s*$", line)
                if m:
                    original_order.append(m.group(1))

    seen  = set()
    parts = []

    for lid in original_order:
        if lid in entries and lid not in seen:
            seen.add(lid)
            parts.append(_entry_block(entries[lid]["raw_lines"]))

    for lid, data in entries.items():
        if lid not in seen:
            parts.append(_entry_block(data["raw_lines"]))

    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    entries   = parse_dictionary(DICT_FILE)
    used_nums = all_numeric_ids(entries)
    id_gen    = IDGenerator(used_nums)

    dict_changes: dict     = {}
    new_dict_entries: dict = {}

    if not os.path.isdir(TEXT_FOLDER):
        print(f"[ERROR] Input folder not found: {TEXT_FOLDER}")
        return

    txt_files = sorted(Path(TEXT_FOLDER).glob("*.txt"))
    if not txt_files:
        print(f"[WARN] No .txt files found in: {TEXT_FOLDER}")

    total_files        = 0
    total_groups       = 0
    total_new_ids      = 0
    total_dict_added   = 0
    total_np_expansions = 0
    output_files_saved: list[str] = []

    all_revised_blocks: list[str] = []

    for txt_path in txt_files:
        if not txt_path.is_file():
            continue
        total_files += 1

        new_lines, revised_log, stats = process_text_file(
            str(txt_path), entries, id_gen, dict_changes, new_dict_entries
        )

        total_groups        += stats["groups_detected"]
        total_new_ids       += stats["new_ids_created"]
        total_dict_added    += stats["dict_entries_added"]
        total_np_expansions += stats["np_expansions"]

        if OVERWRITE_SOURCE:
            out_path = str(txt_path)
        else:
            out_path = os.path.join(OUTPUT_FOLDER, txt_path.name)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        output_files_saved.append(out_path)

        if SAVE_REVISED and revised_log:
            doc_header = (
                f"\n{'=' * 60}\n"
                f"  Document: {txt_path.name}\n"
                f"{'=' * 60}"
            )
            all_revised_blocks.append(doc_header)
            for (start_lno, orig_ls, new_ls, label) in revised_log:
                block_lines = [f"  [Type: {label}]"]
                for k, (ol, nl) in enumerate(zip(orig_ls, new_ls)):
                    lno = start_lno + k
                    block_lines.append(f"  Line {lno} (original): {ol}")
                    block_lines.append(f"  Line {lno} (revised) : {nl}")
                all_revised_blocks.append("\n".join(block_lines))

    if SAVE_REVISED and all_revised_blocks:
        rev_path = os.path.join(OUTPUT_FOLDER, "all_revised_lines.txt")
        with open(rev_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(all_revised_blocks) + "\n")
        output_files_saved.append(rev_path)

    if OVERWRITE_SOURCE:
        dict_out = DICT_FILE
    else:
        dict_stem = Path(DICT_FILE).stem
        dict_ext  = Path(DICT_FILE).suffix
        dict_out  = os.path.join(OUTPUT_FOLDER, f"{dict_stem}{dict_ext}")

    with open(dict_out, "w", encoding="utf-8") as f:
        f.write(serialise_dict(entries, DICT_FILE))
    output_files_saved.append(dict_out)

    # Revised dictionary (refined + new entries only)
    if SAVE_REVISED and (dict_changes or new_dict_entries):
        rev_dict_lines: list[str] = []
        if dict_changes:
            rev_dict_lines.append("# ====  REFINED ENTRIES  ====\n")
            for lid, raw in dict_changes.items():
                clean = [l for l in raw
                         if l.strip() != "" and not re.match(r"^-{10,}$", l.strip())]
                rev_dict_lines.append("\n".join(clean) + "\n\n")
        if new_dict_entries:
            rev_dict_lines.append("# ====  NEW ENTRIES  ====\n")
            for lid, raw in new_dict_entries.items():
                clean = [l for l in raw
                         if l.strip() != "" and not re.match(r"^-{10,}$", l.strip())]
                rev_dict_lines.append(SEPARATOR + "\n" + "\n".join(clean) + "\n\n")
        rev_dict_path = os.path.join(
            OUTPUT_FOLDER,
            f"{Path(DICT_FILE).stem}_revised{Path(DICT_FILE).suffix}"
        )
        with open(rev_dict_path, "w", encoding="utf-8") as f:
            f.write("".join(rev_dict_lines))
        output_files_saved.append(rev_dict_path)

    print()
    print("=" * 55)
    print("  PROCESSING SUMMARY")
    print("=" * 55)
    print(f"  Files processed             : {total_files}")
    print(f"  Compound groups resolved    : {total_groups}")
    print(f"  New lemma IDs created       : {total_new_ids}")
    print(f"  Dictionary entries added    : {total_dict_added}")
    print(f"  NP expansions applied       : {total_np_expansions}")
    print(f"  Source files overwritten    : {OVERWRITE_SOURCE}")
    print(f"  Output files saved          : {len(output_files_saved)}")
    for p in output_files_saved:
        print(f"    -> {p}")
    print("=" * 55)
    print()


if __name__ == "__main__":
    print("compound_lemma_processor_2.0.0")
    print("=" * 55)
    print(f"  Text folder   : {TEXT_FOLDER}")
    print(f"  Dictionary    : {DICT_FILE}")
    print(f"  Output folder : {OUTPUT_FOLDER}")
    print(f"  NP expansion  : {NP_EXPANSION}")
    print(f"  Dict search   : {DICT_SEARCH}")
    print(f"  Dict refine   : {DICT_REFINE}")
    print(f"  Create entries: {DICT_ENTRY_CREATE}")
    print(f"  Overwrite src : {OVERWRITE_SOURCE}")
    print(f"  ID prefix     : {LEMMA_PREFIX}  digits={LEMMA_DIGITS}  start>={LEMMA_START}")
    print("=" * 55)
    print()
    main()
