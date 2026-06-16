"""
lemmas_processor.py
====================================
Contains all configuration, helpers, dictionary I/O, KANA generation,
POS-based annotation, ID generation, and processing loop.
"""

# ══════════════════════════════════════════════════════════════════════════════
#  USER SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

# ── Paths ─────────────────────────────────────────────────────────────────────
TEXT_FOLDER   = "text_files"      # folder containing .txt files to process
DICT_FILE     = "dictionary.txt"  # dictionary file path
OUTPUT_FOLDER = "output_files"    # folder for all output files

# ── Lemma ID settings ─────────────────────────────────────────────────────────
LEMMA_PREFIX  = "N"    # prefix for newly generated IDs  (L, N, F, T, …)
LEMMA_DIGITS  = 6      # zero-padded width  (6 → L000001)
LEMMA_START   = 1      # minimum numeric value for new IDs

# ── Existing-entry ID rewrite ─────────────────────────────────────────────────
DICT_ID_PREFIX = "T"   # prefix applied when inserting an existing dict ID
#                        Set to "T" to turn L011111 → T011111 on insertion.
#                        The numeric part is always taken from the dictionary.

# ── Core behaviour switches ───────────────────────────────────────────────────
OVERWRITE_SOURCE  = False  # True  → overwrite source .txt files in place
                            # False → write *_processed.txt to OUTPUT_FOLDER

DICT_ENTRY_CREATE = True   # True  → add a new entry to the dictionary when a
                            #         word is absent and a new ID is generated

ADVANCED_DISAMBIG = True   # True  → when multiple dict entries share the same
                            #         .FORM, score each against the preceding
                            #         syntactic tag and pick the best match

NORMALIZE_DICT    = True   # True  → before any processing, rewrite the entire
                            #         dictionary so every entry has the standard
                            #         tags in order: .GLOSS .MEANING .FORM .KANA
                            #         .POS  (missing tags are added blank;
                            #         existing extra tags like .NOTE are kept).

# ── Existing-word POS behaviour ──────────────────────────────────────────────
# When False, words found in the dictionary are annotated regardless of POS.
# When True, existing dictionary words are only annotated if the matching
# POS tag is present in the same way that unknown words are handled.
EXISTING_WORDS_POS_LIMIT = False

# ── POS-annotation mode ───────────────────────────────────────────────────────
# AUTO_POS_QUERY and AUTO_MATCH_MODE are applied automatically to every unknown
# word without any runtime prompt.
#
# AUTO_POS_QUERY : the POS tag to match two positions before each unknown word.
#                  Use "ALL!" to annotate every unlemmatised position regardless
#                  of the tag there.
# AUTO_MATCH_MODE: "strict" → the tag must equal AUTO_POS_QUERY exactly
#                  "loose"  → the tag only needs to *contain* AUTO_POS_QUERY
#                             (e.g. "VB" also matches "VB-ADN", "VB-STM", …)
AUTO_POS_QUERY  = "N"        # e.g. "N", "NP", "VB", "ALL!" — never empty
AUTO_MATCH_MODE = "strict"   # "strict" | "loose"


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import os
import re
import sys
from collections import defaultdict

# ══════════════════════════════════════════════════════════════════════════════
#  KANA CONVERSION TABLE
#  Built from: Phonemic transcription to historical kana spelling conversion list
# ══════════════════════════════════════════════════════════════════════════════

