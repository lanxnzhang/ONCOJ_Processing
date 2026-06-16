"""
compound_lemma_processor.py
============================
Processes text files to detect missing shared lemma IDs in paired
compound-noun lines, inserts a shared new lemma ID into both lines,
and optionally creates / refines dictionary entries.

USER SWITCHES — configure here before running
"""

import os
import re
import copy
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# USER SWITCHES
# ──────────────────────────────────────────────────────────────────────────────

# Paths
TEXT_FOLDER       = "input_texts"       # folder containing .txt files to process
DICT_FILE         = "dictionary.txt"    # dictionary file path
OUTPUT_FOLDER     = "output_files"      # folder for all output files

# Core features
DICT_SEARCH       = True    # search dictionary for existing compound lemma
DICT_REFINE       = True    # add missing .COMPOUND lines to existing entry
DICT_ENTRY_CREATE = True    # create a new dictionary entry when compound is new

# Expanded search patterns
EXPANDED_SEARCH_1 = True    # detect NP,N,L…,PHON pairs missing intermediate N
EXPANDED_SEARCH_2 = True    # detect N,N / N,N;@2 pairs without preceding NP

# Output extras
SAVE_REVISED      = True    # also write *_revised files with only changed content
OVERWRITE_SOURCE  = False   # if True, overwrite source text/dict files in place;
                            # if False (default), write processed files to OUTPUT_FOLDER

# Lemma ID settings
LEMMA_PREFIX      = "L"     # prefix character(s)
LEMMA_DIGITS      = 6       # total digit width  (e.g. 6 → L050340)
LEMMA_START       = 50001   # minimum numeric value for new IDs


# ──────────────────────────────────────────────────────────────────────────────
# DICTIONARY PARSING
# ──────────────────────────────────────────────────────────────────────────────

def parse_dictionary(dict_path: str) -> dict:
    """
    Returns a dict keyed by lemma ID (e.g. 'L050340').
    Each value is a dict:
        {
          'raw_lines': [str, ...],   # original lines of the entry (including '=== Lxxxxxx')
                                     # trailing blank lines are NOT stored here
          'fields':    {'.FORM': [str,...], '.GLOSS': [str,...], ...}
        }
    """
    entries = {}
    current_id = None
    current_lines = []

    def flush():
        if current_id:
            # Strip trailing blank lines from stored raw_lines
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
            m = re.match(r"^===\s+(L\d+\S*)\s*$", line)
            if m:
                flush()
                current_id = m.group(1)
                current_lines = [line]
            else:
                if current_id is not None:
                    current_lines.append(line)
    flush()
    return entries


