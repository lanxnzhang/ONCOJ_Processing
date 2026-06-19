# Version: 2.0.0
# Changes from 1.0.1: new group-detection algorithm; layered binary pairing
# for 3+ components; optional NP expansion.
"""
compound_lemma_processor.py
============================
Detects compound nouns in corpus text files, inserts shared lemma IDs,
and creates/refines dictionary entries.

Package-based version — uses src/oncoj for all I/O.

Algorithm:
1. Find every bare 'N' tag (no lemma after it) whose next fields form
   a sequence of component nouns (N, N;@2, N;@3, …).
2. For 3+ component nouns: pair in layers (binary tree from left).
3. Optional NP-expansion: detect NPs whose ALL immediate direct children
   are N / N;@2 / N;@3 …, insert a grouping N before them, then apply (1).
"""

import os
import re
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ══════════════════════════════════════════════════════════════════════════════
#  USER SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

from pathlib import Path

from oncoj.dictionary import Dictionary, DictEntry
from oncoj.lemma_id import IDGenerator
from oncoj.kana import phonemic_to_kana
from oncoj.tags import PHON_TAGS, strip_disambig


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS / HELPERS
# ══════════════════════════════════════════════════════════════════════════════

_LEMMA_RE = re.compile(r'^[A-Za-z]\d+[a-z]*$')
_N_AT_RE  = re.compile(r'^N(;@\d+)?$')


def _is_n_at(tag: str) -> bool:
    return bool(_N_AT_RE.match(tag))


def _is_lemma(token: str) -> bool:
    return bool(_LEMMA_RE.match(token))


# ══════════════════════════════════════════════════════════════════════════════
#  DICTIONARY HELPERS  (working with oncoj.Dictionary / DictEntry)
# ══════════════════════════════════════════════════════════════════════════════

def _pos_priority(entry: DictEntry) -> int:
    pos = (entry.get_first(".POS") or "").lower().strip()
    if pos == "noun":
        return 0
    if "noun" in pos:
        return 1
    return 100


def find_compound_in_dict(form: str, dictionary: Dictionary) -> "str | None":
    """Return the first entry ID whose .FORM list contains *form* (noun-preferred)."""
    candidates = []
    for entry in dictionary:
        if form in entry.get_all(".FORM"):
            candidates.append((str(entry.eid), _pos_priority(entry)))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


def build_compound_entry(new_id: str,
                         comp1_id: str, comp1_text_form: str,
                         comp2_id: str, comp2_text_form: str,
                         dictionary: Dictionary) -> DictEntry:
    """
    Build a new compound DictEntry.
    .FORM = corpus text form concatenation.
    .COMPOUND ref_target = canonical dictionary .FORM (per spec).
    """
    e1 = dictionary.get(comp1_id)
    e2 = dictionary.get(comp2_id)

    gloss1     = (e1.get_first(".GLOSS")   or "") if e1 else ""
    gloss2     = (e2.get_first(".GLOSS")   or "") if e2 else ""
    mean1      = (e1.get_first(".MEANING") or "") if e1 else ""
    mean2      = (e2.get_first(".MEANING") or "") if e2 else ""
    kana1      = (e1.get_first(".KANA")    or "") if e1 else ""
    kana2      = (e2.get_first(".KANA")    or "") if e2 else ""
    dict_form1 = (e1.get_first(".FORM")    or comp1_text_form) if e1 else comp1_text_form
    dict_form2 = (e2.get_first(".FORM")    or comp2_text_form) if e2 else comp2_text_form

    combined_form  = comp1_text_form + comp2_text_form
    combined_kana  = kana1 + kana2 if (kana1 or kana2) else phonemic_to_kana(combined_form)
    combined_gloss = (gloss1 + " " + gloss2).strip()
    combined_mean  = (mean1  + " " + mean2).strip()

    entry = DictEntry(new_id)
    entry.set(".GLOSS",    combined_gloss)
    entry.set(".MEANING",  [combined_mean])
    entry.set(".FORM",     [combined_form])
    entry.set(".KANA",     [combined_kana])
    entry.set(".POS",      "noun")
    entry.append(".COMPOUND", f"ref_target={comp1_id}\t{dict_form1}")
    entry.append(".COMPOUND", f"ref_target={comp2_id}\t{dict_form2}")
    return entry


