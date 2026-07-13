# Version: 2.0.0
# Changes from 1.0.1: .RELATED renamed to .MKTARGETNEW; Report 2 = entries
# normalised, Report 3 = entries added.
"""
mk_lemma_processor.py
=====================
Finds L099999 occurrences in text files, replaces them with new unique IDs,
creates corresponding makura-kotoba dictionary entries, and optionally
normalises existing makura-kotoba entries that are missing .COMPOUND /
.MKTARGETNEW lines.

Package-based version — uses src/oncoj for all I/O.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# ══════════════════════════════════════════════════════════════════════════════
#  USER SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

TEXT_FOLDER   = "data/xml/text"              # folder containing .xml files to process
DICT_FILE     = "data/xml/dict/dictionary.xml"  # dictionary file path
OUTPUT_FOLDER = "data/xml/text"              # folder for all output files

OVERWRITE_SOURCE = False  # True  → overwrite source .txt files in-place
                           # False → write *_processed.txt to OUTPUT_FOLDER

LEMMA_PREFIX = "L"   # prefix for newly generated IDs (L, N, F, T, …)
LEMMA_DIGITS = 6     # zero-padded width  (6 → L000001)
LEMMA_START  = 1     # minimum numeric value for new IDs

TARGET_ID = "L099999"   # the exact sentinel token to hunt for

CREATE_DICT_ENTRIES = True   # True  → add new MK entries to the dictionary

RELATED_TOP_N = 1   # how many top-frequency target words to emit per entry

NORMALISE_EXISTING = True   # True  → fill missing .COMPOUND/.MKTARGETNEW in
                             #         existing MK entries

REPORT_MODIFIED_LINES = "report_modified_lines.txt"
REPORT_DICT_MODIFIED  = "report_dict_modified.txt"
REPORT_DICT_ADDED     = "report_dict_added.txt"


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import re
from collections import Counter
from datetime import datetime

from coj.core.corpus import CorpusDocument, CorpusLine
from coj.core.dictionary import Dictionary, DictEntry
from coj.core.lemma_id import IDGenerator, LemmaID
from coj.core.kana import phonemic_to_kana
from coj.core.tags import PHON_TAGS, strip_disambig


# ══════════════════════════════════════════════════════════════════════════════
#  SENTINEL REPLACEMENT
# ══════════════════════════════════════════════════════════════════════════════

def _replace_sentinel(cl: CorpusLine, new_id: str,
                      target_id: str = TARGET_ID) -> None:
    """
    Replace every occurrence of *target_id* in *cl* with *new_id*.

    Handles both field-list mode (mutates ``_fields_storage``) and XML mode
    (sets ``lemma`` attribute on the leaf element and any ancestor that carries
    the sentinel as an embedded lemma attribute).
    """
    if cl._leaf_elem is not None:
        seen: set[int] = set()
        for elem in [cl._leaf_elem] + cl._ancestors:
            eid = id(elem)
            if eid not in seen and elem.get("lemma") == target_id:
                elem.set("lemma", new_id)
                seen.add(eid)
    else:
        cl._fields_storage[:] = [
            new_id if f == target_id else f for f in cl._fields_storage
        ]


# ══════════════════════════════════════════════════════════════════════════════
#  MK BLOCK GROUPING
# ══════════════════════════════════════════════════════════════════════════════

def _is_sentinel(cl: CorpusLine) -> bool:
    return TARGET_ID in cl.fields


def _block_tag(cl: CorpusLine) -> str:
    """Return the field immediately before TARGET_ID (identifies the MK block)."""
    try:
        idx = cl.fields.index(TARGET_ID)
        return cl.fields[idx - 1] if idx > 0 else ""
    except ValueError:
        return ""


def collect_mk_blocks(doc: CorpusDocument) -> list[list[CorpusLine]]:
    """
    Return a list of MK blocks; each block is a list of CorpusLine objects
    that all carry TARGET_ID and share the same immediately-preceding tag.
    """
    blocks: list[list[CorpusLine]] = []
    current_block: list[CorpusLine] = []
    current_tag = None

    for cl in doc.all_corpus_lines():
        if _is_sentinel(cl):
            tag = _block_tag(cl)
            if current_block and tag == current_tag:
                current_block.append(cl)
            else:
                if current_block:
                    blocks.append(current_block)
                current_block = [cl]
                current_tag   = tag
        else:
            if current_block:
                blocks.append(current_block)
                current_block = []
                current_tag   = None

    if current_block:
        blocks.append(current_block)

    return blocks


# ══════════════════════════════════════════════════════════════════════════════
#  COMPOUND INFO  (component lemma IDs → phonemic forms)
# ══════════════════════════════════════════════════════════════════════════════

def build_compound_info(block: list[CorpusLine],
                        own_id: str) -> list[tuple[str, str]]:
    """
    For each line in the block, find the first component lemma ID (not own_id)
    and its associated phonemic form.  Returns a list of (lemma_id, form) pairs
    in the order they appear, deduplicating by lemma ID.
    """
    seen_order:  list[str]      = []
    phon_by_id:  dict[str, str] = {}

    for cl in block:
        fields = cl.fields
        try:
            sentinel_pos = fields.index(TARGET_ID)
        except ValueError:
            continue

        # Fields after the sentinel: [sub_lemma, ..., PHON_TAG, word_form]
        sub = fields[sentinel_pos + 1:]
        top_id    = None
        line_phon = ""

        i = 0
        while i < len(sub):
            f = sub[i]
            if LemmaID.is_valid(f) and f != own_id:
                if top_id is None:
                    top_id = f
                # Look for the phon tag and form immediately after
                for j in range(i + 1, min(i + 3, len(sub))):
                    if strip_disambig(sub[j]) in PHON_TAGS and j + 1 < len(sub):
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
#  MKTARGET WORD  (first annotated word after the block)
# ══════════════════════════════════════════════════════════════════════════════

def find_mktarget_words(block_end_cl: CorpusLine,
                        all_lines: list[CorpusLine],
                        top_n: int) -> list[tuple[str, str]]:
    """
    Walk forward from the line after block_end_cl to find the first
    annotated phonemic word(s).  Returns up to top_n (lemma_id, form) pairs.
    """
    results: list[tuple[str, str]] = []
    started = False

    for cl in all_lines:
        if not started:
            if cl is block_end_cl:
                started = True
            continue
        if cl.word_form and cl.is_annotated:
            results.append((str(cl.lemma_id), cl.word_form))
            if len(results) >= top_n:
                break
        elif results:
            break

    return results


def find_mktarget_words_multi(block_end_lines: list[CorpusLine],
                               all_lines: list[CorpusLine],
                               top_n: int) -> list[tuple[str, str]]:
    freq: Counter        = Counter()
    seen: dict[str, str] = {}

    for end_cl in block_end_lines:
        for lid, phon in find_mktarget_words(end_cl, all_lines, top_n=1):
            freq[phon] += 1
            seen.setdefault(phon, lid)

    return [(seen[ph], ph) for ph, _ in freq.most_common(top_n) if ph in seen]


# ══════════════════════════════════════════════════════════════════════════════
#  BUILD A NEW MK DICTIONARY ENTRY
# ══════════════════════════════════════════════════════════════════════════════

def build_mk_entry(new_id: str,
                   compound_info: list[tuple[str, str]],
                   mktarget_info: list[tuple[str, str]]) -> DictEntry:
    form    = "".join(ph for _, ph in compound_info if ph)
    kana    = phonemic_to_kana(form)
    rel_ph  = ", ".join(ph for _, ph in mktarget_info) if mktarget_info else "???"
    meaning = f"[MK for {rel_ph}]"

    entry = DictEntry(new_id)
    entry.set(".GLOSS",   "EPITHET")
    entry.set(".MEANING", [meaning])
    entry.set(".FORM",    [form])
    entry.set(".KANA",    [kana])
    entry.set(".POS",     "makura kotoba")
    for lid, ph in compound_info:
        entry.append(".COMPOUND",    f"ref_target={lid}\t{ph}")
    for lid, ph in mktarget_info:
        entry.append(".MKTARGETNEW", f"ref_target={lid}\t{ph}")

    return entry


# ══════════════════════════════════════════════════════════════════════════════
#  NORMALISE EXISTING MK ENTRIES
# ══════════════════════════════════════════════════════════════════════════════

def normalise_mk_entry(entry: DictEntry,
                       all_lines: list[CorpusLine],
                       top_n: int) -> list[str]:
    """
    Fill missing .COMPOUND / .MKTARGETNEW fields on an existing MK entry.
    Returns a list of human-readable descriptions of changes made (empty = none).
    """
    if entry.get_first(".POS") != "makura kotoba":
        return []
    has_compound   = bool(entry.get_all(".COMPOUND"))
    has_mktarget   = bool(entry.get_all(".MKTARGETNEW"))
    if has_compound and has_mktarget:
        return []

    eid = str(entry.eid)
    block_lines: list[CorpusLine]     = []
    block_end_cls: list[CorpusLine]   = []

    # Scan all_lines to find blocks that carry this MK entry's ID
    i = 0
    while i < len(all_lines):
        cl = all_lines[i]
        if eid in cl.fields:
            while i < len(all_lines) and eid in all_lines[i].fields:
                block_lines.append(all_lines[i])
                i += 1
            block_end_cls.append(all_lines[i - 1])
        else:
            i += 1

    if not block_lines:
        return []

    added: list[str] = []

    if not has_compound:
        compound_info = build_compound_info(block_lines, own_id=eid)
        entry.remove(".COMPOUND")
        for lid, ph in compound_info:
            entry.append(".COMPOUND", f"ref_target={lid}\t{ph}")
        added.extend(f".COMPOUND ref_target={lid} {ph}" for lid, ph in compound_info)

    if not has_mktarget:
        mktarget_info = find_mktarget_words_multi(block_end_cls, all_lines, top_n)
        entry.remove(".MKTARGETNEW")
        for lid, ph in mktarget_info:
            entry.append(".MKTARGETNEW", f"ref_target={lid}\t{ph}")
        added.extend(f".MKTARGETNEW ref_target={lid} {ph}" for lid, ph in mktarget_info)

        # Fix placeholder meaning
        meaning = entry.get_first(".MEANING") or ""
        if "???" in meaning and mktarget_info:
            rel_ph = ", ".join(ph for _, ph in mktarget_info)
            entry.set(".MEANING", [f"[MK for {rel_ph}]"])

    return added


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def process_files() -> None:
    if not os.path.isdir(TEXT_FOLDER):
        sys.exit(f"[ERROR] TEXT_FOLDER '{TEXT_FOLDER}' does not exist.")

    dictionary = Dictionary.from_file(DICT_FILE)
    id_gen     = IDGenerator(
        existing=dictionary.used_numbers(),
        start=LEMMA_START,
        prefix=LEMMA_PREFIX,
        digits=LEMMA_DIGITS,
    )

    # Reserve all numeric IDs already present in the text files
    for fname in os.listdir(TEXT_FOLDER):
        if fname.endswith(".xml"):
            with open(os.path.join(TEXT_FOLDER, fname), encoding="utf-8") as fh:
                for tok in re.findall(r'[A-Za-z](\d+)[a-z]*', fh.read()):
                    id_gen.reserve(int(tok))

    # Map .FORM → entry ID for dedup
    form_to_id: dict[str, str] = {}
    for entry in dictionary:
        form = entry.get_first(".FORM")
        if form:
            form_to_id[form] = str(entry.eid)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    total_files        = 0
    total_replacements = 0
    total_new_ids      = 0
    total_dict_added   = 0
    total_normalised   = 0

    report_modified:   list[tuple]     = []
    report_added:      list[DictEntry] = []
    report_normalised: list[tuple]     = []

    form_cache: dict[str, str] = {}

    # ── Pass 1: replace TARGET_ID in all text files ────────────────────────────
    txt_files = sorted(f for f in os.listdir(TEXT_FOLDER) if f.endswith(".xml"))

    all_docs: dict[str, CorpusDocument] = {}
    for fname in txt_files:
        all_docs[fname] = CorpusDocument.from_file(os.path.join(TEXT_FOLDER, fname))

    for fname, doc in all_docs.items():
        total_files += 1
        blocks = collect_mk_blocks(doc)

        for block in blocks:
            # Derive combined form to check for an existing entry
            compound_info_tmp = build_compound_info(block, own_id="")
            form_tmp = "".join(ph for _, ph in compound_info_tmp if ph)

            if form_tmp in form_cache:
                new_id = form_cache[form_tmp]
            elif form_tmp in form_to_id:
                new_id = form_to_id[form_tmp]
                form_cache[form_tmp] = new_id
            else:
                new_id = str(id_gen.next_id())
                form_cache[form_tmp] = new_id
                total_new_ids += 1

            # Replace TARGET_ID with new_id in each line of the block
            for cl in block:
                old_text = cl.to_text()
                _replace_sentinel(cl, new_id)
                new_text  = cl.to_text()
                if old_text != new_text:
                    total_replacements += 1
                    report_modified.append((fname, old_text, new_text))

            # Create dictionary entry if needed
            if CREATE_DICT_ENTRIES and new_id not in dictionary:
                compound_info = build_compound_info(block, own_id=new_id)
                # Find the target word: walk the doc's corpus lines
                all_cls       = doc.all_corpus_lines()
                mktarget_info = find_mktarget_words(block[-1], all_cls, RELATED_TOP_N)

                new_entry = build_mk_entry(new_id, compound_info, mktarget_info)
                dictionary.add(new_entry)
                form_to_id[form_tmp] = new_id
                total_dict_added += 1
                report_added.append(new_entry)

        # Write corpus output
        if OVERWRITE_SOURCE:
            out_path = os.path.join(TEXT_FOLDER, fname)
        else:
            base, ext = os.path.splitext(fname)
            out_path  = os.path.join(OUTPUT_FOLDER, f"{base}_processed{ext}")
        doc.to_file(out_path)

    # ── Pass 2: normalise existing MK entries ──────────────────────────────────
    if NORMALISE_EXISTING:
        # Flatten all corpus lines across all docs (after replacement)
        all_cls: list[CorpusLine] = []
        for doc in all_docs.values():
            all_cls.extend(doc.all_corpus_lines())

        for entry in dictionary:
            added = normalise_mk_entry(entry, all_cls, RELATED_TOP_N)
            if added:
                total_normalised += 1
                report_normalised.append((str(entry.eid), added))

    # ── Save dictionary ────────────────────────────────────────────────────────
    if OVERWRITE_SOURCE:
        dict_save = DICT_FILE
    else:
        dict_save = os.path.join(OUTPUT_FOLDER, os.path.basename(DICT_FILE))

    dictionary.to_file(dict_save)

    # ── Write reports ──────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    r1 = os.path.join(OUTPUT_FOLDER, REPORT_MODIFIED_LINES)
    with open(r1, "w", encoding="utf-8") as fh:
        fh.write(f"REPORT 1 · MODIFIED LINES  ({ts})\n{'='*70}\n\n")
        if not report_modified:
            fh.write("No lines were modified.\n")
        else:
            for fn, old, new in report_modified:
                fh.write(f"File : {fn}\n  OLD: {old}\n  NEW: {new}\n\n")

    r2 = os.path.join(OUTPUT_FOLDER, REPORT_DICT_MODIFIED)
    with open(r2, "w", encoding="utf-8") as fh:
        fh.write(f"REPORT 2 · DICTIONARY ENTRIES MODIFIED  ({ts})\n{'='*70}\n\n")
        if not report_normalised:
            fh.write("No entries were normalised.\n")
        else:
            for eid, added_lines in report_normalised:
                entry = dictionary.get(eid)
                fh.write(f"Entry: {eid}\nLines added:\n")
                for al in added_lines:
                    fh.write(f"  {al}\n")
                fh.write("\nFull entry after normalisation:\n")
                if entry:
                    fh.write(entry.to_text())
                fh.write("\n" + "-"*50 + "\n\n")

    r3 = os.path.join(OUTPUT_FOLDER, REPORT_DICT_ADDED)
    with open(r3, "w", encoding="utf-8") as fh:
        fh.write(f"REPORT 3 · NEW DICTIONARY ENTRIES ADDED  ({ts})\n{'='*70}\n\n")
        if not report_added:
            fh.write("No entries were added.\n")
        else:
            for ne in report_added:
                fh.write(ne.to_text() + "\n")

    print()
    print("=" * 55)
    print("  PROCESSING SUMMARY")
    print("=" * 55)
    print(f"  Files processed              : {total_files}")
    print(f"  Total replacements           : {total_replacements}")
    print(f"  New lemma IDs created        : {total_new_ids}")
    print(f"  Dictionary entries added     : {total_dict_added}")
    print(f"  Dictionary entries normalised: {total_normalised}")
    print(f"  Source files overwritten     : {OVERWRITE_SOURCE}")
    print("=" * 55)
    print()


if __name__ == "__main__":
    print("mk_lemma_processor  (v2.0.0)")
    print("=" * 55)
    print(f"  Text folder   : {TEXT_FOLDER}")
    print(f"  Dictionary    : {DICT_FILE}")
    print(f"  Output folder : {OUTPUT_FOLDER}")
    print(f"  New ID prefix : {LEMMA_PREFIX}")
    print(f"  ID width      : {LEMMA_DIGITS} digits (start >= {LEMMA_START})")
    print(f"  Overwrite src : {OVERWRITE_SOURCE}")
    print(f"  Create entries: {CREATE_DICT_ENTRIES}")
    print(f"  Normalise MK  : {NORMALISE_EXISTING}")
    print(f"  Target top-N  : {RELATED_TOP_N}")
    print("=" * 55)
    print()
    process_files()