def _parse_fields(lines: list) -> dict:
    """Extract multi-valued fields from entry lines."""
    fields: dict = {}
    for line in lines[1:]:          # skip the === header
        m = re.match(r"^(\.\w+)\s*(.*)", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            fields.setdefault(key, []).append(val)
    return fields


def all_numeric_ids(entries: dict) -> set:
    nums = set()
    for lid in entries:
        m = re.match(r"^L(\d+)", lid)
        if m:
            nums.add(int(m.group(1)))
    return nums


def new_lemma_id(used_nums: set) -> str:
    """Return the next unused lemma ID."""
    n = LEMMA_START
    while n in used_nums:
        n += 1
    used_nums.add(n)
    return f"{LEMMA_PREFIX}{str(n).zfill(LEMMA_DIGITS)}"


# ──────────────────────────────────────────────────────────────────────────────
# COMPOUND LOOKUP IN DICTIONARY
# ──────────────────────────────────────────────────────────────────────────────

def _get_pos_priority(pos_value: str) -> int:
    """
    Return POS priority score (lower score = higher priority).
    Prioritizes noun and noun-related entries to avoid false matches
    with non-noun words that share the same form.
    """
    pos_lower = pos_value.lower().strip()
    
    # Highest priority: pure noun
    if pos_lower == "noun":
        return 0
    
    # Second priority: compound POS containing 'noun' (e.g., 'noun.suffix')
    if "noun" in pos_lower:
        return 1
    
    # Default priority: other POS values
    return 100


def find_compound_in_dict(form: str, entries: dict) -> str | None:
    """
    Return lemma ID if an entry with .FORM exactly == form exists, else None.
    If multiple entries match, prioritize those with POS = 'noun' or noun-related.
    Exact match: 'amakumo' must not match 'amakumono'.
    """
    candidates = []  # List of (lemma_id, pos_priority, pos_value)
    
    for lid, data in entries.items():
        for f in data["fields"].get(".FORM", []):
            # strip everything after the first whitespace to get just the form token
            token = f.split()[0] if f else ""
            if token == form:
                # Retrieve POS for this entry
                pos_values = data["fields"].get(".POS", [])
                pos = pos_values[0] if pos_values else ""
                priority = _get_pos_priority(pos)
                candidates.append((lid, priority, pos))
                break  # Check POS only once per lemma_id
    
    if not candidates:
        return None
    
    # Sort by priority score (ascending); return the highest-priority entry
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


# ──────────────────────────────────────────────────────────────────────────────
# DICTIONARY ENTRY BUILDING
# ──────────────────────────────────────────────────────────────────────────────

def get_first_field(entries: dict, lid: str, field: str) -> str:
    """Return first value for a field in an entry, or empty string."""
    vals = entries.get(lid, {}).get("fields", {}).get(field, [])
    return vals[0].strip() if vals else ""


def get_all_fields(entries: dict, lid: str, field: str) -> list:
    return entries.get(lid, {}).get("fields", {}).get(field, [])


def build_new_entry(new_id: str,
                    comp1_id: str, comp1_form: str,
                    comp2_id: str, comp2_form: str,
                    entries: dict) -> list:
    """
    Build the raw lines of a new compound dictionary entry.
    Returns list of strings (no trailing newlines, no trailing blank lines).
    Trailing blank line is added only at serialisation time.
    """
    gloss1  = get_first_field(entries, comp1_id, ".GLOSS")
    gloss2  = get_first_field(entries, comp2_id, ".GLOSS")
    mean1   = get_first_field(entries, comp1_id, ".MEANING")
    mean2   = get_first_field(entries, comp2_id, ".MEANING")
    kana1   = get_first_field(entries, comp1_id, ".KANA")
    kana2   = get_first_field(entries, comp2_id, ".KANA")

    compound_form  = comp1_form + comp2_form
    compound_kana  = kana1 + kana2
    compound_gloss = (gloss1 + " " + gloss2).strip() if (gloss1 or gloss2) else ""
    compound_mean  = (mean1 + " " + mean2).strip() if (mean1 or mean2) else ""

    # NOTE: no trailing blank line stored in raw_lines; serialiser adds it.
    lines = [
        f"=== {new_id}",
        f".GLOSS\t{compound_gloss}",
        f".MEANING\t{compound_mean}",
        f".FORM\t{compound_form}",
        f".KANA\t{compound_kana}",
        f".POS\tnoun",
        f".COMPOUND\tref_target={comp1_id}\t{comp1_form}",
        f".COMPOUND\tref_target={comp2_id}\t{comp2_form}",
    ]
    return lines


SEPARATOR = "-" * 51   # entry separator line used in dictionary output


def compound_ref_lines(comp1_id: str, comp1_form: str,
                        comp2_id: str, comp2_form: str) -> list:
    """Return only the two .COMPOUND lines (no blank lines)."""
    return [
        f".COMPOUND\tref_target={comp1_id}\t{comp1_form}",
        f".COMPOUND\tref_target={comp2_id}\t{comp2_form}",
    ]


# ──────────────────────────────────────────────────────────────────────────────
# LINE PATTERN MATCHING
# ──────────────────────────────────────────────────────────────────────────────

LEMMA_RE = r"L[0-9]+[a-zA-Z]*"

def _fields(line: str) -> list:
    return line.split(",")


def match_core_pair(line1: str, line2: str):
    """
    Core pattern:
      line1: ...,NP,N,N,<comp1_id>,PHON|LOG,<form1>
      line2: ...,NP,N,N;@2,<comp2_id>,PHON|LOG,<form2>
    Returns (prefix1, prefix2, comp1_id, comp1_form, comp2_id, comp2_form)
    or None.
    """
    f1 = _fields(line1)
    f2 = _fields(line2)
    if len(f1) < 5 or len(f2) < 5:
        return None

    if (f1[-4] == "N" and f2[-4] == "N;@2"
            and re.fullmatch(LEMMA_RE, f1[-3])
            and re.fullmatch(LEMMA_RE, f2[-3])
            and f1[-2] in ("PHON", "LOG")
            and f2[-2] in ("PHON", "LOG")
            and f1[-5] == "N" and f2[-5] == "N"):
        prefix1 = ",".join(f1[:-4])
        prefix2 = ",".join(f2[:-4])
        return (prefix1, prefix2,
                f1[-3], f1[-1],
                f2[-3], f2[-1])
    return None


def match_expanded1_pair(line1: str, line2: str):
    """
    Expanded pattern 1:
      line1: ...,NP,N,<comp1_id>,PHON|LOG,<form1>   (N present, compound lemma missing)
      line2: ...,NP,N;@2,<comp2_id>,PHON|LOG,<form2>
    Here the intermediate N (compound marker) is missing.

    Bug B fix: if f1[-5] already equals f1[-3] (comp1_id), the compound lemma
    token has already been inserted — skip to avoid duplicate insertion.

    Returns (prefix1, prefix2, comp1_id, comp1_form, comp2_id, comp2_form) or None.
    """
    if not EXPANDED_SEARCH_1:
        return None
    f1 = _fields(line1)
    f2 = _fields(line2)
    if len(f1) < 4 or len(f2) < 4:
        return None

    if (f1[-4] == "N" and f2[-4] == "N;@2"
            and re.fullmatch(LEMMA_RE, f1[-3])
            and re.fullmatch(LEMMA_RE, f2[-3])
            and f1[-2] in ("PHON", "LOG")
            and f2[-2] in ("PHON", "LOG")):
        # Must NOT be core case (f1[-5] != "N")
        if len(f1) >= 5 and f1[-5] == "N":
            return None
        if len(f2) >= 5 and f2[-5] == "N":
            return None

        # Bug B: check if a compound lemma token already sits at f1[-5]
        # i.e. pattern is already: ...,NP,<some_lemma>,N,<comp1_id>,...
        # In that case the slot is filled — do not re-insert.
        if len(f1) >= 5 and re.fullmatch(LEMMA_RE, f1[-5]):
            return None
        if len(f2) >= 5 and re.fullmatch(LEMMA_RE, f2[-5]):
            return None

        prefix1 = ",".join(f1[:-4])
        prefix2 = ",".join(f2[:-4])
        return (prefix1, prefix2,
                f1[-3], f1[-1],
                f2[-3], f2[-1])
    return None


def match_expanded2_pair(line1: str, line2: str):
    """
    Expanded pattern 2:
      line1: ...,N,N,<comp1_id>,PHON|LOG,<form1>   (no NP before N)
      line2: ...,N,N;@2,<comp2_id>,PHON|LOG,<form2>
    Returns same tuple or None.
    """
    if not EXPANDED_SEARCH_2:
        return None
    f1 = _fields(line1)
    f2 = _fields(line2)
    if len(f1) < 4 or len(f2) < 4:
        return None

    if (f1[-4] == "N" and f2[-4] == "N;@2"
            and re.fullmatch(LEMMA_RE, f1[-3])
            and re.fullmatch(LEMMA_RE, f2[-3])
            and f1[-2] in ("PHON", "LOG")
            and f2[-2] in ("PHON", "LOG")
            and len(f1) >= 5 and f1[-5] == "N"
            and len(f2) >= 5 and f2[-5] == "N"):
        # No NP just before the marker N
        no_np1 = len(f1) < 6 or f1[-6] != "NP"
        no_np2 = len(f2) < 6 or f2[-6] != "NP"
        if no_np1 and no_np2:
            prefix1 = ",".join(f1[:-4])
            prefix2 = ",".join(f2[:-4])
            return (prefix1, prefix2,
                    f1[-3], f1[-1],
                    f2[-3], f2[-1])
    return None


def detect_pair(line1: str, line2: str):
    """
    Try all patterns. Returns (match_type, result_tuple) or (None, None).
    match_type: 'core' | 'exp1' | 'exp2'
    """
    r = match_core_pair(line1, line2)
    if r:
        return "core", r
    r = match_expanded1_pair(line1, line2)
    if r:
        return "exp1", r
    r = match_expanded2_pair(line1, line2)
    if r:
        return "exp2", r
    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# LINE INSERTION
# ──────────────────────────────────────────────────────────────────────────────

def insert_compound_lemma_core(line1: str, line2: str, new_id: str) -> tuple:
    """
    Core case: insert new_id between the marker N and the component N.
    ...,NP,N,N,<comp1>,...  →  ...,NP,N,<new_id>,N,<comp1>,...
    """
    f1 = _fields(line1)
    f2 = _fields(line2)
    f1.insert(len(f1) - 4, new_id)
    f2.insert(len(f2) - 4, new_id)
    return ",".join(f1), ",".join(f2)


def insert_compound_lemma_exp1(line1: str, line2: str, new_id: str) -> tuple:
    """
    Expanded1 case:
      IN  line1: ...,NP,N,<comp1_id>,PHON|LOG,<form1>
      OUT line1: ...,NP,N,<new_id>,N,<comp1_id>,PHON|LOG,<form1>

      IN  line2: ...,NP,N;@2,<comp2_id>,PHON|LOG,<form2>
      OUT line2: ...,NP,N,<new_id>,N;@2,<comp2_id>,PHON|LOG,<form2>
    """
    f1 = _fields(line1)
    f2 = _fields(line2)

    # line1: last 4 = [N, comp1_id, PHON|LOG, form1]
    # target:         [N, new_id, N, comp1_id, PHON|LOG, form1]
    idx1 = len(f1) - 4   # points at existing N
    f1.insert(idx1 + 1, "N")      # duplicate N after existing N
    f1.insert(idx1 + 1, new_id)   # insert new_id between the two Ns
    # Result: [..., N, new_id, N, comp1_id, PHON, form1]

    # line2: last 4 = [N;@2, comp2_id, PHON|LOG, form2]
    # target:         [N, new_id, N;@2, comp2_id, PHON|LOG, form2]
    idx2 = len(f2) - 4   # points at N;@2
    f2.insert(idx2, new_id)   # insert new_id before N;@2
    f2.insert(idx2, "N")      # insert N before new_id
    # Result: [..., N, new_id, N;@2, comp2_id, PHON, form2]

    return ",".join(f1), ",".join(f2)


def insert_compound_lemma_exp2(line1: str, line2: str, new_id: str) -> tuple:
    """
    Expanded2 case: same structure as core.
    ...,N,N,<comp1>,...  →  ...,N,<new_id>,N,<comp1>,...
    """
    return insert_compound_lemma_core(line1, line2, new_id)


def apply_insertion(match_type: str, line1: str, line2: str, new_id: str) -> tuple:
    if match_type == "core":
        return insert_compound_lemma_core(line1, line2, new_id)
    elif match_type == "exp1":
        return insert_compound_lemma_exp1(line1, line2, new_id)
    elif match_type == "exp2":
        return insert_compound_lemma_exp2(line1, line2, new_id)
    return line1, line2


# ──────────────────────────────────────────────────────────────────────────────
# PROCESS A SINGLE TEXT FILE
# ──────────────────────────────────────────────────────────────────────────────

def process_text_file(path: str,
                      entries: dict,
                      used_nums: set,
                      dict_changes: dict,
                      new_dict_entries: dict) -> tuple:
    """
    Process one text file.
    Returns (new_lines, revised_pairs, stats).
      revised_pairs : list of (line_no1, orig1, new1, line_no2, orig2, new2, match_type)
      stats         : dict with per-file counters
    Side-effects: may add to dict_changes and new_dict_entries.
    """
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    new_lines = list(lines)
    revised_pairs = []

    stats = {
        "pairs_detected": 0,
        "core_fixes": 0,
        "expanded_fixes": 0,
        "new_ids_created": 0,
        "dict_entries_added": 0,
        "unchanged_lines": 0,
    }

    i = 0
    while i < len(new_lines) - 1:
        line1 = new_lines[i]
        line2 = new_lines[i + 1]

        match_type, result = detect_pair(line1, line2)
        if match_type is None:
            stats["unchanged_lines"] += 1
            i += 1
            continue

        stats["pairs_detected"] += 1
        (prefix1, prefix2,
         comp1_id, comp1_form,
         comp2_id, comp2_form) = result

        compound_form = comp1_form + comp2_form
        new_id = None
        was_new = False

        # 1. Dictionary search
        if DICT_SEARCH:
            new_id = find_compound_in_dict(compound_form, entries)
            if new_id and DICT_REFINE:
                existing = entries[new_id]["fields"].get(".COMPOUND", [])
                if not existing:
                    ref_lines = compound_ref_lines(comp1_id, comp1_form,
                                                   comp2_id, comp2_form)
                    # Append only the .COMPOUND lines (no blank lines) to raw_lines
                    entries[new_id]["raw_lines"].extend(ref_lines)
                    entries[new_id]["fields"].setdefault(".COMPOUND", []).extend(
                        [f"ref_target={comp1_id}\t{comp1_form}",
                         f"ref_target={comp2_id}\t{comp2_form}"]
                    )
                    dict_changes[new_id] = list(entries[new_id]["raw_lines"])

        # 2. Generate new ID if needed
        if new_id is None:
            new_id = new_lemma_id(used_nums)
            was_new = True
            stats["new_ids_created"] += 1

            # 3. Create new dictionary entry
            if DICT_ENTRY_CREATE:
                entry_lines = build_new_entry(new_id,
                                              comp1_id, comp1_form,
                                              comp2_id, comp2_form,
                                              entries)
                entries[new_id] = {
                    "raw_lines": list(entry_lines),
                    "fields": _parse_fields(entry_lines)
                }
                new_dict_entries[new_id] = list(entry_lines)
                stats["dict_entries_added"] += 1

        # 4. Insert lemma ID into both lines
        out1, out2 = apply_insertion(match_type, line1, line2, new_id)
        new_lines[i]     = out1
        new_lines[i + 1] = out2

        revised_pairs.append((i + 1, line1, out1, i + 2, line2, out2, match_type))

        if match_type == "core":
            stats["core_fixes"] += 1
        else:
            stats["expanded_fixes"] += 1

        i += 2   # skip the processed pair

    # remaining unchanged lines
    stats["unchanged_lines"] += len(new_lines) - stats["pairs_detected"] * 2 - stats["unchanged_lines"]

    return new_lines, revised_pairs, stats


# ──────────────────────────────────────────────────────────────────────────────
# SERIALISE DICTIONARY
# ──────────────────────────────────────────────────────────────────────────────

def _entry_block(raw_lines: list) -> str:
    """
    Format a single dictionary entry as:
        SEPARATOR\\n
        === Lxxxxxx\\n
        .FIELD  value\\n
        ...\\n
        \\n          ← one trailing blank line

    raw_lines must NOT contain any trailing blank lines (parse_dictionary
    and build_new_entry both guarantee this).
    Separator lines (-----) embedded inside raw_lines are stripped out
    so none can accidentally appear inside the content block.
    """
    # Remove any stray separator or blank lines that may have crept in
    clean = [l for l in raw_lines if l.strip() != "" and not re.match(r"^-{10,}$", l.strip())]
    return SEPARATOR + "\n" + "\n".join(clean) + "\n\n"


def serialise_dict(entries: dict, original_path: str) -> str:
    """
    Re-serialise all entries preserving original order plus appending new ones.
    Format per entry:
        SEPARATOR
        === Lxxxxxx
        .FIELD  value
        ...
        <blank line>
    """
    original_order = []
    if os.path.isfile(original_path):
        with open(original_path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^===\s+(L\d+\S*)\s*$", line)
                if m:
                    original_order.append(m.group(1))

    seen = set()
    parts = []

    for lid in original_order:
        if lid in entries and lid not in seen:
            seen.add(lid)
            parts.append(_entry_block(entries[lid]["raw_lines"]))

    for lid, data in entries.items():
        if lid not in seen:
            parts.append(_entry_block(data["raw_lines"]))

    # Join without extra newlines between blocks; each block already ends with \n\n
    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# REVISED DICTIONARY HELPER
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_entry_revised(raw_lines: list) -> str:
    """
    Format a single entry for the *_revised file.
    No leading SEPARATOR for refined entries (they are already labelled by section
    header); new entries get a SEPARATOR.
    We simply output the content lines followed by a blank line.
    Stray separators / blanks inside raw_lines are removed.
    """
    clean = [l for l in raw_lines if l.strip() != "" and not re.match(r"^-{10,}$", l.strip())]
    return "\n".join(clean) + "\n\n"


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Load dictionary
    entries = parse_dictionary(DICT_FILE)
    used_nums = all_numeric_ids(entries)

    # Track changes for revised output
    dict_changes: dict     = {}  # lid → raw_lines of refined entries
    new_dict_entries: dict = {}  # lid → raw_lines of brand-new entries

    # Collect all .txt files from the input folder
    if not os.path.isdir(TEXT_FOLDER):
        print(f"[ERROR] Input folder not found: {TEXT_FOLDER}")
        return
    txt_files = sorted(Path(TEXT_FOLDER).glob("*.txt"))
    if not txt_files:
        print(f"[WARN]  No .txt files found in: {TEXT_FOLDER}")

    # Global summary counters
    total_files        = 0
    total_pairs        = 0
    total_core         = 0
    total_expanded     = 0
    total_new_ids      = 0
    total_dict_added   = 0
    total_unchanged    = 0
    output_files_saved = []

    # Accumulator for the single combined revised-text file
    all_revised_blocks = []

    # Process each text file
    for txt_path in txt_files:
        if not txt_path.is_file():
            print(f"[SKIP] File not found: {txt_path}")
            continue

        total_files += 1
        new_lines, revised_pairs, stats = process_text_file(
            str(txt_path), entries, used_nums, dict_changes, new_dict_entries
        )

        # Accumulate global stats
        total_pairs      += stats["pairs_detected"]
        total_core       += stats["core_fixes"]
        total_expanded   += stats["expanded_fixes"]
        total_new_ids    += stats["new_ids_created"]
        total_dict_added += stats["dict_entries_added"]
        total_unchanged  += stats["unchanged_lines"]

        # Determine output path for processed text
        if OVERWRITE_SOURCE:
            out_path = str(txt_path)
        else:
            stem = txt_path.stem
            ext  = txt_path.suffix
            out_path = os.path.join(OUTPUT_FOLDER, f"{stem}{ext}")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        output_files_saved.append(out_path)

        # Collect revised pairs for the combined revised-text file
        if SAVE_REVISED and revised_pairs:
            doc_header = (
                f"\n{'=' * 60}\n"
                f"  Document: {txt_path.name}\n"
                f"{'=' * 60}"
            )
            all_revised_blocks.append(doc_header)
            for (ln1, orig1, new1, ln2, orig2, new2, mtype) in revised_pairs:
                pattern_label = {
                    "core": "core pattern",
                    "exp1": "expanded pattern 1",
                    "exp2": "expanded pattern 2",
                }.get(mtype, mtype)
                block = (
                    f"  [Pattern: {pattern_label}]\n"
                    f"  Line {ln1} (original): {orig1}\n"
                    f"  Line {ln1} (revised) : {new1}\n"
                    f"  Line {ln2} (original): {orig2}\n"
                    f"  Line {ln2} (revised) : {new2}"
                )
                all_revised_blocks.append(block)

    # Write the single combined revised-text file
    if SAVE_REVISED and all_revised_blocks:
        rev_txt_path = os.path.join(OUTPUT_FOLDER, "all_revised_lines.txt")
        with open(rev_txt_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(all_revised_blocks) + "\n")
        output_files_saved.append(rev_txt_path)

    # Determine output path for processed dictionary
    if OVERWRITE_SOURCE:
        dict_out = DICT_FILE
    else:
        dict_stem = Path(DICT_FILE).stem
        dict_ext  = Path(DICT_FILE).suffix
        dict_out  = os.path.join(OUTPUT_FOLDER, f"{dict_stem}{dict_ext}")

    with open(dict_out, "w", encoding="utf-8") as f:
        f.write(serialise_dict(entries, DICT_FILE))
    output_files_saved.append(dict_out)

    # Write revised dictionary (refined + new entries only)
    if SAVE_REVISED and (dict_changes or new_dict_entries):
        rev_dict_lines = []

        if dict_changes:
            rev_dict_lines.append("# ====  REFINED ENTRIES  ====")
            rev_dict_lines.append(
                "# (existing entries that had .COMPOUND lines appended)\n"
            )
            for lid, raw in dict_changes.items():
                rev_dict_lines.append(_fmt_entry_revised(raw))

        if new_dict_entries:
            rev_dict_lines.append("# ====  NEW ENTRIES  ====")
            rev_dict_lines.append(
                "# (brand-new compound entries created during this run)\n"
            )
            for lid, raw in new_dict_entries.items():
                # New entries get a separator line in the revised file
                clean = [l for l in raw
                         if l.strip() != "" and not re.match(r"^-{10,}$", l.strip())]
                rev_dict_lines.append(SEPARATOR + "\n" + "\n".join(clean) + "\n\n")

        dict_stem = Path(DICT_FILE).stem
        dict_ext  = Path(DICT_FILE).suffix
        rev_dict_path = os.path.join(OUTPUT_FOLDER, f"{dict_stem}_revised{dict_ext}")
        with open(rev_dict_path, "w", encoding="utf-8") as f:
            f.write("\n".join(rev_dict_lines) + "\n")
        output_files_saved.append(rev_dict_path)

    # ── Logging summary ──────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print("  PROCESSING SUMMARY")
    print("=" * 55)
    print(f"  Files processed             : {total_files}")
    print(f"  Paired lines detected       : {total_pairs}")
    print(f"  Default-pattern fixes       : {total_core}")
    print(f"  Expanded-pattern fixes      : {total_expanded}")
    print(f"  New lemma IDs created       : {total_new_ids}")
    print(f"  Dictionary entries added    : {total_dict_added}")
    print(f"  Unchanged lines             : {total_unchanged}")
    print(f"  Source files overwritten    : {OVERWRITE_SOURCE}")
    print(f"  Output files saved          : {len(output_files_saved)}")
    for p in output_files_saved:
        print(f"    -> {p}")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()
