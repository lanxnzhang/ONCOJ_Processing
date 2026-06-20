"""
Import XML corpus files and dictionary back to plain-text format.

# ─────────────────── USER SETTINGS ───────────────────────────────────────────

Set XML_FOLDERS to the directories containing .xml corpus files.
Set DICT_FILE to the path of dictionary.xml.
Set OUTPUT_BASE to the root directory for plain-text output (sub-folders
text/, trees/, and dict/ will be created automatically).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# ──────────────────────────────────────────────────────────────────────────────
# USER SETTINGS
# ──────────────────────────────────────────────────────────────────────────────

# Source folders — each maps to a same-named sub-folder under OUTPUT_BASE
XML_FOLDERS = {
    "text":  "data/xml/text",
    "trees": "data/xml/trees",
}

DICT_FILE   = "data/xml/dict/dictionary.xml"
OUTPUT_BASE = "data/txt"

# ──────────────────────────────────────────────────────────────────────────────

from oncoj.xml.corpus_xml import corpus_from_xml_file
from oncoj.xml.dictionary_xml import dictionary_from_xml_file


def main() -> None:
    imported = 0

    # Import corpus files — preserve text/ and trees/ sub-folder structure
    for subfolder, src_dir in XML_FOLDERS.items():
        out_dir = os.path.join(OUTPUT_BASE, subfolder)
        if not os.path.isdir(src_dir):
            print(f"[skip] {src_dir} not found")
            continue
        os.makedirs(out_dir, exist_ok=True)
        for fname in sorted(os.listdir(src_dir)):
            if not fname.endswith(".xml"):
                continue
            src = os.path.join(src_dir, fname)
            dst = os.path.join(out_dir, os.path.splitext(fname)[0] + ".txt")
            doc = corpus_from_xml_file(src)
            doc.to_file(dst)
            print(f"  corpus  {src} → {dst}  ({len(doc)} utterances)")
            imported += 1

    print(f"Imported {imported} corpus file(s).")

    # Import dictionary
    if os.path.isfile(DICT_FILE):
        d = dictionary_from_xml_file(DICT_FILE)
        out_dir = os.path.join(OUTPUT_BASE, "dict")
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, "dictionary.txt")
        d.to_file(dst)
        print(f"  dict    {DICT_FILE} → {dst}  ({len(d)} entries)")
    else:
        print(f"[skip] {DICT_FILE} not found")


if __name__ == "__main__":
    main()
