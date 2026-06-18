#!/usr/bin/env python3
"""
mk_lemma_processor.py
=====================
Finds L099999 occurrences in text files, replaces them with new unique IDs,
creates corresponding makura-kotoba dictionary entries, and optionally
normalises existing makura-kotoba entries that are missing .COMPOUND /
.MKTARGETNEW lines.
"""

# ══════════════════════════════════════════════════════════════════════════════
#  USER SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

# ── Paths ─────────────────────────────────────────────────────────────────────
TEXT_FOLDER       =    r""      # folder that contains .txt files to process
DICT_FILE         =    r""      # path to the dictionary file
OUTPUT_FOLDER     =    r""    # folder for processed output

# ── Output behaviour ──────────────────────────────────────────────────────────
OVERWRITE_SOURCE = False  # True  → overwrite source .txt files in-place
                           # False → write *_processed.txt to OUTPUT_FOLDER

# ── Lemma ID settings ─────────────────────────────────────────────────────────
LEMMA_PREFIX = "L"   # prefix for newly generated IDs (L, N, F, T, …)
LEMMA_DIGITS = 6     # zero-padded width  (6 → L000001)
LEMMA_START  = 20501     # minimum numeric value for new IDs

# ── Target ID to replace ──────────────────────────────────────────────────────
TARGET_ID      = "L099999"   # the exact token to hunt for
TARGET_NUMERIC = "099999"    # numeric part that must match exactly

# ── Dictionary entry creation ─────────────────────────────────────────────────
CREATE_DICT_ENTRIES = True   # True  → add new MK entries to the dictionary
                              # False → skip all dictionary modifications

# ── .MKTARGETNEW settings ─────────────────────────────────────────────────────────
RELATED_TOP_N = 1   # how many top-frequency related words to emit
                     # (1 = most frequent only, 2 = top-2, etc.)

# ── Normalise existing makura-kotoba entries ──────────────────────────────────
NORMALISE_EXISTING = True   # True  → scan existing MK entries missing
                             #         .COMPOUND/.MKTARGETNEW and fill them in
                             # False → skip normalisation

# ── Report filenames (all saved inside OUTPUT_FOLDER) ─────────────────────────
REPORT_MODIFIED_LINES = "report_modified_lines.txt"
REPORT_DICT_ADDED     = "report_dict_added.txt"
REPORT_DICT_MODIFIED  = "report_dict_modified.txt"

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
#  KANA CONVERSION TABLE
#  Source: Phonemic transcription to historical kana spelling conversion list
# ══════════════════════════════════════════════════════════════════════════════

_KANA_RAW: list[tuple[str, str]] = [
    # GROUP 1 — three-character syllables first
    ("pye", "ヘ"), ("pwi", "ヒ"),
    ("bye", "ベ"), ("bwi", "ビ"),
    ("kye", "ケ"), ("kwi", "キ"), ("kwo", "コ"),
    ("gye", "ゲ"), ("gwi", "ギ"), ("gwo", "ゴ"),
    ("mye", "メ"), ("mwi", "ミ"), ("mwo", "モ"),
    ("two", "ト"), ("dwo", "ド"),
    ("swo", "ソ"), ("zwo", "ゾ"),
    ("nwo", "ノ"), ("ywo", "ヨ"), ("rwo", "ロ"),
    # GROUP 1 — two-character syllables
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
    # GROUP 2
    ("ye", "エ"), ("wi", "ヰ"), ("wo", "ヲ"),
    # GROUP 3 — bare vowels (shortest; must come last)
    ("a", "ア"), ("i", "イ"), ("u", "ウ"), ("o", "オ"), ("e", "エ"),
]

_KANA_TABLE: list[tuple[str, str]] = sorted(_KANA_RAW, key=lambda x: -len(x[0]))


def phonemic_to_kana(form: str) -> str:
    """
    Convert a phonemic transcription string to historical katakana using a
    greedy longest-match left-to-right scan.  Unrecognised characters are
    wrapped in ⟨…⟩ to flag them.
    """
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


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS / REGEX
# ══════════════════════════════════════════════════════════════════════════════