def resolve_compound(comp1_id: str, comp1_text_form: str,
                     comp2_id: str, comp2_text_form: str,
                     dictionary: Dictionary,
                     id_gen: IDGenerator,
                     dict_changes: dict,
                     new_entries: dict) -> str:
    """
    Look up, refine, or create a dictionary entry for the compound.
    Returns the compound lemma ID.
    """
    combined = comp1_text_form + comp2_text_form
    new_id   = None

    if DICT_SEARCH:
        new_id = find_compound_in_dict(combined, dictionary)
        if new_id and DICT_REFINE:
            entry = dictionary.get(new_id)
            if entry and not entry.get_all(".COMPOUND"):
                e1 = dictionary.get(comp1_id)
                e2 = dictionary.get(comp2_id)
                df1 = (e1.get_first(".FORM") or comp1_text_form) if e1 else comp1_text_form
                df2 = (e2.get_first(".FORM") or comp2_text_form) if e2 else comp2_text_form
                entry.append(".COMPOUND", f"ref_target={comp1_id}\t{df1}")
                entry.append(".COMPOUND", f"ref_target={comp2_id}\t{df2}")
                dict_changes[new_id] = entry

    if new_id is None:
        new_id = str(id_gen.next_id())
        if DICT_ENTRY_CREATE:
            entry = build_compound_entry(new_id,
                                         comp1_id, comp1_text_form,
                                         comp2_id, comp2_text_form,
                                         dictionary)
            dictionary.add(entry)
            new_entries[new_id] = entry

    return new_id


# ══════════════════════════════════════════════════════════════════════════════
#  GROUP DETECTION  (operates on raw field lists, not CorpusLine objects)
# ══════════════════════════════════════════════════════════════════════════════
#
#  The group detector works on raw comma-split field lists because NP expansion
#  needs to insert fields before the parsed-line boundaries.  CorpusLine objects
#  are reconstructed from the mutated field lists after all processing.

def _find_marker_col(fields: list[str]) -> "int | None":
    """
    Find the column of a bare compound-marker N.
    Pattern: [...prefix..., N-or-N;@k, comp_lemma, PHON_TAG, word_form]
    Returns the leftmost N-at with no lemma immediately before it, or None.
    """
    n = len(fields)
    if n < 4:
        return None
    if not re.match(r'^[A-Za-z]+$', fields[-1]):
        return None
    if strip_disambig(fields[-2]) not in PHON_TAGS:
        return None
    if not _is_lemma(fields[-3]):
        return None

    for col in range(n - 4, -1, -1):
        if not _is_n_at(fields[col]):
            continue
        if col > 0 and _is_lemma(fields[col - 1]):
            continue
        return col
    return None


def _component_from_fields(fields: list[str]) -> "dict | None":
    n = len(fields)
    comp_id   = fields[-3] if n >= 3 and _is_lemma(fields[-3]) else None
    text_form = fields[-1] if n >= 1 else None
    if comp_id is None or text_form is None:
        return None
    return {"comp_id": comp_id, "text_form": text_form}


def find_compound_groups(raw_lines: list[list[str]]) -> list[dict]:
    """
    Scan field-lists for compound groups.  A group is a maximal consecutive
    sequence sharing a marker-N column, with component lemma IDs present.
    """
    groups: list[dict] = []
    n = len(raw_lines)
    i = 0
    while i < n:
        f = raw_lines[i]
        marker_col = _find_marker_col(f)
        if marker_col is None or f[marker_col] != "N":
            i += 1
            continue
        if len(f) > marker_col + 1 and _is_lemma(f[marker_col + 1]):
            i += 1
            continue

        comp0 = _component_from_fields(f)
        if comp0 is None:
            i += 1
            continue

        group_lines = [i]
        components  = [{"line_idx": i, "at_tag": f[marker_col], **comp0}]

        j = i + 1
        while j < n:
            fj = raw_lines[j]
            if len(fj) <= marker_col or fj[:marker_col] != f[:marker_col]:
                break
            at_tag = fj[marker_col]
            if not _is_n_at(at_tag) or at_tag == "N":
                break
            if len(fj) > marker_col + 1 and _is_lemma(fj[marker_col + 1]):
                break
            compj = _component_from_fields(fj)
            if compj is None:
                break
            group_lines.append(j)
            components.append({"line_idx": j, "at_tag": at_tag, **compj})
            j += 1

        if len(group_lines) < 2:
            i += 1
            continue

        groups.append({
            "start":      i,
            "end":        j - 1,
            "marker_col": marker_col,
            "lines":      group_lines,
            "components": components,
        })
        i = j

    return groups


