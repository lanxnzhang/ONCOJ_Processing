"""Tests for oncoj.dictionary — DictEntry and Dictionary."""
import pytest
from oncoj.core.dictionary import DictEntry, Dictionary, ENTRY_SEP
from oncoj.core.lemma_id import LemmaID
from oncoj.core.tags import REQUIRED_FIELDS


# ── minimal entry text used across tests ──────────────────────────────────────

_ENTRY_NEG = """\
---------------------------------------------------
=== L000006a
.GLOSS\tNEG
.MEANING\t[negative]
.FORM\tnu
.KANA\tヌ
.FORM\tzu
.KANA\tズ
.POS\tauxiliary
.ITYPE\tquadrigrade
.NOTE\tconclusive: -zu

"""

_ENTRY_MINIMAL = """\
---------------------------------------------------
=== L000001
.FORM\tugonapar

"""

_TWO_ENTRY_TEXT = _ENTRY_NEG + _ENTRY_MINIMAL


# ══════════════════════════════════════════════════════════════════════════════
#  DictEntry
# ══════════════════════════════════════════════════════════════════════════════

class TestDictEntry:
    def test_eid_parsed(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        e = d["L000006a"]
        assert isinstance(e.eid, LemmaID)
        assert str(e.eid) == "L000006a"

    def test_get_singular_field(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        e = d["L000006a"]
        assert e.get_first(".GLOSS") == "NEG"
        assert e.get_first(".POS") == "auxiliary"

    def test_get_multi_valued_field(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        e = d["L000006a"]
        forms = e.get_all(".FORM")
        assert forms == ["nu", "zu"]
        kanas = e.get_all(".KANA")
        assert kanas == ["ヌ", "ズ"]

    def test_get_returns_none_for_absent(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        e = d["L000006a"]
        assert e.get(".CORRESP") is None
        assert e.get_first(".CORRESP") is None
        assert e.get_all(".CORRESP") == []

    def test_has(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        e = d["L000006a"]
        assert e.has(".GLOSS")
        assert e.has(".NOTE")
        assert not e.has(".COMPOUND")

    def test_set_singular(self):
        e = DictEntry.blank("L000001", "kamu")
        e.set(".GLOSS", "N")
        assert e.get_first(".GLOSS") == "N"

    def test_set_multi_replaces_list(self):
        e = DictEntry.blank("L000001", "kamu")
        e.set(".FORM", ["kamu", "kamo"])
        assert e.get_all(".FORM") == ["kamu", "kamo"]

    def test_append_multi(self):
        e = DictEntry.blank("L000001", "kamu")
        e.append(".FORM", "kamo")
        forms = e.get_all(".FORM")
        assert "kamu" in forms
        assert "kamo" in forms

    def test_append_to_singular_raises(self):
        e = DictEntry.blank("L000001", "kamu")
        with pytest.raises(ValueError):
            e.append(".GLOSS", "extra")

    def test_remove(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        e = d["L000006a"]
        e.remove(".NOTE")
        assert not e.has(".NOTE")
        e.remove(".NOTE")   # no-op, should not raise

    def test_update_multi(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        e = d["L000006a"]
        e.update(".FORM", "ZU", index=1)
        assert e.get_all(".FORM")[1] == "ZU"

    def test_tags_order(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        tags = d["L000006a"].tags()
        # GLOSS must come before FORM which must come before POS
        assert tags.index(".GLOSS") < tags.index(".FORM")
        assert tags.index(".FORM") < tags.index(".POS")

    def test_to_text_contains_sep_and_header(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        text = d["L000006a"].to_text()
        assert ENTRY_SEP in text
        assert "=== L000006a" in text
        assert ".GLOSS\tNEG" in text
        assert text.endswith("\n")

    def test_blank_factory(self):
        e = DictEntry.blank("L000042", "kamu")
        assert e.get_first(".FORM") == "kamu" or "kamu" in e.get_all(".FORM")
        assert e.get_first(".KANA") == "カム" or "カム" in e.get_all(".KANA")
        for tag in REQUIRED_FIELDS:
            assert e.has(tag)

    def test_normalise_adds_missing_required_tags(self):
        e = DictEntry("L000001")
        e.set(".FORM", ["kamu"])
        changes = e.normalise()
        assert any(".GLOSS" in c for c in changes)
        assert any(".POS" in c for c in changes)
        for tag in REQUIRED_FIELDS:
            assert e.has(tag)

    def test_normalise_autofills_kana(self):
        e = DictEntry("L000001")
        e.set(".FORM", ["nu"])
        e.set(".KANA", [""])   # blank kana
        e.normalise()
        kanas = e.get_all(".KANA")
        assert "ヌ" in kanas

    def test_normalise_no_change_when_complete(self):
        d = Dictionary.from_text(_ENTRY_NEG)
        e = d["L000006a"]
        changes = e.normalise()
        assert changes == []

    def test_indexed_meaning_parsed(self):
        text = (
            "---------------------------------------------------\n"
            "=== L000010\n"
            ".GLOSS\tCTV\n"
            ".MEANING[1]\t[causative]\n"
            ".MEANING[2]\t[respect]\n"
            ".FORM\tsime\n"
            ".KANA\tシメ\n"
            ".POS\tauxiliary\n\n"
        )
        d = Dictionary.from_text(text)
        e = d["L000010"]
        meanings = e.get_all(".MEANING")
        assert meanings == ["[causative]", "[respect]"]


# ══════════════════════════════════════════════════════════════════════════════
#  Dictionary
# ══════════════════════════════════════════════════════════════════════════════

class TestDictionary:
    def test_len(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        assert len(d) == 2

    def test_contains(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        assert "L000006a" in d
        assert LemmaID.parse("L000006a") in d
        assert "L999999" not in d

    def test_getitem_and_get(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        assert d["L000006a"].get_first(".GLOSS") == "NEG"
        assert d.get("L000006a") is not None
        assert d.get("L999999") is None

    def test_getitem_missing_raises(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        with pytest.raises(KeyError):
            _ = d["L999999"]

    def test_add_and_delete(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        e = DictEntry.blank("L000099", "test")
        d.add(e)
        assert "L000099" in d
        removed = d.delete("L000099")
        assert str(removed.eid) == "L000099"
        assert "L000099" not in d

    def test_add_duplicate_raises(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        e = DictEntry.blank("L000006a", "nu")
        with pytest.raises(KeyError):
            d.add(e)

    def test_add_allow_update(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        e = DictEntry.blank("L000006a", "replacement")
        d.add(e, allow_update=True)
        assert d["L000006a"].get_all(".FORM") == ["replacement"]

    def test_delete_missing_raises(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        with pytest.raises(KeyError):
            d.delete("L999999")

    def test_update_field(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        d.update_field("L000006a", ".GLOSS", "CHANGED")
        assert d["L000006a"].get_first(".GLOSS") == "CHANGED"

    def test_find_by_form(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        results = d.find_by_form("nu")
        assert any(str(e.eid) == "L000006a" for e in results)

    def test_find_by_form_no_match(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        assert d.find_by_form("xyz") == []

    def test_find_by_pos_exact(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        results = d.find_by_pos("auxiliary")
        assert any(str(e.eid) == "L000006a" for e in results)

    def test_find_by_pos_substring(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        results = d.find_by_pos("aux", exact=False)
        assert any(str(e.eid) == "L000006a" for e in results)

    def test_find_by_gloss(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        assert any(str(e.eid) == "L000006a" for e in d.find_by_gloss("NEG"))

    def test_used_numbers(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        nums = d.used_numbers()
        assert 6 in nums
        assert 1 in nums

    def test_sorted_entries(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        entries = d.sorted_entries()
        assert entries[0].eid.number <= entries[1].eid.number

    def test_iteration(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        ids = [str(e.eid) for e in d]
        assert "L000006a" in ids

    def test_normalise_all(self):
        d = Dictionary.from_text(_ENTRY_MINIMAL)   # L000001 has only .FORM
        report = d.normalise_all()
        assert "L000001" in report
        assert d["L000001"].has(".GLOSS")

    def test_round_trip_text(self):
        d = Dictionary.from_text(_TWO_ENTRY_TEXT)
        d2 = Dictionary.from_text(d.to_text())
        assert len(d) == len(d2)
        assert d["L000006a"].get_all(".FORM") == d2["L000006a"].get_all(".FORM")


class TestDictionaryRealFile:
    """Integration tests against the actual dictionary file."""

    @pytest.fixture(scope="class")
    def dictionary(self, dict_file):
        return Dictionary.from_file(dict_file)

    def test_entry_count(self, dictionary):
        assert len(dictionary) > 7000

    def test_known_entry_fields(self, dictionary):
        e = dictionary["L000006a"]
        assert e.get_first(".GLOSS") == "NEG"
        assert "nu" in e.get_all(".FORM")
        assert "zu" in e.get_all(".FORM")
        assert "ヌ" in e.get_all(".KANA")

    def test_multi_meaning_entry(self, dictionary):
        # L000010 has .MEANING[1] and .MEANING[2]
        e = dictionary["L000010"]
        meanings = e.get_all(".MEANING")
        assert len(meanings) >= 2

    def test_compound_entry_multi(self, dictionary):
        # L000012 has two .COMPOUND lines
        e = dictionary["L000012"]
        compounds = e.get_all(".COMPOUND")
        assert len(compounds) >= 2

    def test_round_trip_preserves_count(self, dictionary):
        d2 = Dictionary.from_text(dictionary.to_text())
        assert len(d2) == len(dictionary)

    def test_find_by_form_real(self, dictionary):
        results = dictionary.find_by_form("ki")
        assert len(results) >= 1

    def test_normalise_all_no_crash(self, dictionary):
        # Round-trip through text to get an independent copy, then normalise
        d2 = Dictionary.from_text(dictionary.to_text())
        d2.normalise_all()
        from oncoj.core.tags import REQUIRED_FIELDS
        for entry in d2:
            for tag in REQUIRED_FIELDS:
                assert entry.has(tag), f"{entry.eid} missing {tag}"