ENTRY_SEP   = "---------------------------------------------------"
# Matches  === L000012  or  === L000006a  etc.
ENTRY_HEAD_RE = re.compile(r'^=== ([A-Za-z]\d+[a-z]*)$')
# Matches any lemma-like token: letter(s) + digits + optional letter suffix
LEMMA_RE      = re.compile(r'^[A-Za-z]\d+[a-z]*$')
# "Word form" field: purely alphabetic (no digits, no punctuation)
WORD_FORM_RE  = re.compile(r'^[A-Za-z]+$')
# Phoneme/pronunciation tags in corpus lines
PHON_TAGS     = {"PHON", "LOG", "NLOG","PHON-ON", "PHON-KUN", "PLOG"}
# Syntactic tags that mark the immediate post-block word (Q1)
# A valid "word-ending" line is one whose LAST field is purely alphabetic.


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY  —  data structures
# ══════════════════════════════════════════════════════════════════════════════

class DictEntry:
    """One parsed dictionary entry."""

    __slots__ = ("eid", "lines")

    def __init__(self, eid: str, lines: list[str]):
        self.eid   = eid           # e.g. "L000012"
        self.lines = lines         # raw text lines WITHOUT the leading sep

    # ── field accessors ───────────────────────────────────────────────────────

    def get_field(self, tag: str) -> str | None:
        """Return the value of the FIRST occurrence of .TAG, or None."""
        prefix = f".{tag}\t"
        for ln in self.lines:
            if ln.startswith(prefix):
                return ln[len(prefix):].rstrip("\r\n")
        return None

    def has_tag(self, tag: str) -> bool:
        prefix = f".{tag}"
        return any(ln.startswith(prefix) for ln in self.lines)

    def get_all_fields(self, tag: str) -> list[str]:
        """Return values of ALL occurrences of .TAG."""
        prefix = f".{tag}\t"
        return [ln[len(prefix):].rstrip("\r\n") for ln in self.lines
                if ln.startswith(prefix)]

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_text(self) -> str:
        """
        Serialise as:
            ---------------------------------------------------\n
            === <id>\n
            .<TAG>\t<VALUE>\n
            …
            \n
        """
        body = "".join(
            ln if ln.endswith("\n") else ln + "\n"
            for ln in self.lines
        )
        return ENTRY_SEP + "\n" + f"=== {self.eid}\n" + body


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY  —  loader
# ══════════════════════════════════════════════════════════════════════════════

def load_dictionary(dict_path: str) -> tuple[list[DictEntry], set[int]]:
    """
    Parse the dictionary file into a list of DictEntry objects.
    Also returns the set of ALL numeric parts already in use (including
    entries like L000006a → numeric 6 is reserved).

    Returns (entries, used_numeric_ints).
    """
    entries: list[DictEntry] = []
    used_nums: set[int]      = set()

    if not os.path.isfile(dict_path):
        print(f"[WARNING] Dictionary file not found: {dict_path}")
        return entries, used_nums

    with open(dict_path, encoding="utf-8") as fh:
        raw = fh.read()

    # Split on separator; first chunk is pre-amble (may be empty)
    blocks = raw.split(ENTRY_SEP)
    for block in blocks[1:]:          # skip preamble
        lines = block.lstrip("\r\n").splitlines(keepends=True)
        if not lines:
            continue
        # First line of block should be  === <ID>
        header = lines[0].rstrip("\r\n")
        m = ENTRY_HEAD_RE.match(header)
        if not m:
            continue
        eid = m.group(1)
        num = int(re.search(r'\d+', eid).group())
        used_nums.add(num)

        # Body: everything after the header line, strip trailing blank lines
        body_lines = lines[1:]
        # Remove leading blank lines
        while body_lines and body_lines[0].strip() == "":
            body_lines.pop(0)
        # Ensure exactly one trailing blank line
        while body_lines and body_lines[-1].strip() == "":
            body_lines.pop()
        body_lines.append("\n")

        entries.append(DictEntry(eid, body_lines))

    return entries, used_nums


def dict_by_id(entries: list[DictEntry]) -> dict[str, DictEntry]:
    return {e.eid: e for e in entries}


