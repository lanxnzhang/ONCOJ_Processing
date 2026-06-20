"""
Export corpus files and dictionary to XML.

# ─────────────────── USER SETTINGS ───────────────────────────────────────────

Set TEXT_FOLDERS to the directories containing .txt corpus files.
Set DICT_FILE to the path of dictionary.txt.
Set OUTPUT_BASE to the root directory for XML output (sub-folders text/, trees/,
and dict/ will be created automatically).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# ──────────────────────────────────────────────────────────────────────────────
# USER SETTINGS
# ──────────────────────────────────────────────────────────────────────────────

# Source folders — each maps to a same-named sub-folder under OUTPUT_BASE
TEXT_FOLDERS = {
    "text":  "data/txt/text",
    "trees": "data/txt/trees",
}

DICT_FILE   = "data/txt/dict/dictionary.txt"
OUTPUT_BASE = "data/xml"

# ──────────────────────────────────────────────────────────────────────────────

from oncoj.core.corpus import CorpusDocument
from oncoj.core.dictionary import Dictionary
from oncoj.xml.corpus_xml import corpus_to_xml_file
from oncoj.xml.dictionary_xml import dictionary_to_xml_file


def main() -> None:
    exported = 0

    # Export corpus files — preserve text/ and trees/ sub-folder structure
    for subfolder, src_dir in TEXT_FOLDERS.items():
        out_dir = os.path.join(OUTPUT_BASE, subfolder)
        if not os.path.isdir(src_dir):
            print(f"[skip] {src_dir} not found")
            continue
        os.makedirs(out_dir, exist_ok=True)
        for fname in sorted(os.listdir(src_dir)):
            if not fname.endswith(".txt"):
                continue
            src = os.path.join(src_dir, fname)
            dst = os.path.join(out_dir, os.path.splitext(fname)[0] + ".xml")
            doc = CorpusDocument.from_file(src)
            corpus_to_xml_file(doc, dst)
            print(f"  corpus  {src} → {dst}  ({len(doc)} utterances)")
            exported += 1

    print(f"Exported {exported} corpus file(s).")

    # Export dictionary
    if os.path.isfile(DICT_FILE):
        d = Dictionary.from_file(DICT_FILE)
        out_dir = os.path.join(OUTPUT_BASE, "dict")
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, "dictionary.xml")
        dictionary_to_xml_file(d, dst)
        print(f"  dict    {DICT_FILE} → {dst}  ({len(d)} entries)")
    else:
        print(f"[skip] {DICT_FILE} not found")


if __name__ == "__main__":
    main()