# ══════════════════════════════════════════════════════════════════════════════
#  LAYERED PAIRING
# ══════════════════════════════════════════════════════════════════════════════

def pair_components_layered(components: list[dict],
                             dictionary: Dictionary,
                             id_gen: IDGenerator,
                             dict_changes: dict,
                             new_entries: dict) -> list[tuple[str, str, int]]:
    """
    Pair k components left-to-right in layers; return list of
    (compound_id, combined_text_form, layer).  Last entry = outermost compound.
    """
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
                cid = resolve_compound(id1, form1, id2, form2,
                                       dictionary, id_gen,
                                       dict_changes, new_entries)
                new_slots.append((cid, form1 + form2))
                results.append((cid, form1 + form2, layer))
                k += 2
            else:
                new_slots.append(slots[k])
                k += 1
        slots = new_slots
        layer += 1
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  NP EXPANSION  (optional)
# ══════════════════════════════════════════════════════════════════════════════

def _find_np_expansion_col(fields: list[str]) -> "int | None":
    n = len(fields)
    for col in range(n - 2, -1, -1):
        if fields[col] != "NP":
            continue
        at_tag = fields[col + 1]
        if not _is_n_at(at_tag):
            continue
        if col + 2 >= n or not _is_lemma(fields[col + 2]):
            continue
        return col
    return None


def np_expand(raw_lines: list[list[str]]) -> tuple[list[list[str]], list[tuple]]:
    """
    Insert a bare N before each N-at tag when all direct NP children are N-at.
    Returns (new_raw_lines, expansion_log).
    """
    working = [list(f) for f in raw_lines]
    log: list[tuple] = []
    n = len(working)
    i = 0
    while i < n:
        f = working[i]
        np_col = _find_np_expansion_col(f)
        if np_col is None:
            i += 1
            continue
        at_col = np_col + 1
        if at_col >= len(f) or f[at_col] != "N":
            i += 1
            continue
        if at_col > 0 and f[at_col - 1] == "N":
            i += 1
            continue
        if at_col + 1 >= len(f) or not _is_lemma(f[at_col + 1]):
            i += 1
            continue

        group = [i]
        j = i + 1
        while j < n:
            fj = working[j]
            if fj[:np_col + 1] != f[:np_col + 1]:
                break
            at_tag = fj[np_col + 1] if len(fj) > np_col + 1 else ""
            if not _is_n_at(at_tag) or at_tag == "N":
                break
            if np_col + 2 >= len(fj) or not _is_lemma(fj[np_col + 2]):
                break
            if np_col > 0 and fj[np_col] == "N":
                break
            group.append(j)
            j += 1

        if len(group) < 2:
            i += 1
            continue

        for idx in group:
            orig = list(working[idx])
            working[idx].insert(at_col, "N")
            log.append((idx, orig, list(working[idx])))

        i = j

    return working, log


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS A SINGLE TEXT FILE
# ══════════════════════════════════════════════════════════════════════════════

