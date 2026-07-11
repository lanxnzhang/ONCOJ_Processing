"""
coj.core — domain model for the Oxford-NINJAL Corpus of Old Japanese.

Re-exports the full public API so callers can use either
``from coj.core.corpus import ...`` or ``from coj.core import ...``.
"""

from coj.core.kana import phonemic_to_kana
from coj.core.lemma_id import IDGenerator, LemmaID
from coj.core.tags import (
    DICT_FIELDS,
    GEO_VALUES,
    INFLECTION_SUFFIXES,
    ITYPE_VALUES,
    MULTI_VALUE_FIELDS,
    PHON_TAGS,
    POS_VALUES,
    REQUIRED_FIELDS,
    TEXT_COLLECTIONS,
    VAX_SEMANTICS,
    is_phon_tag,
    strip_disambig,
)
from coj.core.dictionary import DictEntry, Dictionary
from coj.core.corpus import CorpusDocument, CorpusLine, CommentLine, Utterance

__all__ = [
    "phonemic_to_kana",
    "LemmaID", "IDGenerator",
    "PHON_TAGS", "MULTI_VALUE_FIELDS", "REQUIRED_FIELDS",
    "DICT_FIELDS", "POS_VALUES", "ITYPE_VALUES", "GEO_VALUES",
    "TEXT_COLLECTIONS", "VAX_SEMANTICS", "INFLECTION_SUFFIXES",
    "strip_disambig", "is_phon_tag",
    "DictEntry", "Dictionary",
    "CorpusLine", "CommentLine", "Utterance", "CorpusDocument",
]
