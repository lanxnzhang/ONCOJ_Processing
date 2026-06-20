"""
oncoj.xml — export-only XML serialisation for corpus and dictionary.

from oncoj.xml.corpus_xml    import corpus_to_xml, corpus_to_xml_file, ...
from oncoj.xml.dictionary_xml import dictionary_to_xml, entry_to_str, ...
"""

from oncoj.xml.corpus_xml import (
    corpus_to_xml,
    corpus_to_xml_file,
    utterance_to_xml,
    utterance_to_tree_str,
)
from oncoj.xml.dictionary_xml import (
    dictionary_to_xml,
    dictionary_to_xml_file,
    entry_to_xml,
    entry_to_str,
)

__all__ = [
    "corpus_to_xml", "corpus_to_xml_file",
    "utterance_to_xml", "utterance_to_tree_str",
    "dictionary_to_xml", "dictionary_to_xml_file",
    "entry_to_xml", "entry_to_str",
]
