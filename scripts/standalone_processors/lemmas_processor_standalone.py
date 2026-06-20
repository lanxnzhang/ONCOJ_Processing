# Version: 3.0.0
# Changes from 2.0.4: Report 1 = new ID lines, Report 1.5 = existing ID
# lines, Report 2 = normalised entries, Report 3 = new entries.
"""
lemmas_processor.py
===================
Standard lemma annotator.
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
LEMMA_DIGITS  = 6      # zero-padded width  (6 → N000001)
LEMMA_START   = 1      # minimum numeric value for new IDs

# ── Existing-entry ID rewrite ─────────────────────────────────────────────────
DICT_ID_PREFIX = "T"   # prefix applied when inserting an existing dict ID

# ── Core behaviour switches ───────────────────────────────────────────────────
OVERWRITE_SOURCE  = False  # True  → overwrite source .txt files in place
                            # False → write *_processed.txt to OUTPUT_FOLDER

DICT_ENTRY_CREATE = True   # True  → add a new entry when a word is absent

ADVANCED_DISAMBIG = True   # True  → score candidates against the preceding tag

NORMALIZE_DICT    = True   # True  → rewrite dictionary to canonical field order

# ── Existing-word POS behaviour ───────────────────────────────────────────────
EXISTING_WORDS_POS_LIMIT = False

# ── POS-annotation mode ───────────────────────────────────────────────────────
AUTO_POS_QUERY  = "N"        # "N", "NP", "VB", "ALL!" — never empty
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
# ══════════════════════════════════════════════════════════════════════════════

_KANA_RAW: list[tuple[str, str]] = [
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
    ("ye", "エ"), ("wi", "ヰ"), ("wo", "ヲ"),
    ("a", "ア"), ("i", "イ"), ("u", "ウ"), ("o", "オ"), ("e", "エ"),
]

_KANA_TABLE: list[tuple[str, str]] = sorted(_KANA_RAW, key=lambda x: -len(x[0]))


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


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

ENTRY_SEP  = "---------------------------------------------------"
ENTRY_HEAD = re.compile(r'^=== ([A-Za-z]\d+[a-z]*)$')
FORM_LINE  = re.compile(r'^\.(FORM)\s+(\S+)')
GLOSS_LINE = re.compile(r'^\.(GLOSS)\s+(\S+)')
LEMMA_RE   = re.compile(r'^[A-Za-z]\d+[a-z]*$')


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY LOADER
# ══════════════════════════════════════════════════════════════════════════════

def load_dictionary(dict_path: str):
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
            current_lemma = m.group(1) or ""
            current_gloss = ""
            m2 = re.search(r'\d+', m.group(1) or "")
            num = int(m2.group()) if m2 else 0
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
    m2 = re.search(r'\d+', lemma_id)
    num       = int(m2.group()) if m2 else 0
    new_block = build_entry_block(lemma_id, word_form)

    insert_after_sep: int | None = None
    for entry_num, sep_idx in sorted(entries_order, key=lambda x: x[0]):
        if entry_num < num:
            insert_after_sep = sep_idx
        else:
            break

    if insert_after_sep is None:
        for i, line in enumerate(new_block):
            raw_lines.insert(i, line)
        shift = len(new_block)
        entries_order[:] = [(en, si + shift) for en, si in entries_order]
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
            new_sep_idx = len(raw_lines)
            raw_lines.extend(new_block)
            entries_order.append((num, new_sep_idx))

        entries_order.sort(key=lambda x: x[0])


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY NORMALISER
# ══════════════════════════════════════════════════════════════════════════════

_REQUIRED_TAGS = [".GLOSS", ".MEANING", ".FORM", ".KANA", ".POS"]
_TAG_RE = re.compile(r'^(\.[A-Z]+(?:\[\d+\])?)\s*(.*)')


def normalize_dictionary(dict_path: str, report: "AnnotationReport") -> None:
    if not os.path.isfile(dict_path):
        print(f"[NORMALIZE] Dictionary not found: {dict_path}")
        return

    with open(dict_path, encoding="utf-8") as fh:
        raw = fh.read()

    blocks   = raw.split(ENTRY_SEP)
    out_blocks: list[str] = [blocks[0]]
    changed_entries: list[tuple[str, list[str]]] = []

    for block in blocks[1:]:
        lines = block.splitlines(keepends=True)

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

        m3 = ENTRY_HEAD.match(header_line)
        lemma_id = m3.group(1) if m3 else ""

        seen_required: set[str]  = set()
        existing: dict[str, str] = {}
        extra_lines: list[str]   = []

        for ln in body_lines:
            s = ln.rstrip("\r\n")
            if s == "":
                continue
            m = _TAG_RE.match(s)
            if m:
                raw_tag  = m.group(1)
                val      = m.group(2).strip()
                m4 = re.match(r'\.[A-Z]+', raw_tag)
                base_tag = m4.group() if m4 else raw_tag
                if base_tag in _REQUIRED_TAGS and base_tag not in seen_required:
                    existing[base_tag] = val
                    seen_required.add(base_tag)
                else:
                    extra_lines.append(ln if ln.endswith("\n") else ln + "\n")
            else:
                extra_lines.append(ln if ln.endswith("\n") else ln + "\n")

        if all(t in existing for t in _REQUIRED_TAGS):
            out_blocks.append(
                ENTRY_SEP + "\n"
                + header_line + "\n"
                + "".join(ln if ln.endswith("\n") else ln + "\n"
                          for ln in body_lines)
            )
            continue

        changes: list[str] = []
        new_body: list[str] = []

        for tag in _REQUIRED_TAGS:
            old_val = existing.get(tag)

            if old_val is not None:
                val = old_val
                if tag == ".KANA" and not val:
                    form_val = existing.get(".FORM", "")
                    if form_val:
                        val = phonemic_to_kana(form_val)
                        changes.append(f"filled {tag} = {val}")
            else:
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

    report.record_normalization(changed_entries)


# ══════════════════════════════════════════════════════════════════════════════
#  LINE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

PEN_RE  = re.compile(r'^[A-Z][A-Z0-9\-]*$')
LAST_RE = re.compile(r'^[A-Za-z]+$')


def analyse_line(fields: list[str]):
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
#  POS-ANNOTATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def pos_matches(field: str, pos_query: str, mode: str) -> bool:
    if pos_query == "ALL!":
        return True
    if mode == "strict":
        return field == pos_query
    return pos_query.upper() in field.upper()


def find_annotation_targets(fields: list[str],
                             pos_query: str,
                             match_mode: str) -> list[int]:
    n       = len(fields)
    targets = []
    for tag_idx in range(n - 2):
        tag  = fields[tag_idx]
        word = fields[tag_idx + 2]

        if not pos_matches(tag, pos_query, match_mode):
            continue
        if not LAST_RE.match(word):
            continue

        slot = fields[tag_idx + 1]
        if LEMMA_RE.match(slot):
            continue

        targets.append(tag_idx)

    return targets


# ══════════════════════════════════════════════════════════════════════════════
#  ANNOTATION REPORT  (with split Report 1 / Report 1.5)
# ══════════════════════════════════════════════════════════════════════════════

class AnnotationReport:
    def __init__(self):
        # Report 1: lines modified via newly generated ID
        self.new_id_lines: dict[str, list[tuple]] = defaultdict(list)
        # Report 1.5: lines modified via existing dictionary ID
        self.existing_id_lines: dict[str, list[tuple]] = defaultdict(list)
        # Report 2: normalised entries
        self.normalized_entries: list[tuple[str, list[str]]] = []
        # Report 3: new dictionary entries
        self.new_entries: list[tuple[str, str, str]] = []

    def record_normalization(self, changed_entries: list[tuple[str, list[str]]]) -> None:
        self.normalized_entries.extend(changed_entries)

    def record_existing_annotation(self, filename: str, line_no: int,
                                    original: str, lemma_id: str):
        self.existing_id_lines[filename].append((line_no, original.rstrip(), lemma_id))

    def record_new_annotation(self, filename: str, line_no: int,
                               original: str, lemma_id: str):
        self.new_id_lines[filename].append((line_no, original.rstrip(), lemma_id))

    def record_new_entry(self, lemma_id: str, word_form: str):
        kana = phonemic_to_kana(word_form)
        self.new_entries.append((lemma_id, word_form, kana))

    def save_reports(self, output_folder: str) -> None:
        os.makedirs(output_folder, exist_ok=True)

        def _write_line_report(path, title, records_by_file):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"{title}\n")
                fh.write("══════════════════════════════════════════════════════\n")
                if not records_by_file:
                    fh.write("(none)\n")
                else:
                    for fname, records in sorted(records_by_file.items()):
                        fh.write(f"\nFile: {fname}\n")
                        for line_no, original, lemma_id in records:
                            fh.write(f"  Line {line_no:>6}  [{lemma_id}]\n")
                            fh.write(f"           {original}\n")
            print(f"  [REPORT] {path}")

        r1_path = os.path.join(output_folder, "report1_new_id_lines.txt")
        _write_line_report(r1_path,
                           "REPORT 1 · Lines modified via newly generated ID",
                           self.new_id_lines)

        r15_path = os.path.join(output_folder, "report1_5_existing_id_lines.txt")
        _write_line_report(r15_path,
                           "REPORT 1.5 · Lines modified via existing dictionary ID",
                           self.existing_id_lines)

        # Report 2: normalised entries
        r2_path = os.path.join(output_folder, "report2_normalized_entries.txt")
        with open(r2_path, "w", encoding="utf-8") as fh:
            fh.write("REPORT 2 · Dictionary entries modified by normalisation\n")
            fh.write("══════════════════════════════════════════════════════\n")
            if not self.normalized_entries:
                fh.write("(none)\n")
            else:
                fh.write(f"{'ID':<14}  Changes\n")
                fh.write(f"{'-'*14}  {'-'*40}\n")
                for lemma_id, changes in self.normalized_entries:
                    fh.write(f"{lemma_id:<14}  {'; '.join(changes)}\n")
        print(f"  [REPORT] {r2_path}")

        # Report 3: new dictionary entries
        r3_path = os.path.join(output_folder, "report3_new_entries.txt")
        with open(r3_path, "w", encoding="utf-8") as fh:
            fh.write("REPORT 3 · New dictionary entries added\n")
            fh.write("══════════════════════════════════════════════════════\n")
            if not self.new_entries:
                fh.write("(none)\n")
            else:
                fh.write(f"{'ID':<12}  {'FORM':<20}  KANA\n")
                fh.write(f"{'-'*12}  {'-'*20}  {'-'*20}\n")
                for lemma_id, word_form, kana in self.new_entries:
                    fh.write(f"{lemma_id:<12}  {word_form:<20}  {kana}\n")
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

        if word_form in form_to_lemma:
            candidates = form_to_candidates[word_form]
            if ADVANCED_DISAMBIG and len(candidates) > 1:
                raw_lemma = disambiguate(candidates, preceding_tag, line_body)
                stats["disambiguations_applied"] += 1
            else:
                raw_lemma = form_to_lemma[word_form]

            m5 = re.search(r'\d+[a-z]*', raw_lemma)
            num_part = m5.group() if m5 else raw_lemma
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
            # Record in Report 1.5 (existing ID)
            report.record_existing_annotation(filename, line_no, line_body, lemma_id)

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
            # Reused new ID → also Report 1
            report.record_new_annotation(filename, line_no, line_body, lemma_id)

        else:
            stats["unchanged_lines"] += 1
            output_lines.append(raw_line)

    return output_lines


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS UNKNOWN WORDS  (POS-annotation path)
# ══════════════════════════════════════════════════════════════════════════════

def process_unknown_words(
    filename: str,
    lines: list[str],
    form_to_lemma: dict,
    id_gen: IDGenerator,
    new_id_cache: dict,
    dict_raw: list,
    entries_order: list,
    report: AnnotationReport,
    stats: dict,
) -> list[str]:
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

    output_lines = list(lines)

    for word_form, line_indices in unknown_forms.items():

        if word_form in new_id_cache:
            lemma_id   = new_id_cache[word_form]
            pos_query  = "ALL!"
            match_mode = "strict"
        else:
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

        annotated_count = 0
        for i in line_indices:
            raw_line  = output_lines[i]
            line_body = raw_line.rstrip("\n").rstrip("\r")
            trailing  = raw_line[len(line_body):]
            fields    = line_body.split(",")

            targets = find_annotation_targets(fields, pos_query, match_mode)
            n = len(fields)
            targets = [t for t in targets if t == n - 3]
            if not targets:
                continue

            for tag_idx in sorted(targets, reverse=True):
                fields.insert(tag_idx + 1, lemma_id)

            output_lines[i] = ",".join(fields) + trailing
            # Record in Report 1 (new ID)
            report.record_new_annotation(
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
    (form_to_lemma, form_to_candidates,
     existing_numbers, dict_raw, entries_order) = load_dictionary(DICT_FILE)

    id_gen = IDGenerator(existing_numbers, start=LEMMA_START)
    new_id_cache: dict[str, str] = {}
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

    if not os.path.isdir(TEXT_FOLDER):
        sys.exit(f"[ERROR] Text folder not found: {TEXT_FOLDER}")

    txt_files = sorted(
        f for f in os.listdir(TEXT_FOLDER) if f.lower().endswith(".txt")
    )

    if not txt_files:
        print(f"[INFO] No .txt files found in '{TEXT_FOLDER}'.")
        return

    for filename in txt_files:
        filepath = os.path.join(TEXT_FOLDER, filename)
        print(f"\n  Processing: {filename}")

        output_lines = process_file_standard(
            filename, filepath,
            form_to_lemma, form_to_candidates,
            id_gen, new_id_cache,
            dict_raw, entries_order,
            report, stats,
        )

        output_lines = process_unknown_words(
            filename, output_lines,
            form_to_lemma,
            id_gen, new_id_cache,
            dict_raw, entries_order,
            report, stats,
        )

        out_path = write_output(filename, filepath, output_lines)
        stats["files_processed"]    += 1
        stats["output_files_saved"] += 1
        mode = "overwritten" if OVERWRITE_SOURCE else f"→ '{os.path.basename(out_path)}'"
        print(f"  [OK] {filename} {mode}")

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    if OVERWRITE_SOURCE:
        dict_out_path = DICT_FILE
    else:
        dict_base = os.path.splitext(os.path.basename(DICT_FILE))[0]
        dict_out_path = os.path.join(OUTPUT_FOLDER, f"{dict_base}_processed.txt")

    with open(dict_out_path, "w", encoding="utf-8") as fh:
        fh.writelines(dict_raw)
    print(f"\n  [OK] Dictionary written: {dict_out_path}")

    if NORMALIZE_DICT:
        normalize_dictionary(dict_out_path, report)

    print()
    print("══════════════════════════════════════════════════════")
    print("  PROCESSING SUMMARY")
    print("══════════════════════════════════════════════════════")
    print(f"  Files processed               : {stats['files_processed']}")
    print(f"  Lines scanned                 : {stats['lines_scanned']}")
    print(f"  Lines already containing lemma: {stats['lines_already_lemma']}")
    print(f"  Lemma IDs inserted            : {stats['dict_matches_inserted']}")
    if ADVANCED_DISAMBIG:
        print(f"  Advanced disambiguations      : {stats['disambiguations_applied']}")
    print(f"  New IDs generated             : {stats['new_ids_created']}")
    print(f"  Repeated words reused         : {stats['words_reused']}")
    print(f"  Dictionary entries added      : {stats['dict_entries_added']}")
    print(f"  Unchanged / unmatched lines   : {stats['unchanged_lines']}")
    print(f"  Output files saved            : {stats['output_files_saved']}")
    print("══════════════════════════════════════════════════════")

    report.save_reports(OUTPUT_FOLDER)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("lemmas_processor_3.0.0")
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
