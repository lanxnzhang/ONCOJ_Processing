# Version: 3.0.0
# Changes from 2.0.0: XML-native; reads/writes data/xml/ directly.
"""
compound_lemma_processor.py
============================
Detects compound nouns in corpus XML files, inserts shared lemma IDs,
and creates/refines dictionary entries.

Package-based version — uses src/oncoj for all I/O.

Algorithm:
1. Walk the XML element tree looking for internal <N> elements (no lemma attr)
   whose direct element children are all <N> elements with lemma attrs.
2. For 3+ component nouns: pair in layers (binary tree from left).
3. Optional NP-expansion: detect <NP> elements whose ALL direct element
   children are <N> leaves with lemmas; wrap them in a new bare <N>.
"""

import os
import re
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import xml.etree.ElementTree as ET
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
#  USER SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

TEXT_FOLDER       = "data/xml/text"
DICT_FILE         = "data/xml/dict/dictionary.xml"
OUTPUT_FOLDER     = "data/xml/text"

DICT_SEARCH       = True    # look up compound form in dictionary
DICT_REFINE       = True    # add missing .COMPOUND lines to an existing entry
DICT_ENTRY_CREATE = True    # create a new entry when the compound is new

NP_EXPANSION      = True    # detect NP-grouped N;@N siblings and insert marker N

SAVE_REVISED      = True    # write all_revised_log.txt
OVERWRITE_SOURCE  = False   # overwrite source files; False → OUTPUT_FOLDER

LEMMA_PREFIX      = "L"
LEMMA_DIGITS      = 6
LEMMA_START       = 50001


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

from oncoj.core.corpus import CorpusDocument
from oncoj.core.dictionary import Dictionary, DictEntry
from oncoj.core.lemma_id import IDGenerator
from oncoj.core.kana import phonemic_to_kana


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS / HELPERS
# ══════════════════════════════════════════════════════════════════════════════

_LEMMA_RE = re.compile(r'^[A-Za-z]\d+[a-z]*$')


def _is_lemma(token: str) -> bool:
    return bool(_LEMMA_RE.match(token))


def _elem_children(elem: ET.Element) -> list[ET.Element]:
    """Return direct element children, skipping <comment> nodes."""
    return [c for c in elem if c.tag != "comment"]


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
    """Look up, refine, or create a dictionary entry. Returns the compound lemma ID."""
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
#  XML TREE — GROUP DETECTION AND NP EXPANSION
# ══════════════════════════════════════════════════════════════════════════════

def _is_annotated_n_leaf(elem: ET.Element) -> bool:
    """True if *elem* is a leaf <N> element (any index) with a lemma attr."""
    if elem.tag != "N":
        return False
    if not elem.get("lemma"):
        return False
    return len(_elem_children(elem)) == 0


def _is_bare_n(elem: ET.Element) -> bool:
    """True if *elem* is an internal <N> element with no lemma attr."""
    if elem.tag != "N":
        return False
    if elem.get("lemma"):
        return False
    return len(_elem_children(elem)) > 0


def find_compound_groups_xml(doc_elem: ET.Element) -> list[dict]:
    """
    Walk the XML element tree and return groups of compound nouns.

    A compound group is an internal <N> element (no lemma) whose direct
    element children are ALL <N> elements with lemma attrs.  Groups with
    only one component are ignored.

    Returns a list of dicts with keys:
      bare_n_elem: the bare <N> ET.Element (the compound marker)
      components:  list of {comp_id, text_form} for each child <N>
    """
    groups: list[dict] = []

    def _walk(elem: ET.Element) -> None:
        children = _elem_children(elem)
        if _is_bare_n(elem):
            n_children = [c for c in children if c.tag == "N"]
            if len(n_children) >= 2 and all(
                _is_annotated_n_leaf(c) for c in n_children
            ):
                components = [
                    {"comp_id": c.get("lemma"), "text_form": c.get("form") or ""}
                    for c in n_children
                ]
                groups.append({
                    "bare_n_elem": elem,
                    "components":  components,
                })
                return  # don't recurse into an already-detected group
        for child in children:
            _walk(child)

    for block in doc_elem:
        if block.tag == "block":
            for child in _elem_children(block):
                _walk(child)

    return groups


