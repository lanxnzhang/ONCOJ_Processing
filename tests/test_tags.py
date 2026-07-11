"""Tests for coj.tags — tag sets, dicts, and strip_disambig."""
from coj.core.tags import (
    PHON_TAGS, MULTI_VALUE_FIELDS, REQUIRED_FIELDS,
    strip_disambig, is_phon_tag,
    DICT_FIELDS, POS_VALUES, ITYPE_VALUES, GEO_VALUES, TEXT_COLLECTIONS,
    VAX_SEMANTICS, INFLECTION_SUFFIXES,
)


class TestPhonTags:
    def test_core_tags_present(self):
        for tag in ("LOG", "PHON", "PHON-KUN", "NLOG"):
            assert tag in PHON_TAGS, f"{tag} missing from PHON_TAGS"

    def test_extended_tags_present(self):
        for tag in ("PHON-ON", "PLOG", "BPHON", "ILL", "ORDLOG", "NLPOG"):
            assert tag in PHON_TAGS, f"{tag} missing from PHON_TAGS"

    def test_syntactic_tags_not_in_phon_tags(self):
        for tag in ("NP", "VB-STM", "N", "IP-MAT", "PP-SBJ"):
            assert tag not in PHON_TAGS


class TestStripDisambig:
    def test_plain_tag_unchanged(self):
        assert strip_disambig("NP") == "NP"
        assert strip_disambig("VB-STM") == "VB-STM"

    def test_suffix_stripped(self):
        assert strip_disambig("N;@2") == "N"
        assert strip_disambig("C-NP;@5") == "C-NP"
        assert strip_disambig("LOG;@2") == "LOG"

    def test_is_phon_tag_with_suffix(self):
        assert is_phon_tag("LOG;@2")
        assert is_phon_tag("PHON;@3")
        assert not is_phon_tag("NP;@2")


class TestMultiValueFields:
    def test_required_multi_fields_present(self):
        for f in (".FORM", ".KANA", ".MEANING", ".COMPOUND", ".RELATED"):
            assert f in MULTI_VALUE_FIELDS

    def test_extended_multi_fields_present(self):
        for f in (".DERIVATION", ".TRANSREL", ".NOTE", ".VCLASS", ".ITYPE",
                  ".POS", ".GEO", ".PTR"):
            assert f in MULTI_VALUE_FIELDS


class TestRequiredFields:
    def test_five_required_fields(self):
        assert len(REQUIRED_FIELDS) == 5

    def test_canonical_order(self):
        assert list(REQUIRED_FIELDS) == [
            ".GLOSS", ".MEANING", ".FORM", ".KANA", ".POS"
        ]


class TestReferenceDicts:
    def test_dict_fields_covers_all_known(self):
        for f in (".GLOSS", ".MEANING", ".FORM", ".KANA", ".POS",
                  ".COMPOUND", ".RELATED", ".DERIVATION", ".ITYPE",
                  ".NOTE", ".GEO", ".CORRESP"):
            assert f in DICT_FIELDS, f"{f} not documented in DICT_FIELDS"

    def test_pos_values_covers_main(self):
        for pos in ("noun", "verb", "adjective", "auxiliary",
                    "case particle", "makura kotoba"):
            assert pos in POS_VALUES

    def test_itype_values_covers_main(self):
        for itype in ("quadrigrade", "lower_bigrade", "KU-adjective",
                      "R-irregular"):
            assert itype in ITYPE_VALUES

    def test_geo_values(self):
        assert "EOJ" in GEO_VALUES
        assert "NEOJ" in GEO_VALUES

    def test_text_collections(self):
        for code in ("MYS", "KK", "NSK", "BS", "FK"):
            assert code in TEXT_COLLECTIONS

    def test_vax_semantics_covers_main(self):
        for sem in ("NEG", "STV", "PRF", "SPST", "MPST", "CJR",
                    "PASS", "CTV", "RSP", "SJV"):
            assert sem in VAX_SEMANTICS

    def test_inflection_suffixes_covers_main(self):
        for suf in ("STM", "INF", "CLS", "ADN", "GER", "IMP"):
            assert suf in INFLECTION_SUFFIXES