# Sorted longest-first so multi-char syllables are matched before single-char
_KANA_RAW: list[tuple[str, str]] = [
    # GROUP 1 — consonant + vowel
    ("pye", "ヘ"), ("pwi", "ヒ"),
    ("bye", "ベ"), ("bwi", "ビ"),
    ("kye", "ケ"), ("kwi", "キ"), ("kwo", "コ"),
    ("gye", "ゲ"), ("gwi", "ギ"), ("gwo", "ゴ"),
    ("mye", "メ"), ("mwi", "ミ"), ("mwo", "モ"),
    ("two", "ト"), ("dwo", "ド"),
    ("swo", "ソ"), ("zwo", "ゾ"),
    ("nwo", "ノ"),
    ("ywo", "ヨ"),
    ("rwo", "ロ"),
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

# Build a deterministic longest-match mapping
_KANA_TABLE: list[tuple[str, str]] = sorted(
    _KANA_RAW, key=lambda x: -len(x[0])
)


def phonemic_to_kana(form: str) -> str:
    """
    Convert a phonemic transcription string into katakana using the
    historical kana spelling conversion table (longest-match left-to-right).

    Unrecognised segments are left as-is (wrapped in ⟨…⟩ to flag them).
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
            # Unrecognised character — pass through and flag
            result.append(f"⟨{low[pos]}⟩")
            pos += 1
    return "".join(result)


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

ENTRY_SEP  = "---------------------------------------------------"
ENTRY_HEAD = re.compile(r'^=== ([A-Za-z]\d+[a-z]*)$')
FORM_LINE  = re.compile(r'^\.(FORM)\s+(\S+)')
GLOSS_LINE = re.compile(r'^\.(GLOSS)\s+(\S+)')
LEMMA_RE   = re.compile(r'^[A-Za-z]\d+[a-z]*$')   # any-prefix lemma ID


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY LOADER
# ══════════════════════════════════════════════════════════════════════════════

def load_dictionary(dict_path: str):
    """
    Parse the dictionary file.

    Returns
    -------
    form_to_lemma      : dict[str, str]
        Maps each .FORM to the *first* matching entry's lemma ID.
        (Used when ADVANCED_DISAMBIG is False.)
    form_to_candidates : dict[str, list[dict]]
        Maps each .FORM to ALL matching entries: [{'lemma': str, 'gloss': str}, …]
        (Used when ADVANCED_DISAMBIG is True.)
    existing_numbers   : set[int]
        Numeric parts of all existing lemma IDs (any prefix).
    raw_lines          : list[str]
        Original file lines, for in-place rewriting when DICT_ENTRY_CREATE=True.
    entries_order      : list[tuple[int, int]]
        (numeric_id, separator_line_index) per entry — used for sorted insertion.
    """
    form_to_lemma: dict[str, str]       = {}
    form_to_candidates: dict[str, list] = defaultdict(list)
    existing_numbers: set[int]          = set()
    raw_lines: list[str]                = []
    entries_order: list[tuple]          = []

    if not os.path.isfile(dict_path):
        print(f"[WARNING] Dictionary file not found: {dict_path}")
        return (form_to_lemma, form_to_candidates,
                existing_numbers, raw_lines, entries_order)

    with open(dict_path, encoding="utf-8") as fh:
        raw_lines = fh.readlines()

    current_lemma: str | None   = None
    current_gloss: str          = ""
    current_sep_idx: int | None = None

    for idx, line in enumerate(raw_lines):
        stripped = line.rstrip("\n").rstrip("\r")

        if stripped == ENTRY_SEP:
            current_sep_idx = idx
            continue

        m = ENTRY_HEAD.match(stripped)
        if m:
            current_lemma = m.group(1)
            current_gloss = ""
            num = int(re.search(r'\d+', current_lemma).group())
            existing_numbers.add(num)
            if current_sep_idx is not None:
                entries_order.append((num, current_sep_idx))
            continue

        if current_lemma:
            gm = GLOSS_LINE.match(stripped)
            if gm:
                current_gloss = gm.group(2) if gm.lastindex == 2 else gm.group(1)

            fm = FORM_LINE.match(stripped)
            if fm:
                form_val = fm.group(2) if fm.lastindex == 2 else fm.group(1)
                form_to_lemma.setdefault(form_val, current_lemma)
                form_to_candidates[form_val].append({
                    "lemma": current_lemma,
                    "gloss": current_gloss,
                })

    return (form_to_lemma, form_to_candidates,
            existing_numbers, raw_lines, entries_order)


# ══════════════════════════════════════════════════════════════════════════════
#  ADVANCED DISAMBIGUATION
# ══════════════════════════════════════════════════════════════════════════════

def disambiguate(candidates: list[dict],
                 preceding_tag: str,
                 full_line: str) -> str:
    """
    Pick the best lemma ID from *candidates* by scoring each against the
    syntactic tag that immediately precedes the word position.

    Score (first match wins per candidate):
        3 — preceding_tag starts with candidate .GLOSS
        2 — preceding_tag contains candidate .GLOSS (case-insensitive)
        1 — full_line contains candidate .GLOSS  (broad fallback)
        0 — no match
    Ties → first candidate (dictionary order).
    """
    best_lemma = candidates[0]["lemma"]
    best_score = -1
    tag_upper  = preceding_tag.upper()
    line_upper = full_line.upper()

    for cand in candidates:
        gloss = cand["gloss"].upper()
        if not gloss:
            score = 0
        elif tag_upper.startswith(gloss):
            score = 3
        elif gloss in tag_upper:
            score = 2
        elif gloss in line_upper:
            score = 1
        else:
            score = 0

        if score > best_score:
            best_score = score
            best_lemma = cand["lemma"]

    return best_lemma


# ══════════════════════════════════════════════════════════════════════════════
#  ID GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class IDGenerator:
    """Generates unique numeric IDs that never clash with existing ones."""

    def __init__(self, existing: set[int], start: int = LEMMA_START):
        self._used: set[int] = set(existing)
        self._counter: int   = max(start, 1)

    def next_number(self) -> int:
        while self._counter in self._used:
            self._counter += 1
        n = self._counter
        self._used.add(n)
        self._counter += 1
        return n

    def make_id(self, prefix: str, number: int) -> str:
        return f"{prefix}{number:0{LEMMA_DIGITS}d}"


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY ENTRY BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_entry_block(lemma_id: str, word_form: str) -> list[str]:
    """
    Build the lines for a new dictionary entry.

    Format (per spec):
        ---------------------------------------------------
        === <lemma_id>
        .GLOSS\t
        .MEANING\t
        .FORM\t<word_form>
        .KANA\t<auto-generated katakana>
        .POS\t
        <blank line>
    """
    kana = phonemic_to_kana(word_form)
    return [
        ENTRY_SEP + "\n",
        f"=== {lemma_id}\n",
        ".GLOSS\t\n",
        ".MEANING\t\n",
        f".FORM\t{word_form}\n",
        f".KANA\t{kana}\n",
        ".POS\t\n",
        "\n",
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  SORTED DICTIONARY INSERTION
# ══════════════════════════════════════════════════════════════════════════════

def insert_dict_entry(raw_lines: list[str],
                      entries_order: list[tuple],
                      lemma_id: str,
                      word_form: str) -> None:
    """
    Insert a new dictionary entry block into raw_lines in sorted numeric order.
    Modifies raw_lines and entries_order in-place.
    """
    num       = int(re.search(r'\d+', lemma_id).group())
    new_block = build_entry_block(lemma_id, word_form)

    # Find the separator of the last entry whose numeric ID < num
    insert_after_sep: int | None = None
    for entry_num, sep_idx in sorted(entries_order, key=lambda x: x[0]):
        if entry_num < num:
            insert_after_sep = sep_idx
        else:
            break

    if insert_after_sep is None:
        # Insert before everything
        for i, line in enumerate(new_block):
            raw_lines.insert(i, line)
        shift = len(new_block)
        entries_order[:] = [
            (en, si + shift) for en, si in entries_order
        ]
        entries_order.insert(0, (num, 0))
    else:
        later = [(en, si) for en, si in entries_order if si > insert_after_sep]
        if later:
            target = min(later, key=lambda x: x[1])[1]
            for i, line in enumerate(new_block):
                raw_lines.insert(target + i, line)
            shift = len(new_block)
            entries_order[:] = [
                (en, si + shift) if si >= target else (en, si)
                for en, si in entries_order
            ]
            entries_order.append((num, target))
        else:
            # Append at end
            new_sep_idx = len(raw_lines)
            raw_lines.extend(new_block)
            entries_order.append((num, new_sep_idx))

        entries_order.sort(key=lambda x: x[0])


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY NORMALISER
# ══════════════════════════════════════════════════════════════════════════════

# The five tags that every entry must contain, in this order.
_REQUIRED_TAGS = [".GLOSS", ".MEANING", ".FORM", ".KANA", ".POS"]
# Tag used to recognise any dot-field line
_TAG_RE = re.compile(r'^(\.[A-Z]+(?:\[\d+\])?)\s*(.*)')


def normalize_dictionary(dict_path: str, report: "AnnotationReport") -> None:
    """
    Read the dictionary at *dict_path*, ensure every entry contains all five
    required tags (.GLOSS .MEANING .FORM .KANA .POS), add any missing ones,
    auto-fill .KANA from .FORM when absent, preserve all extra tags (e.g.
    .NOTE), and write the result back in-place.

    All entries that were changed are recorded in *report*.
    """
    if not os.path.isfile(dict_path):
        print(f"[NORMALIZE] Dictionary not found: {dict_path}")
        return

    with open(dict_path, encoding="utf-8") as fh:
        raw = fh.read()

    blocks   = raw.split(ENTRY_SEP)
    out_blocks: list[str] = [blocks[0]]
    changed_entries: list[tuple[str, list[str]]] = []  # (lemma_id, [change descriptions])

    for block in blocks[1:]:
        lines = block.splitlines(keepends=True)

        # Find the header line
        header_line = ""
        body_lines: list[str] = []
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if ENTRY_HEAD.match(stripped):
                header_line = stripped
                body_lines  = lines[i + 1:]
                break
        else:
            out_blocks.append(ENTRY_SEP + block)
            continue

        lemma_id = ENTRY_HEAD.match(header_line).group(1)

        # Parse existing tags.
        # For required tags: record only the FIRST occurrence's value.
        # Any subsequent occurrence of the same required tag, and all
        # non-required tags, go into extra_lines (preserved verbatim).
        seen_required: set[str]  = set()
        existing: dict[str, str] = {}   # required tag → first value
        extra_lines: list[str]   = []   # everything else, kept in order

        for ln in body_lines:
            s = ln.rstrip("\r\n")
            if s == "":
                continue
            m = _TAG_RE.match(s)
            if m:
                raw_tag  = m.group(1)
                val      = m.group(2).strip()
                base_tag = re.match(r'\.[A-Z]+', raw_tag).group()
                if base_tag in _REQUIRED_TAGS and base_tag not in seen_required:
                    existing[base_tag] = val
                    seen_required.add(base_tag)
                else:
                    # Second+ occurrence of a required tag, or a non-required tag
                    extra_lines.append(ln if ln.endswith("\n") else ln + "\n")
            else:
                extra_lines.append(ln if ln.endswith("\n") else ln + "\n")

        # If every required tag is already present, skip this entry entirely
        if all(t in existing for t in _REQUIRED_TAGS):
            out_blocks.append(
                ENTRY_SEP + "\n"
                + header_line + "\n"
                + "".join(ln if ln.endswith("\n") else ln + "\n"
                          for ln in body_lines)
            )
            continue

        # Build normalised body, adding any missing required tags
        changes: list[str] = []
        new_body: list[str] = []

        for tag in _REQUIRED_TAGS:
            old_val = existing.get(tag)   # None = tag absent

            if old_val is not None:
                val = old_val
                # Auto-fill blank .KANA from .FORM
                if tag == ".KANA" and not val:
                    form_val = existing.get(".FORM", "")
                    if form_val:
                        val = phonemic_to_kana(form_val)
                        changes.append(f"filled {tag} = {val}")
            else:
                # Tag missing — add it
                if tag == ".KANA":
                    form_val = existing.get(".FORM", "")
                    val = phonemic_to_kana(form_val) if form_val else ""
                else:
                    val = ""
                changes.append(f"added {tag}" + (f" = {val}" if val else " (blank)"))

            new_body.append(f"{tag}\t{val}\n")

        new_body.extend(extra_lines)
        new_body.append("\n")

        if changes:
            changed_entries.append((lemma_id, changes))

        out_blocks.append(
            ENTRY_SEP + "\n"
            + header_line + "\n"
            + "".join(new_body)
        )

    result = "".join(out_blocks)
    with open(dict_path, "w", encoding="utf-8") as fh:
        fh.write(result)

    total = len(changed_entries)
    print(f"  [NORMALIZE] Dictionary normalised: {dict_path} "
          f"({total} entr{'y' if total == 1 else 'ies'} modified)")

    # Pass all normalisation changes to the report
    report.record_normalization(changed_entries)


# ══════════════════════════════════════════════════════════════════════════════
#  LINE ANALYSIS  (standard mode — existing dict lookup)
# ══════════════════════════════════════════════════════════════════════════════

PEN_RE  = re.compile(r'^[A-Z][A-Z0-9\-]*$')  # syntactic tag (uppercase, may contain - or digits)
LAST_RE = re.compile(r'^[A-Za-z]+$')          # word form (alphabetic)


def analyse_line(fields: list[str]):
    """
    Return (needs_lemma, word_form, insert_pos, preceding_tag) or None.

    Looks for the pattern: …, <SYNCTAG>, <word_form>
    where SYNCTAG is all-uppercase (possibly with hyphens/digits) and
    word_form is alphabetic.

    insert_pos    — index where the lemma ID should be inserted
    preceding_tag — the field just before insert_pos (for disambiguation)
    needs_lemma   — False when a lemma ID is already present there
    """
    n = len(fields)
    if n < 2:
        return None

    penultimate = fields[-2]
    last        = fields[-1]

    if not PEN_RE.match(penultimate):
        return None
    if not LAST_RE.match(last):
        return None

    insert_pos    = n - 2
    preceding_idx = insert_pos - 1
    preceding_tag = fields[preceding_idx] if preceding_idx >= 0 else ""

    if preceding_idx >= 0 and LEMMA_RE.match(fields[preceding_idx]):
        return (False, last, insert_pos, preceding_tag)

    return (True, last, insert_pos, preceding_tag)


# ══════════════════════════════════════════════════════════════════════════════
#  POS-ANNOTATION HELPERS  (for words absent from the dictionary)
# ══════════════════════════════════════════════════════════════════════════════

def pos_matches(field: str, pos_query: str, mode: str) -> bool:
    """
    Return True when *field* matches *pos_query* under *mode*.

    mode="strict" → exact equality
    mode="loose"  → field contains pos_query (case-insensitive)
    pos_query="ALL!" → always True (match everything without a lemma)
    """
    if pos_query == "ALL!":
        return True
    if mode == "strict":
        return field == pos_query
    return pos_query.upper() in field.upper()


def find_annotation_targets(
    fields: list[str],
    pos_query: str,
    match_mode: str,
) -> list[int]:
    """
    Scan *fields* for positions where:
      - the field at index i matches pos_query (per match_mode)
      - the field two positions AFTER i is a word (LAST_RE)
      - no lemma ID already occupies position i+1

    Returns a list of (tag_index) values — the position of the matching POS tag.

    Requirement (spec §3): "two positions before this word".
    So if the word is at index w, the POS tag is at w-2, and the lemma
    slot to fill is at w-1.
    """
    n       = len(fields)
    targets = []
    for tag_idx in range(n - 2):
        tag  = fields[tag_idx]
        word = fields[tag_idx + 2]

        if not pos_matches(tag, pos_query, match_mode):
            continue
        if not LAST_RE.match(word):
            continue

        # Slot between tag and word
        slot = fields[tag_idx + 1]
        if LEMMA_RE.match(slot):
            continue   # already annotated

        targets.append(tag_idx)

    return targets


# ══════════════════════════════════════════════════════════════════════════════
#  ANNOTATION REPORT  (accumulated during a run)
# ══════════════════════════════════════════════════════════════════════════════

class AnnotationReport:
    """Collects data for Report 1 (annotated lines) and Report 2 (new entries)."""

    def __init__(self):
        # Report 1: {filename: [(line_no, original_line, new_lemma_id), …]}
        self.annotated_lines: dict[str, list[tuple]] = defaultdict(list)
        # Report 2: [(lemma_id, word_form, kana), …]
        self.new_entries: list[tuple[str, str, str]] = []
        # Report 3: [(lemma_id, [change descriptions]), …]
        self.normalized_entries: list[tuple[str, list[str]]] = []

    def record_normalization(self, changed_entries: list[tuple[str, list[str]]]) -> None:
        self.normalized_entries.extend(changed_entries)

    def record_annotation(self, filename: str, line_no: int,
                          original: str, lemma_id: str):
        self.annotated_lines[filename].append((line_no, original.rstrip(), lemma_id))

    def record_new_entry(self, lemma_id: str, word_form: str):
        kana = phonemic_to_kana(word_form)
        self.new_entries.append((lemma_id, word_form, kana))

    def save_reports(self, output_folder: str) -> None:
        os.makedirs(output_folder, exist_ok=True)
        r1_path = os.path.join(output_folder, "report1_annotated_lines.txt")
        r2_path = os.path.join(output_folder, "report2_new_entries.txt")
        r3_path = os.path.join(output_folder, "report3_normalized_entries.txt")

        # ── Report 1 ──────────────────────────────────────────────────────────
        with open(r1_path, "w", encoding="utf-8") as fh:
            fh.write("REPORT 1 · Annotated lines\n")
            fh.write("══════════════════════════════════════════════════════\n")
            if not self.annotated_lines:
                fh.write("(none)\n")
            else:
                for fname, records in sorted(self.annotated_lines.items()):
                    fh.write(f"\nFile: {fname}\n")
                    for line_no, original, lemma_id in records:
                        fh.write(f"  Line {line_no:>6}  [{lemma_id}]\n")
                        fh.write(f"           {original}\n")
        print(f"  [REPORT] {r1_path}")

        # ── Report 2 ──────────────────────────────────────────────────────────
        with open(r2_path, "w", encoding="utf-8") as fh:
            fh.write("REPORT 2 · New dictionary entries added\n")
            fh.write("══════════════════════════════════════════════════════\n")
            if not self.new_entries:
                fh.write("(none)\n")
            else:
                fh.write(f"{'ID':<12}  {'FORM':<20}  KANA\n")
                fh.write(f"{'-'*12}  {'-'*20}  {'-'*20}\n")
                for lemma_id, word_form, kana in self.new_entries:
                    fh.write(f"{lemma_id:<12}  {word_form:<20}  {kana}\n")
        print(f"  [REPORT] {r2_path}")

        # ── Report 3 ──────────────────────────────────────────────────────────
        r3_path = os.path.join(output_folder, "report3_normalized_entries.txt")
        with open(r3_path, "w", encoding="utf-8") as fh:
            fh.write("REPORT 3 · Dictionary entries modified by normalisation\n")
            fh.write("══════════════════════════════════════════════════════\n")
            if not self.normalized_entries:
                fh.write("(none)\n")
            else:
                fh.write(f"{'ID':<14}  Changes\n")
                fh.write(f"{'-'*14}  {'-'*40}\n")
                for lemma_id, changes in self.normalized_entries:
                    fh.write(f"{lemma_id:<14}  {'; '.join(changes)}\n")
        print(f"  [REPORT] {r3_path}")


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS A SINGLE FILE  (standard dictionary-lookup path)
# ══════════════════════════════════════════════════════════════════════════════

def process_file_standard(
    filename: str,
    filepath: str,
    form_to_lemma: dict,
    form_to_candidates: dict,
    id_gen: IDGenerator,
    new_id_cache: dict,
    dict_raw: list,
    entries_order: list,
    report: AnnotationReport,
    stats: dict,
) -> list[str]:
    """
    Process one .txt file using standard dictionary-lookup logic.
    Returns the list of output lines.
    """
    with open(filepath, encoding="utf-8") as fh:
        original_lines = fh.readlines()

    output_lines: list[str] = []

    for line_no, raw_line in enumerate(original_lines, start=1):
        stats["lines_scanned"] += 1
        line_body = raw_line.rstrip("\n").rstrip("\r")
        trailing  = raw_line[len(line_body):]

        fields = line_body.split(",")
        result = analyse_line(fields)

        if result is None:
            stats["unchanged_lines"] += 1
            output_lines.append(raw_line)
            continue

        needs_lemma, word_form, insert_pos, preceding_tag = result

        if not needs_lemma:
            stats["lines_already_lemma"] += 1
            output_lines.append(raw_line)
            continue

        # ── Resolve lemma ID ──────────────────────────────────────────────────
        if word_form in form_to_lemma:
            candidates = form_to_candidates[word_form]
            if ADVANCED_DISAMBIG and len(candidates) > 1:
                raw_lemma = disambiguate(candidates, preceding_tag, line_body)
                stats["disambiguations_applied"] += 1
            else:
                raw_lemma = form_to_lemma[word_form]

            num_part = re.search(r'\d+[a-z]*', raw_lemma).group()
            lemma_id = f"{DICT_ID_PREFIX}{num_part}"

            if EXISTING_WORDS_POS_LIMIT:
                pos_query  = AUTO_POS_QUERY
                match_mode = AUTO_MATCH_MODE
            else:
                pos_query  = "ALL!"
                match_mode = "strict"

            targets = find_annotation_targets(fields, pos_query, match_mode)
            n = len(fields)
            targets = [t for t in targets if t == n - 3]

            if not targets:
                stats["unchanged_lines"] += 1
                output_lines.append(raw_line)
                continue

            fields.insert(targets[0] + 1, lemma_id)
            stats["dict_matches_inserted"] += 1
            new_line = ",".join(fields) + trailing
            output_lines.append(new_line)
            report.record_annotation(filename, line_no, line_body, lemma_id)

        elif word_form in new_id_cache:
            lemma_id = new_id_cache[word_form]
            stats["words_reused"] += 1

            targets = find_annotation_targets(fields, "ALL!", "strict")
            n = len(fields)
            targets = [t for t in targets if t == n - 3]

            if not targets:
                stats["unchanged_lines"] += 1
                output_lines.append(raw_line)
                continue

            fields.insert(targets[0] + 1, lemma_id)
            stats["dict_matches_inserted"] += 1
            new_line = ",".join(fields) + trailing
            output_lines.append(new_line)
            report.record_annotation(filename, line_no, line_body, lemma_id)

        else:
            # Brand-new word — deferred to process_unknown_words pass 2
            stats["unchanged_lines"] += 1
            output_lines.append(raw_line)
            continue

    return output_lines


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS UNKNOWN WORDS  (POS-prompt path — batch per word form)
# ══════════════════════════════════════════════════════════════════════════════

def process_unknown_words(
    filename: str,
    lines: list[str],
    form_to_lemma: dict,
    id_gen: "IDGenerator",
    new_id_cache: dict,
    dict_raw: list,
    entries_order: list,
    report: "AnnotationReport",
    stats: dict,
) -> list[str]:
    """
    Second pass: collect ALL unknown word forms across the whole file first,
    then ask the user once per unique form, and apply all matching annotations
    in one go.
    """
    # ── Step 1: scan every line and collect unknown forms ─────────────────────
    # unknown_forms: form → list of (line_index, needs_lemma)
    unknown_forms: dict[str, list[int]] = {}

    for i, raw_line in enumerate(lines):
        line_body = raw_line.rstrip("\n").rstrip("\r")
        fields    = line_body.split(",")
        result    = analyse_line(fields)
        if result is None:
            continue
        needs_lemma, word_form, _, _ = result
        if not needs_lemma:
            continue
        if word_form in form_to_lemma:
            continue
        unknown_forms.setdefault(word_form, []).append(i)

    if not unknown_forms:
        return lines

    # ── Step 2: for each unique unknown form, ask once then annotate all ──────
    output_lines = list(lines)

    for word_form, line_indices in unknown_forms.items():

        # Determine the lemma ID (may already exist from a previous file)
        if word_form in new_id_cache:
            lemma_id   = new_id_cache[word_form]
            pos_query  = "ALL!"
            match_mode = "strict"

        else:
            # Apply the global auto-annotation settings; no prompt needed.
            pos_query  = AUTO_POS_QUERY
            match_mode = AUTO_MATCH_MODE

            print(f"\n  [NEW] '{word_form}' — not in dictionary, "
                  f"found on {len(line_indices)} line(s) in {filename} "
                  f"→ auto-annotating with POS='{pos_query}', mode='{match_mode}'")

            num      = id_gen.next_number()
            lemma_id = id_gen.make_id(LEMMA_PREFIX, num)
            new_id_cache[word_form] = lemma_id
            stats["new_ids_created"] += 1

            if DICT_ENTRY_CREATE:
                insert_dict_entry(dict_raw, entries_order, lemma_id, word_form)
                stats["dict_entries_added"] += 1
                report.record_new_entry(lemma_id, word_form)

        # ── Apply to every line that contains this word form ──────────────────
        annotated_count = 0
        for i in line_indices:
            raw_line  = output_lines[i]
            line_body = raw_line.rstrip("\n").rstrip("\r")
            trailing  = raw_line[len(line_body):]
            fields    = line_body.split(",")

            targets = find_annotation_targets(fields, pos_query, match_mode)
            # Filter to only insert at the specific position (third from end)
            n = len(fields)
            targets = [t for t in targets if t == n - 3]
            if not targets:
                continue

            # Insert from right to left to keep earlier indices valid
            for tag_idx in sorted(targets, reverse=True):
                fields.insert(tag_idx + 1, lemma_id)

            output_lines[i] = ",".join(fields) + trailing
            report.record_annotation(
                filename, i + 1, line_body,
                f"{lemma_id} [POS={pos_query}, mode={match_mode}]"
            )
            stats["dict_matches_inserted"] += 1
            annotated_count += 1

        print(f"      → {lemma_id} inserted on {annotated_count} line(s)")

    return output_lines


# ══════════════════════════════════════════════════════════════════════════════
#  WRITE OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

def write_output(filename: str, filepath: str, output_lines: list[str]) -> str:
    """Write processed lines and return the output path used."""
    if OVERWRITE_SOURCE:
        out_path = filepath
    else:
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        base, ext = os.path.splitext(filename)
        out_path  = os.path.join(OUTPUT_FOLDER, f"{base}_processed{ext}")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.writelines(output_lines)

    return out_path


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def process_files():
    # ── Load dictionary ───────────────────────────────────────────────────────
    (form_to_lemma, form_to_candidates,
     existing_numbers, dict_raw, entries_order) = load_dictionary(DICT_FILE)

    id_gen = IDGenerator(existing_numbers, start=LEMMA_START)

    new_id_cache: dict[str, str] = {}   # word_form → generated lemma_id

    report = AnnotationReport()

    stats = {
        "files_processed"        : 0,
        "lines_scanned"          : 0,
        "lines_already_lemma"    : 0,
        "dict_matches_inserted"  : 0,
        "disambiguations_applied": 0,
        "new_ids_created"        : 0,
        "words_reused"           : 0,
        "dict_entries_added"     : 0,
        "unchanged_lines"        : 0,
        "output_files_saved"     : 0,
    }

    # ── Collect .txt files ────────────────────────────────────────────────────
    if not os.path.isdir(TEXT_FOLDER):
        sys.exit(f"[ERROR] Text folder not found: {TEXT_FOLDER}")

    txt_files = sorted(
        f for f in os.listdir(TEXT_FOLDER) if f.lower().endswith(".txt")
    )

    if not txt_files:
        print(f"[INFO] No .txt files found in '{TEXT_FOLDER}'.")
        return

    # ── Process each file ─────────────────────────────────────────────────────
    for filename in txt_files:
        filepath = os.path.join(TEXT_FOLDER, filename)
        print(f"\n  Processing: {filename}")

        # Pass 1 — annotate words that ARE in the dictionary
        output_lines = process_file_standard(
            filename, filepath,
            form_to_lemma, form_to_candidates,
            id_gen, new_id_cache,
            dict_raw, entries_order,
            report, stats,
        )

        # Pass 2 — prompt for POS and annotate words NOT in the dictionary
        output_lines = process_unknown_words(
            filename, output_lines,
            form_to_lemma,
            id_gen, new_id_cache,
            dict_raw, entries_order,
            report, stats,
        )

        # Write result
        out_path = write_output(filename, filepath, output_lines)
        stats["files_processed"]   += 1
        stats["output_files_saved"] += 1
        mode = "overwritten" if OVERWRITE_SOURCE else f"→ '{os.path.basename(out_path)}'"
        print(f"  [OK] {filename} {mode}")

    # ── Write the processed dictionary to OUTPUT_FOLDER ───────────────────────
    # Always write dictionary_processed.txt when OVERWRITE_SOURCE is False,
    # so even a normalise-only run produces output.
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    if OVERWRITE_SOURCE:
        dict_out_path = DICT_FILE
    else:
        dict_base = os.path.splitext(os.path.basename(DICT_FILE))[0]
        dict_out_path = os.path.join(OUTPUT_FOLDER, f"{dict_base}_processed.txt")

    with open(dict_out_path, "w", encoding="utf-8") as fh:
        fh.writelines(dict_raw)
    print(f"\n  [OK] Dictionary written: {dict_out_path}")

    # ── Normalise dictionary after all entries have been added/modified ────────
    if NORMALIZE_DICT:
        normalize_dictionary(dict_out_path, report)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("══════════════════════════════════════════════════════")
    print("  PROCESSING SUMMARY")
    print("══════════════════════════════════════════════════════")
    print(f"  Files processed               : {stats['files_processed']}")
    print(f"  Lines scanned                 : {stats['lines_scanned']}")
    print(f"  Lines already containing lemma: {stats['lines_already_lemma']}")
    print(f"  Lemma IDs inserted (dict hit) : {stats['dict_matches_inserted']}")
    if ADVANCED_DISAMBIG:
        print(f"  Advanced disambiguations      : {stats['disambiguations_applied']}")
    print(f"  New IDs generated             : {stats['new_ids_created']}")
    print(f"  Repeated words reused         : {stats['words_reused']}")
    print(f"  Dictionary entries added      : {stats['dict_entries_added']}")
    print(f"  Unchanged / unmatched lines   : {stats['unchanged_lines']}")
    print(f"  Output files saved            : {stats['output_files_saved']}")
    print("══════════════════════════════════════════════════════")

    # ── Annotation reports ────────────────────────────────────────────────────
    report.save_reports(OUTPUT_FOLDER)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("lemmas_processor")
    print("════════════════════════════════════════════════════════")
    print(f"  Text folder   : {TEXT_FOLDER}")
    print(f"  Dictionary    : {DICT_FILE}")
    print(f"  Output folder : {OUTPUT_FOLDER}")
    print(f"  New ID prefix : {LEMMA_PREFIX}  (dict IDs use prefix: {DICT_ID_PREFIX})")
    print(f"  ID width      : {LEMMA_DIGITS} digits  (start ≥ {LEMMA_START})")
    print(f"  Overwrite src : {OVERWRITE_SOURCE}")
    print(f"  Create entry  : {DICT_ENTRY_CREATE}")
    print(f"  Adv. disambig : {ADVANCED_DISAMBIG}")
    print(f"  Auto POS query: {AUTO_POS_QUERY}")
    print(f"  Auto POS mode : {AUTO_MATCH_MODE}")
    print("════════════════════════════════════════════════════════")
    print()
    process_files()