def np_expand_xml(doc_elem: ET.Element) -> int:
    """
    NP expansion on the XML tree.

    Finds <NP> elements whose ALL direct element children are <N> leaves
    with lemma attrs (and no wrapping bare <N> already present).
    Wraps those children in a new bare <N> element.

    Returns the number of expansions performed.
    """
    count = 0

    def _walk(elem: ET.Element) -> None:
        nonlocal count
        children = _elem_children(elem)
        if elem.tag == "NP":
            n_children = [c for c in children if c.tag == "N"]
            if (
                len(n_children) >= 2
                and n_children == children  # all children are <N>
                and all(_is_annotated_n_leaf(c) for c in n_children)
                # don't expand if a bare <N> already wraps them
                and not any(_is_bare_n(c) for c in children)
            ):
                wrapper = ET.Element("N")
                for child in list(n_children):
                    elem.remove(child)
                    wrapper.append(child)
                elem.append(wrapper)
                count += 1
                return  # the new bare N will be picked up by group detection
        for child in list(children):
            _walk(child)

    for block in doc_elem:
        if block.tag == "block":
            for child in _elem_children(block):
                _walk(child)

    return count


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS A SINGLE XML FILE
# ══════════════════════════════════════════════════════════════════════════════

def process_xml_file(path: str,
                     dictionary: Dictionary,
                     id_gen: IDGenerator,
                     dict_changes: dict,
                     new_entries: dict) -> tuple:
    """
    Process one corpus XML file for compound nouns.
    Returns (doc, revised_log, stats).
    """
    doc = CorpusDocument.from_file(path)
    doc_elem = doc._get_doc_elem()

    revised_log: list[dict] = []
    stats = {
        "groups_detected":   0,
        "new_ids_created":   0,
        "dict_entries_added": 0,
        "np_expansions":     0,
    }

    if NP_EXPANSION:
        n_exp = np_expand_xml(doc_elem)
        stats["np_expansions"] += n_exp

    for iteration in range(20):
        groups = find_compound_groups_xml(doc_elem)
        if not groups:
            break
        made_changes = False
        for group in groups:
            bare_n = group["bare_n_elem"]
            if bare_n.get("lemma"):
                continue  # already annotated in a previous iteration
            components = group["components"]
            if len(components) < 2:
                continue

            prev_new_count = len(new_entries)
            layer_results  = pair_components_layered(
                components, dictionary, id_gen, dict_changes, new_entries
            )
            if not layer_results:
                continue

            stats["new_ids_created"]    += len(new_entries) - prev_new_count
            stats["dict_entries_added"] += len(new_entries) - prev_new_count
            outermost_id = layer_results[-1][0]
            bare_n.set("lemma", outermost_id)
            revised_log.append({
                "iteration": iteration,
                "outermost_id": outermost_id,
                "components": [(c["comp_id"], c["text_form"]) for c in components],
            })
            stats["groups_detected"] += 1
            made_changes = True

        if not made_changes:
            break

    return doc, revised_log, stats


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

    xml_files = sorted(Path(TEXT_FOLDER).glob("*.xml"))
    if not xml_files:
        print(f"[WARN] No .xml files found in: {TEXT_FOLDER}")

    total_files         = 0
    total_groups        = 0
    total_new_ids       = 0
    total_dict_added    = 0
    total_np_expansions = 0
    all_revised:  list[str] = []
    output_files: list[str] = []

    for xml_path in xml_files:
        if not xml_path.is_file():
            continue
        total_files += 1

        doc, revised_log, stats = process_xml_file(
            str(xml_path), dictionary, id_gen, dict_changes, new_entries
        )

        total_groups        += stats["groups_detected"]
        total_new_ids       += stats["new_ids_created"]
        total_dict_added    += stats["dict_entries_added"]
        total_np_expansions += stats["np_expansions"]

        out_path = str(xml_path) if OVERWRITE_SOURCE else os.path.join(
            OUTPUT_FOLDER, xml_path.name
        )
        doc.to_file(out_path)
        output_files.append(out_path)

        if SAVE_REVISED and revised_log:
            all_revised.append(f"\n{'='*60}\n  Document: {xml_path.name}\n{'='*60}")
            for entry in revised_log:
                comps = ", ".join(f"{cid}:{form}" for cid, form in entry["components"])
                all_revised.append(
                    f"  iter={entry['iteration']}  id={entry['outermost_id']}  [{comps}]"
                )

    if SAVE_REVISED and all_revised:
        rev_path = os.path.join(OUTPUT_FOLDER, "all_revised_log.txt")
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
        rev_dict = os.path.join(
            OUTPUT_FOLDER, f"{Path(DICT_FILE).stem}_revised{Path(DICT_FILE).suffix}"
        )
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
    print("compound_lemma_processor  (v3.0.0  XML-native)")
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