def save_dictionary(entries: list[DictEntry], path: str) -> None:
    """Write all entries to *path* in sorted numeric order."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def sort_key(e: DictEntry):
        m = re.search(r'\d+', e.eid)
        n = int(m.group()) if m else 0
        suffix = re.sub(r'[^a-z]', '', e.eid.lower())
        return (n, suffix)

    sorted_entries = sorted(entries, key=sort_key)
    with open(path, "w", encoding="utf-8") as fh:
        for e in sorted_entries:
            fh.write(e.to_text())


# ══════════════════════════════════════════════════════════════════════════════
#  ID GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class IDGenerator:
    """Produces unique numeric IDs that never clash with existing ones."""

    def __init__(self, used_ints: set[int], start: int = LEMMA_START):
        self._used: set[int] = set(used_ints)
        self._next: int      = max(start, 1)

    def next_id(self, prefix: str = LEMMA_PREFIX) -> tuple[str, int]:
        """Return (full_id_string, numeric_value)."""
        while self._next in self._used:
            self._next += 1
        n = self._next
        self._used.add(n)
        self._next += 1
        num_str = str(n).zfill(LEMMA_DIGITS)
        return f"{prefix}{num_str}", n

    def reserve(self, n: int) -> None:
        self._used.add(n)


# ══════════════════════════════════════════════════════════════════════════════
#  CORPUS LINE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def parse_fields(line: str) -> list[str]:
    return line.rstrip("\r\n").split(",")


def line_ends_with_word(fields: list[str]) -> bool:
    """
    True when the last field is purely alphabetic (a real word form).
    Lines ending in '*' or a number-like token are excluded.
    """
    if not fields:
        return False
    last = fields[-1]
    return bool(WORD_FORM_RE.match(last))


def tag_before_target(fields: list[str], target: str) -> str | None:
    """Return the field immediately before *target* in *fields*, or None."""
    for i, f in enumerate(fields):
        if f == target and i > 0:
            return fields[i - 1]
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  COMPOUND INFO  (sub-components of an MK block)
# ══════════════════════════════════════════════════════════════════════════════

def build_compound_info(block_lines: list[str],
                        own_id: str) -> list[tuple[str, str]]:
    """
    Extract (lemma_id, phon) pairs for the TOP-LEVEL compound components.

    Strategy
    --------
    Walk every line in the block.  After TARGET_ID (and its preceding tag),
    the remaining fields form a small sub-tree.  We collect the FIRST
    lemma token on each line that appears at the top-level slot immediately
    after TARGET_ID's tag.  Sub-components of that token (nested lemmas on
    the same line) contribute their phon values to their immediate parent,
    not to the top-level list.

    Simplified rule that matches the reference output:
    • On each block line, collect lemma IDs that appear after TARGET_ID.
    • The first such ID on the line is a top-level compound component.
    • Its phon is built by concatenating the LOG/PHON values of ALL
      subsequent lemma sub-nodes on the same line (depth-first left scan).
    • If the same top-level ID recurs on another line, append that line's
      phon to the running total for that ID.
    • Skip TARGET_ID and own_id at every level.
    • De-duplicate top-level IDs while preserving first-seen order.
    """
    seen_order:  list[str]      = []   # ordered top-level lemma IDs
    phon_by_id:  dict[str, str] = {}   # lemma_id → concatenated phon

    for raw in block_lines:
        fields = parse_fields(raw)

        # Find the position of TARGET_ID in this line
        try:
            tid_pos = fields.index(TARGET_ID)
        except ValueError:
            continue

        # Everything after TARGET_ID is the compound sub-tree for this line
        sub = fields[tid_pos + 1:]

        # Collect ALL lemma tokens and their following PHON/LOG values
        # The first lemma token is the top-level component for this line.
        top_id   = None
        line_phon = ""

        i = 0
        while i < len(sub):
            f = sub[i]
            if LEMMA_RE.match(f) and f != own_id:
                if top_id is None:
                    top_id = f
                # Collect the PHON/LOG value for this sub-node
                for j in range(i + 1, min(i + 3, len(sub))):
                    if sub[j] in PHON_TAGS and j + 1 < len(sub):
                        line_phon += sub[j + 1]
                        break
            i += 1

        if top_id is None:
            continue

        if top_id not in phon_by_id:
            seen_order.append(top_id)
            phon_by_id[top_id] = line_phon
        else:
            phon_by_id[top_id] += line_phon

    return [(lid, phon_by_id[lid]) for lid in seen_order]


# ══════════════════════════════════════════════════════════════════════════════
#  RELATED WORD  (Q1 – walk forward past non-word lines)
# ══════════════════════════════════════════════════════════════════════════════

def find_related_words(block_end_idx: int,
                       all_lines: list[str],
                       top_n: int) -> list[tuple[str, str]]:
    """
    Starting from the line AFTER block_end_idx, skip lines that do NOT
    end with a real word.  The first line that DOES end with a real word
    is the source of the related-word entry.

    A "real word ending" means:
      - The last field is purely alphabetic (WORD_FORM_RE).
      - The third-to-last field is a LEMMA_RE token (the lemma ID).

    Returns a list of up to *top_n* (lemma_id, phon) pairs.
    In the single-occurrence case this list has exactly one element.

    When called from the normalise path (multiple occurrences across files),
    *all_lines* is a flat list of all corpus lines from ALL files; the caller
    must supply the correct block_end_idx into that flat list.
    """
    results: list[tuple[str, str]] = []
    i = block_end_idx + 1
    while i < len(all_lines):
        fields = parse_fields(all_lines[i])
        if line_ends_with_word(fields) and len(fields) >= 3:
            # third-to-last must be a lemma ID
            cand_lemma = fields[-3] if len(fields) >= 3 else ""
            cand_phon  = fields[-1]
            if LEMMA_RE.match(cand_lemma):
                results.append((cand_lemma, cand_phon))
                if len(results) >= top_n:
                    break
                # if top_n > 1, keep walking
                i += 1
                continue
        # Non-word line → skip and keep looking
        i += 1
        # But if we already have at least one result stop here
        # (the block's related word is the very next word-bearing line)
        if results:
            break

    return results


def find_related_words_multi(block_end_indices: list[int],
                              all_lines: list[str],
                              top_n: int) -> list[tuple[str, str]]:
    """
    For normalisation: collect related-word candidates from multiple block
    occurrences, rank by frequency, return top *top_n*.
    """
    freq: Counter             = Counter()
    seen: dict[str, str]      = {}   # phon → lemma_id

    for end_idx in block_end_indices:
        for lid, phon in find_related_words(end_idx, all_lines, top_n=1):
            freq[phon] += 1
            seen.setdefault(phon, lid)

    top = [(seen[ph], ph) for ph, _ in freq.most_common(top_n) if ph in seen]
    return top


# ══════════════════════════════════════════════════════════════════════════════
#  BUILD A NEW DICTIONARY ENTRY
# ══════════════════════════════════════════════════════════════════════════════

def build_mk_entry(new_id: str,
                   compound_info: list[tuple[str, str]],
                   related_info: list[tuple[str, str]]) -> DictEntry:
    """
    Build a makura-kotoba DictEntry.

    .FORM  = concatenation of all phon strings in compound_info
    .KANA  = phonemic_to_kana(.FORM)
    .MEANING = [MK for <related phon(s)>]
    """
    form    = "".join(ph for _, ph in compound_info if ph)
    kana    = phonemic_to_kana(form)
    rel_ph  = ", ".join(ph for _, ph in related_info) if related_info else "???"
    meaning = f"[MK for {rel_ph}]"

    body: list[str] = []
    body.append(f".GLOSS\tEPITHET\n")
    body.append(f".MEANING\t{meaning}\n")
    body.append(f".FORM\t{form}\n")
    body.append(f".KANA\t{kana}\n")
    body.append(f".POS\tmakura kotoba\n")
    for lid, ph in compound_info:
        body.append(f".COMPOUND\tref_target={lid}\t{ph}\n")
    for lid, ph in related_info:
        body.append(f".MKTARGETNEW\tref_target={lid}\t{ph}\n")
    body.append("\n")

    return DictEntry(new_id, body)


# ══════════════════════════════════════════════════════════════════════════════
#  NORMALISE EXISTING ENTRIES  (Q2 / feature 2.2)
# ══════════════════════════════════════════════════════════════════════════════

def normalise_entry(entry: DictEntry,
                    all_lines: list[str],
                    top_n: int) -> tuple[bool, list[str]]:
    """
    If *entry* is a makura-kotoba entry missing .COMPOUND or .MKTARGETNEW,
    search for its ID in *all_lines* and fill in the missing parts.

    Returns (changed: bool, description_lines: list[str]).
    The description_lines are used in the report (Q2).
    """
    if entry.get_field("POS") != "makura kotoba":
        return False, []
    has_compound = entry.has_tag("COMPOUND")
    has_related  = entry.has_tag("RELATED")
    if has_compound and has_related:
        return False, []

    eid = entry.eid

    # Find all occurrences of this ID in the corpus
    block_lines: list[str]  = []
    block_end_indices: list[int] = []

    i = 0
    while i < len(all_lines):
        fields = parse_fields(all_lines[i])
        if eid in fields:
            start = i
            while i < len(all_lines) and eid in parse_fields(all_lines[i]):
                block_lines.append(all_lines[i])
                i += 1
            block_end_indices.append(i - 1)
        else:
            i += 1

    if not block_lines:
        return False, []

    added: list[str] = []

    if not has_compound:
        compound_info = build_compound_info(block_lines, own_id=eid)
        # Strip any existing (probably blank) compound lines
        entry.lines = [ln for ln in entry.lines if not ln.startswith(".COMPOUND")]
        # Insert before the trailing blank line
        ins_lines = [f".COMPOUND\tref_target={lid}\t{ph}\n"
                     for lid, ph in compound_info]
        _insert_before_blank(entry, ins_lines)
        added.extend(f".COMPOUND\tref_target={lid}\t{ph}" for lid, ph in compound_info)

    if not has_related:
        related_info = find_related_words_multi(block_end_indices, all_lines, top_n)
        entry.lines = [ln for ln in entry.lines if not ln.startswith(".MKTARGETNEW")]
        ins_lines = [f".MKTARGETNEW\tref_target={lid}\t{ph}\n"
                     for lid, ph in related_info]
        _insert_before_blank(entry, ins_lines)
        added.extend(f".MKTARGETNEW\tref_target={lid}\t{ph}" for lid, ph in related_info)

        # Also update .MEANING if it still says [MK for ???]
        meaning = entry.get_field("MEANING") or ""
        if "???" in meaning and related_info:
            rel_ph = ", ".join(ph for _, ph in related_info)
            new_meaning = f"[MK for {rel_ph}]"
            entry.lines = [
                f".MEANING\t{new_meaning}\n" if ln.startswith(".MEANING\t") else ln
                for ln in entry.lines
            ]

    return bool(added), added


def _insert_before_blank(entry: DictEntry, new_lines: list[str]) -> None:
    """Insert *new_lines* into entry.lines just before the trailing blank line."""
    if entry.lines and entry.lines[-1].strip() == "":
        entry.lines[-1:] = new_lines + ["\n"]
    else:
        entry.lines.extend(new_lines)
        entry.lines.append("\n")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def process_files() -> None:

    # ── counters ──────────────────────────────────────────────────────────────
    total_files        = 0
    total_replacements = 0
    total_new_ids      = 0
    total_dict_added   = 0
    total_normalized   = 0
    output_files_saved: list[str] = []

    # ── output dirs ───────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    if not OVERWRITE_SOURCE:
        dict_out_dir = os.path.join(OUTPUT_FOLDER, "dictionary_processed")
        os.makedirs(dict_out_dir, exist_ok=True)

    # ── load dictionary ───────────────────────────────────────────────────────
    entries, used_ints = load_dictionary(DICT_FILE)
    id_gen = IDGenerator(used_ints, start=LEMMA_START)
    by_id  = dict_by_id(entries)

    # Also reserve all numeric parts found in text files
    if os.path.isdir(TEXT_FOLDER):
        for fname in os.listdir(TEXT_FOLDER):
            if fname.endswith(".txt"):
                with open(os.path.join(TEXT_FOLDER, fname), encoding="utf-8") as fh:
                    for line in fh:
                        for m in re.finditer(r'[A-Za-z](\d+)[a-z]*', line):
                            id_gen.reserve(int(m.group(1)))

    # ── read all text files ───────────────────────────────────────────────────
    if not os.path.isdir(TEXT_FOLDER):
        sys.exit(f"[ERROR] TEXT_FOLDER '{TEXT_FOLDER}' does not exist.")

    txt_files = sorted(f for f in os.listdir(TEXT_FOLDER) if f.endswith(".txt"))
    # all_file_lines: fname → list[str]  (raw lines, may be mutated during pass 1)
    all_file_lines: dict[str, list[str]] = {}
    for fname in txt_files:
        with open(os.path.join(TEXT_FOLDER, fname), encoding="utf-8") as fh:
            all_file_lines[fname] = fh.readlines()

    # flat list for normalisation look-ups (read-only view, rebuilt after pass 1)
    def flat_lines() -> list[str]:
        result = []
        for fn in txt_files:
            result.extend(all_file_lines[fn])
        return result

    # ── report containers ─────────────────────────────────────────────────────
    report_modified:   list[tuple]      = []  # (fname, lineno, old, new)
    report_added:      list[DictEntry]  = []
    report_normalized: list[tuple]      = []  # (eid, [added_lines])

    # form_cache: .FORM value → new_id  (Q3 – reuse same ID for same form)
    form_cache: dict[str, str] = {}

    # ══════════════════════════════════════════════════════════════════════════
    #  PASS 1 – replace TARGET_ID in text files, build new dict entries
    # ══════════════════════════════════════════════════════════════════════════

    for fname in txt_files:
        total_files += 1
        lines = list(all_file_lines[fname])   # working copy

        i = 0
        while i < len(lines):
            fields = parse_fields(lines[i])

            if TARGET_ID not in fields:
                i += 1
                continue

            # ── collect the whole contiguous block ────────────────────────────
            block_tag   = tag_before_target(fields, TARGET_ID)
            block_start = i
            block_idxs  = [i]
            j = i + 1
            while j < len(lines):
                jf = parse_fields(lines[j])
                if (TARGET_ID in jf
                        and tag_before_target(jf, TARGET_ID) == block_tag):
                    block_idxs.append(j)
                    j += 1
                else:
                    break
            block_end = j - 1   # inclusive index of last block line

            block_lines_text = [lines[k] for k in block_idxs]

            # ── determine new ID (reuse if same .FORM seen before) ────────────
            # Pre-compute .FORM to check cache
            compound_info_tmp = build_compound_info(block_lines_text, own_id="")
            form_tmp = "".join(ph for _, ph in compound_info_tmp if ph)

            if form_tmp in form_cache:
                new_id = form_cache[form_tmp]
            else:
                new_id, _ = id_gen.next_id(LEMMA_PREFIX)
                form_cache[form_tmp] = new_id
                total_new_ids += 1

            # ── replace TARGET_ID in every block line ─────────────────────────
            target_pat = re.compile(r'\b' + re.escape(TARGET_ID) + r'\b')
            for k in block_idxs:
                old = lines[k]
                new = target_pat.sub(new_id, old)
                if new != old:
                    lines[k] = new
                    total_replacements += 1
                    report_modified.append((fname, k + 1, old.rstrip("\r\n"),
                                            new.rstrip("\r\n")))

            # ── build dictionary entry ────────────────────────────────────────
            if CREATE_DICT_ENTRIES and new_id not in by_id:
                compound_info = build_compound_info(block_lines_text, own_id=new_id)
                # Q1 – related word: walk forward from block_end in THESE lines
                related_info  = find_related_words(block_end, lines, RELATED_TOP_N)

                new_entry = build_mk_entry(new_id, compound_info, related_info)
                entries.append(new_entry)
                by_id[new_id] = new_entry
                total_dict_added += 1
                report_added.append(new_entry)

            all_file_lines[fname] = lines
            i = block_end + 1   # jump past the block

        # ── save processed text file ──────────────────────────────────────────
        if OVERWRITE_SOURCE:
            out_path = os.path.join(TEXT_FOLDER, fname)
        else:
            base, ext = os.path.splitext(fname)
            out_path  = os.path.join(OUTPUT_FOLDER, f"{base}_processed{ext}")

        with open(out_path, "w", encoding="utf-8") as fh:
            fh.writelines(lines)
        output_files_saved.append(out_path)

    # ══════════════════════════════════════════════════════════════════════════
    #  PASS 2 – normalise existing makura-kotoba entries
    # ══════════════════════════════════════════════════════════════════════════

    if NORMALISE_EXISTING:
        corpus = flat_lines()
        for entry in entries:
            changed, added_desc = normalise_entry(entry, corpus, RELATED_TOP_N)
            if changed:
                total_normalized += 1
                report_normalized.append((entry.eid, added_desc))

    # ══════════════════════════════════════════════════════════════════════════
    #  SAVE DICTIONARY
    # ══════════════════════════════════════════════════════════════════════════

    if OVERWRITE_SOURCE:
        dict_save = DICT_FILE
    else:
        dict_save = os.path.join(dict_out_dir,
                                 os.path.basename(DICT_FILE))

    save_dictionary(entries, dict_save)
    output_files_saved.append(dict_save)

    # ══════════════════════════════════════════════════════════════════════════
    #  WRITE REPORTS
    # ══════════════════════════════════════════════════════════════════════════

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Report 1: modified lines ──────────────────────────────────────────────
    r1 = os.path.join(OUTPUT_FOLDER, REPORT_MODIFIED_LINES)
    with open(r1, "w", encoding="utf-8") as fh:
        fh.write(f"MODIFIED LINES REPORT  ({ts})\n")
        fh.write("=" * 70 + "\n\n")
        if not report_modified:
            fh.write("No lines were modified.\n")
        else:
            for fn, lno, old, new in report_modified:
                fh.write(f"File : {fn}  |  Line {lno}\n")
                fh.write(f"  OLD: {old}\n")
                fh.write(f"  NEW: {new}\n\n")
    output_files_saved.append(r1)

    # ── Report 2: dictionary entries added ────────────────────────────────────
    r2 = os.path.join(OUTPUT_FOLDER, REPORT_DICT_ADDED)
    with open(r2, "w", encoding="utf-8") as fh:
        fh.write(f"DICTIONARY ENTRIES ADDED  ({ts})\n")
        fh.write("=" * 70 + "\n\n")
        if not report_added:
            fh.write("No entries were added.\n")
        else:
            for ne in report_added:
                fh.write(ne.to_text())
                fh.write("\n")
    output_files_saved.append(r2)

    # ── Report 3: dictionary entries normalised (Q2 – full entry + what changed)
    r3 = os.path.join(OUTPUT_FOLDER, REPORT_DICT_MODIFIED)
    with open(r3, "w", encoding="utf-8") as fh:
        fh.write(f"DICTIONARY ENTRIES NORMALISED  ({ts})\n")
        fh.write("=" * 70 + "\n\n")
        if not report_normalized:
            fh.write("No entries were normalised.\n")
        else:
            for eid, added_lines in report_normalized:
                entry = by_id.get(eid)
                fh.write(f"Entry: {eid}\n")
                fh.write("Lines added:\n")
                for al in added_lines:
                    fh.write(f"  {al}\n")
                fh.write("\nFull entry after normalisation:\n")
                if entry:
                    fh.write(entry.to_text())
                fh.write("\n" + "-" * 50 + "\n\n")
    output_files_saved.append(r3)

    # ══════════════════════════════════════════════════════════════════════════
    #  TERMINAL SUMMARY
    # ══════════════════════════════════════════════════════════════════════════

    print()
    print("=" * 55)
    print("  PROCESSING SUMMARY")
    print("=" * 55)
    print(f"  Files processed              : {total_files}")
    print(f"  Total replacements           : {total_replacements}")
    print(f"  New lemma IDs created        : {total_new_ids}")
    print(f"  Dictionary entries added     : {total_dict_added}")
    print(f"  Dictionary entries normalised: {total_normalized}")
    print(f"  Source files overwritten     : {OVERWRITE_SOURCE}")
    print(f"  Output files saved           : {len(output_files_saved)}")
    for p in output_files_saved:
        print(f"    -> {p}")
    print("=" * 55)
    print()


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("mk_lemma_processor")
    print("=" * 55)
    print(f"  Text folder   : {TEXT_FOLDER}")
    print(f"  Dictionary    : {DICT_FILE}")
    print(f"  Output folder : {OUTPUT_FOLDER}")
    print(f"  New ID prefix : {LEMMA_PREFIX}")
    print(f"  ID width      : {LEMMA_DIGITS} digits (start >= {LEMMA_START})")
    print(f"  Overwrite src : {OVERWRITE_SOURCE}")
    print(f"  Create entries: {CREATE_DICT_ENTRIES}")
    print(f"  Normalise MK  : {NORMALISE_EXISTING}")
    print(f"  Related top-N : {RELATED_TOP_N}")
    print("=" * 55)
    print()
    process_files()
