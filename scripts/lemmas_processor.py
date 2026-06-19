# Version: 3.0.0
# Changes from 2.0.4: Report 1 = new ID lines, Report 1.5 = existing ID
# lines, Report 2 = normalised entries, Report 3 = new entries.
"""
lemmas_processor.py
===================
Standard lemma annotator — package-based version.
Uses src/oncoj for all corpus and dictionary I/O.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

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

# ── POS-annotation mode ───────────────────────────────────────────────────────
AUTO_POS_QUERY  = "N"        # "N", "NP", "VB", "ALL!" — never empty
AUTO_MATCH_MODE = "strict"   # "strict" | "loose"


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

from collections import defaultdict

from oncoj.corpus import CorpusDocument, CorpusLine
from oncoj.dictionary import Dictionary, DictEntry
from oncoj.lemma_id import IDGenerator
from oncoj.tags import strip_disambig


# ══════════════════════════════════════════════════════════════════════════════
#  DISAMBIGUATION
# ══════════════════════════════════════════════════════════════════════════════

def disambiguate(candidates: list[DictEntry], preceding_tag: str) -> DictEntry:
    """Score each candidate against the preceding syntactic tag; return the best."""
    best       = candidates[0]
    best_score = -1
    tag_upper  = preceding_tag.upper()

    for entry in candidates:
        gloss = (entry.get_first(".GLOSS") or "").upper()
        if not gloss:
            score = 0
        elif tag_upper.startswith(gloss):
            score = 3
        elif gloss in tag_upper:
            score = 2
        else:
            score = 0
        if score > best_score:
            best_score = score
            best       = entry

    return best


# ══════════════════════════════════════════════════════════════════════════════
#  POS MATCHING
# ══════════════════════════════════════════════════════════════════════════════

def pos_matches(tag: str, pos_query: str, mode: str) -> bool:
    if pos_query == "ALL!":
        return True
    base = strip_disambig(tag)
    if mode == "strict":
        return base == pos_query
    return pos_query.upper() in base.upper()


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS A SINGLE FILE — standard dictionary-lookup path
# ══════════════════════════════════════════════════════════════════════════════

def process_file_standard(
    doc: CorpusDocument,
    form_to_entries: dict[str, list[DictEntry]],
    new_id_cache: dict[str, str],
    report_existing: dict,
    stats: dict,
) -> None:
    """
    Pass 1: for each unannotated corpus line, insert the matching dictionary ID.
    Modifies the CorpusLine objects in-place inside *doc*.
    """
    for utt in doc:
        for cl in utt.lines:
            if not isinstance(cl, CorpusLine):
                continue
            if not cl.is_annotatable:
                stats["lines_already_lemma" if cl.is_annotated else "unchanged_lines"] += 1
                continue

            form = cl.word_form
            prev = cl.preceding_synt_tag() or ""

            if form in form_to_entries:
                candidates = form_to_entries[form]
                entry = (disambiguate(candidates, prev)
                         if ADVANCED_DISAMBIG and len(candidates) > 1
                         else candidates[0])
                if ADVANCED_DISAMBIG and len(candidates) > 1:
                    stats["disambiguations_applied"] += 1

                # Check POS filter on the preceding tag
                if not pos_matches(prev, AUTO_POS_QUERY if form not in new_id_cache else "ALL!", AUTO_MATCH_MODE):
                    stats["unchanged_lines"] += 1
                    continue

                raw_id   = str(entry.eid)
                num_part = raw_id.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
                lemma_id = f"{DICT_ID_PREFIX}{num_part}"
                original = cl.to_text()
                cl.insert_lemma(lemma_id)
                stats["dict_matches_inserted"] += 1
                report_existing[doc.filename].append((original, lemma_id))

            elif form in new_id_cache:
                lemma_id = new_id_cache[form]
                if not pos_matches(prev, "ALL!", "strict"):
                    stats["unchanged_lines"] += 1
                    continue
                original = cl.to_text()
                cl.insert_lemma(lemma_id)
                stats["dict_matches_inserted"] += 1
                stats["words_reused"] += 1
                report_existing[doc.filename].append((original, lemma_id))

            else:
                stats["unchanged_lines"] += 1


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS UNKNOWN WORDS — new ID path
# ══════════════════════════════════════════════════════════════════════════════

def process_unknown_words(
    doc: CorpusDocument,
    form_to_entries: dict[str, list[DictEntry]],
    id_gen: IDGenerator,
    new_id_cache: dict[str, str],
    dictionary: Dictionary,
    report_new: dict,
    report_new_entries: list,
    stats: dict,
) -> None:
    """
    Pass 2: assign new IDs to tokens absent from the dictionary.
    Modifies CorpusLine objects in-place.
    """
    # Collect distinct unknown forms in this document
    unknown_forms: dict[str, list[CorpusLine]] = {}
    for cl in doc.all_corpus_lines():
        if not cl.is_annotatable:
            continue
        form = cl.word_form
        if form and form not in form_to_entries:
            unknown_forms.setdefault(form, []).append(cl)

    for form, lines in unknown_forms.items():
        if form in new_id_cache:
            lemma_id = new_id_cache[form]
        else:
            print(f"\n  [NEW] '{form}' — not in dictionary, "
                  f"found {len(lines)} time(s) in {doc.filename} "
                  f"→ auto-annotating POS='{AUTO_POS_QUERY}', mode='{AUTO_MATCH_MODE}'")

            lemma_id = str(id_gen.next_id(prefix=LEMMA_PREFIX))
            new_id_cache[form] = lemma_id
            stats["new_ids_created"] += 1

            if DICT_ENTRY_CREATE:
                entry = DictEntry.blank(lemma_id, form)
                dictionary.add(entry)
                report_new_entries.append((lemma_id, form))
                stats["dict_entries_added"] += 1

        annotated_count = 0
        for cl in lines:
            if not cl.is_annotatable:
                continue
            prev = cl.preceding_synt_tag() or ""
            if not pos_matches(prev, AUTO_POS_QUERY, AUTO_MATCH_MODE):
                continue
            original = cl.to_text()
            cl.insert_lemma(lemma_id)
            report_new[doc.filename].append((original, lemma_id))
            stats["dict_matches_inserted"] += 1
            annotated_count += 1

        print(f"      → {lemma_id} inserted on {annotated_count} line(s)")


# ══════════════════════════════════════════════════════════════════════════════
#  WRITE REPORTS
# ══════════════════════════════════════════════════════════════════════════════

def save_reports(
    output_folder: str,
    report_new: dict,
    report_existing: dict,
    report_normalised: dict,
    report_new_entries: list,
) -> None:
    os.makedirs(output_folder, exist_ok=True)

    def write_line_report(path, title, records_by_file):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{title}\n")
            fh.write("══════════════════════════════════════════════════════\n")
            if not records_by_file:
                fh.write("(none)\n")
            else:
                for fname, records in sorted(records_by_file.items()):
                    fh.write(f"\nFile: {fname}\n")
                    for original, lemma_id in records:
                        fh.write(f"  [{lemma_id}]\n")
                        fh.write(f"    {original}\n")
        print(f"  [REPORT] {path}")

    write_line_report(
        os.path.join(output_folder, "report1_new_id_lines.txt"),
        "REPORT 1 · Lines modified via newly generated ID",
        report_new,
    )
    write_line_report(
        os.path.join(output_folder, "report1_5_existing_id_lines.txt"),
        "REPORT 1.5 · Lines modified via existing dictionary ID",
        report_existing,
    )

    r2 = os.path.join(output_folder, "report2_normalized_entries.txt")
    with open(r2, "w", encoding="utf-8") as fh:
        fh.write("REPORT 2 · Dictionary entries modified by normalisation\n")
        fh.write("══════════════════════════════════════════════════════\n")
        if not report_normalised:
            fh.write("(none)\n")
        else:
            for eid, changes in report_normalised.items():
                fh.write(f"  {eid:<14}  {'; '.join(changes)}\n")
    print(f"  [REPORT] {r2}")

    r3 = os.path.join(output_folder, "report3_new_entries.txt")
    with open(r3, "w", encoding="utf-8") as fh:
        fh.write("REPORT 3 · New dictionary entries added\n")
        fh.write("══════════════════════════════════════════════════════\n")
        if not report_new_entries:
            fh.write("(none)\n")
        else:
            fh.write(f"{'ID':<12}  FORM\n")
            fh.write(f"{'-'*12}  {'-'*20}\n")
            for lemma_id, form in report_new_entries:
                fh.write(f"{lemma_id:<12}  {form}\n")
    print(f"  [REPORT] {r3}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def process_files() -> None:
    if not os.path.isdir(TEXT_FOLDER):
        sys.exit(f"[ERROR] Text folder not found: {TEXT_FOLDER}")

    dictionary = Dictionary.from_file(DICT_FILE)
    id_gen     = IDGenerator(
        existing=dictionary.used_numbers(),
        start=LEMMA_START,
        prefix=LEMMA_PREFIX,
        digits=LEMMA_DIGITS,
    )

    # Build form → [DictEntry] lookup
    form_to_entries: dict[str, list[DictEntry]] = defaultdict(list)
    for entry in dictionary:
        for form in entry.get_all(".FORM"):
            form_to_entries[form].append(entry)

    new_id_cache: dict[str, str] = {}

    report_new:         dict = defaultdict(list)   # Report 1
    report_existing:    dict = defaultdict(list)   # Report 1.5
    report_new_entries: list = []                  # Report 3

    stats = {
        "files_processed"        : 0,
        "lines_already_lemma"    : 0,
        "dict_matches_inserted"  : 0,
        "disambiguations_applied": 0,
        "new_ids_created"        : 0,
        "words_reused"           : 0,
        "dict_entries_added"     : 0,
        "unchanged_lines"        : 0,
        "output_files_saved"     : 0,
    }

    txt_files = sorted(f for f in os.listdir(TEXT_FOLDER) if f.lower().endswith(".txt"))
    if not txt_files:
        print(f"[INFO] No .txt files found in '{TEXT_FOLDER}'.")
        return

    for filename in txt_files:
        filepath = os.path.join(TEXT_FOLDER, filename)
        print(f"\n  Processing: {filename}")

        doc = CorpusDocument.from_file(filepath)

        process_file_standard(doc, form_to_entries, new_id_cache, report_existing, stats)
        process_unknown_words(doc, form_to_entries, id_gen, new_id_cache,
                              dictionary, report_new, report_new_entries, stats)

        if OVERWRITE_SOURCE:
            out_path = filepath
        else:
            os.makedirs(OUTPUT_FOLDER, exist_ok=True)
            base, ext = os.path.splitext(filename)
            out_path  = os.path.join(OUTPUT_FOLDER, f"{base}_processed{ext}")

        doc.to_file(out_path)
        stats["files_processed"]    += 1
        stats["output_files_saved"] += 1
        mode = "overwritten" if OVERWRITE_SOURCE else f"→ '{os.path.basename(out_path)}'"
        print(f"  [OK] {filename} {mode}")

    # Normalise and save dictionary
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    if NORMALIZE_DICT:
        report_normalised = dictionary.normalise_all()
    else:
        report_normalised = {}

    if OVERWRITE_SOURCE:
        dict_out = DICT_FILE
    else:
        dict_base = os.path.splitext(os.path.basename(DICT_FILE))[0]
        dict_out  = os.path.join(OUTPUT_FOLDER, f"{dict_base}_processed.txt")

    dictionary.to_file(dict_out)
    print(f"\n  [OK] Dictionary written: {dict_out}")

    print()
    print("══════════════════════════════════════════════════════")
    print("  PROCESSING SUMMARY")
    print("══════════════════════════════════════════════════════")
    print(f"  Files processed               : {stats['files_processed']}")
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

    save_reports(OUTPUT_FOLDER, report_new, report_existing,
                 report_normalised, report_new_entries)


if __name__ == "__main__":
    print("lemmas_processor  (v3.0.0)")
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