def process_text_file(path: str,
                      dictionary: Dictionary,
                      id_gen: IDGenerator,
                      dict_changes: dict,
                      new_entries: dict) -> tuple:
    """
    Returns (new_text_lines, revised_log, stats).
    raw_lines are plain strings (not CorpusLine objects) to allow field-level
    manipulation before round-tripping through CorpusDocument.
    """
    with open(path, encoding="utf-8") as f:
        orig_text_lines = f.read().splitlines()

    # Work on raw field lists for group detection / NP expansion
    raw = [line.split(",") for line in orig_text_lines]
    revised_log: list[tuple] = []
    stats = {
        "groups_detected": 0,
        "new_ids_created": 0,
        "dict_entries_added": 0,
        "np_expansions": 0,
    }

    if NP_EXPANSION:
        raw, exp_log = np_expand(raw)
        stats["np_expansions"] += len(exp_log)
        for idx, orig_f, new_f in exp_log:
            revised_log.append((idx + 1, [",".join(orig_f)], [",".join(new_f)], "np_expansion"))

    for iteration in range(20):
        groups = find_compound_groups(raw)
        if not groups:
            break
        made_changes = False
        for group in groups:
            marker_col = group["marker_col"]
            components = group["components"]

            prev_new_count = len(new_entries)
            layer_results  = pair_components_layered(
                components, dictionary, id_gen, dict_changes, new_entries
            )
            if not layer_results:
                continue

            stats["new_ids_created"]  += len(new_entries) - prev_new_count
            stats["dict_entries_added"] += len(new_entries) - prev_new_count
            outermost_id = layer_results[-1][0]

            orig_group = [",".join(raw[idx]) for idx in group["lines"]]
            for idx in group["lines"]:
                raw[idx].insert(marker_col + 1, outermost_id)
            new_group  = [",".join(raw[idx]) for idx in group["lines"]]

            revised_log.append((
                group["start"] + 1, orig_group, new_group, f"compound layer {iteration}"
            ))
            stats["groups_detected"] += 1
            made_changes = True

        if not made_changes:
            break

    return [",".join(f) for f in raw], revised_log, stats


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    if not os.path.isdir(TEXT_FOLDER):
        print(f"[ERROR] Input folder not found: {TEXT_FOLDER}")
        return

    dictionary  = Dictionary.from_file(DICT_FILE)
    id_gen      = IDGenerator(
        existing=dictionary.used_numbers(),
        start=LEMMA_START,
        prefix=LEMMA_PREFIX,
        digits=LEMMA_DIGITS,
    )
    dict_changes: dict = {}
    new_entries:  dict = {}

    txt_files = sorted(Path(TEXT_FOLDER).glob("*.txt"))
    if not txt_files:
        print(f"[WARN] No .txt files found in: {TEXT_FOLDER}")

    total_files         = 0
    total_groups        = 0
    total_new_ids       = 0
    total_dict_added    = 0
    total_np_expansions = 0
    all_revised:  list[str] = []
    output_files: list[str] = []

    for txt_path in txt_files:
        if not txt_path.is_file():
            continue
        total_files += 1

        new_text_lines, revised_log, stats = process_text_file(
            str(txt_path), dictionary, id_gen, dict_changes, new_entries
        )

        total_groups        += stats["groups_detected"]
        total_new_ids       += stats["new_ids_created"]
        total_dict_added    += stats["dict_entries_added"]
        total_np_expansions += stats["np_expansions"]

        out_path = str(txt_path) if OVERWRITE_SOURCE else os.path.join(OUTPUT_FOLDER, txt_path.name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_text_lines) + "\n")
        output_files.append(out_path)

        if SAVE_REVISED and revised_log:
            all_revised.append(f"\n{'='*60}\n  Document: {txt_path.name}\n{'='*60}")
            for start_lno, orig_ls, new_ls, label in revised_log:
                block = [f"  [Type: {label}]"]
                for k, (ol, nl) in enumerate(zip(orig_ls, new_ls)):
                    block.append(f"  Line {start_lno + k} (original): {ol}")
                    block.append(f"  Line {start_lno + k} (revised) : {nl}")
                all_revised.append("\n".join(block))

    if SAVE_REVISED and all_revised:
        rev_path = os.path.join(OUTPUT_FOLDER, "all_revised_lines.txt")
        with open(rev_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(all_revised) + "\n")
        output_files.append(rev_path)

    dict_out = DICT_FILE if OVERWRITE_SOURCE else os.path.join(
        OUTPUT_FOLDER, Path(DICT_FILE).name
    )
    dictionary.to_file(dict_out)
    output_files.append(dict_out)

    if SAVE_REVISED and (dict_changes or new_entries):
        lines = []
        if dict_changes:
            lines.append("# ====  REFINED ENTRIES  ====\n")
            for entry in dict_changes.values():
                lines.append(entry.to_text())
        if new_entries:
            lines.append("# ====  NEW ENTRIES  ====\n")
            for entry in new_entries.values():
                lines.append(entry.to_text())
        rev_dict = os.path.join(OUTPUT_FOLDER, f"{Path(DICT_FILE).stem}_revised{Path(DICT_FILE).suffix}")
        with open(rev_dict, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        output_files.append(rev_dict)

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
    print(f"  Output files saved          : {len(output_files)}")
    for p in output_files:
        print(f"    -> {p}")
    print("=" * 55)
    print()


if __name__ == "__main__":
    print("compound_lemma_processor  (v2.0.0)")
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
