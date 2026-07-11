"""Tests for coj.lemma_id — LemmaID and IDGenerator."""
import pytest
from coj.core.lemma_id import LemmaID, IDGenerator


class TestLemmaID:
    def test_parse_basic(self):
        lid = LemmaID.parse("L000006")
        assert lid.prefix == "L"
        assert lid.number == 6
        assert lid.suffix == ""

    def test_parse_with_suffix(self):
        lid = LemmaID.parse("L000006a")
        assert lid.prefix == "L"
        assert lid.number == 6
        assert lid.suffix == "a"

    def test_parse_multi_letter_prefix(self):
        lid = LemmaID.parse("L050877")
        assert lid.number == 50877

    def test_parse_other_prefixes(self):
        assert LemmaID.parse("N000001").prefix == "N"
        assert LemmaID.parse("T050877").prefix == "T"
        assert LemmaID.parse("F000052").prefix == "F"

    def test_str_round_trip(self):
        for s in ("L000006a", "N000001", "T050877", "L000006b"):
            assert str(LemmaID.parse(s)) == s

    def test_default_zero_padding(self):
        lid = LemmaID("L", 6, "a")
        assert str(lid) == "L000006a"

    def test_custom_digits(self):
        lid = LemmaID("L", 6, digits=4)
        assert str(lid) == "L0006"

    def test_is_valid(self):
        assert LemmaID.is_valid("L000006a")
        assert LemmaID.is_valid("N000001")
        assert not LemmaID.is_valid("LOG")
        assert not LemmaID.is_valid("123")
        assert not LemmaID.is_valid("")

    def test_immutability(self):
        lid = LemmaID.parse("L000006a")
        with pytest.raises(AttributeError):
            lid.prefix = "N"

    def test_equality_with_string(self):
        lid = LemmaID.parse("L000006a")
        assert lid == "L000006a"
        assert "L000006a" == lid

    def test_equality_with_lemma_id(self):
        assert LemmaID.parse("L000006a") == LemmaID.parse("L000006a")
        assert LemmaID.parse("L000006a") != LemmaID.parse("L000006b")

    def test_hashable(self):
        s = {LemmaID.parse("L000006a"), LemmaID.parse("L000006a")}
        assert len(s) == 1

    def test_ordering(self):
        ids = [LemmaID.parse(s) for s in ("L000010", "L000006a", "L000006b")]
        assert sorted(ids) == [
            LemmaID.parse("L000006a"),
            LemmaID.parse("L000006b"),
            LemmaID.parse("L000010"),
        ]

    def test_with_prefix(self):
        lid = LemmaID.parse("L050877")
        t = lid.with_prefix("T")
        assert str(t) == "T050877"
        assert str(lid) == "L050877"   # original unchanged

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            LemmaID.parse("not-an-id")
        with pytest.raises(ValueError):
            LemmaID.parse("123abc")


class TestIDGenerator:
    def test_skips_existing(self):
        gen = IDGenerator({1, 2, 3}, start=1, prefix="N")
        assert gen.next_id().number == 4

    def test_sequential(self):
        gen = IDGenerator(set(), start=1, prefix="L")
        nums = [gen.next_id().number for _ in range(5)]
        assert nums == [1, 2, 3, 4, 5]

    def test_prefix_applied(self):
        gen = IDGenerator(set(), start=1, prefix="N")
        lid = gen.next_id()
        assert lid.prefix == "N"

    def test_prefix_override(self):
        gen = IDGenerator(set(), start=1, prefix="L")
        lid = gen.next_id(prefix="T")
        assert lid.prefix == "T"

    def test_reserve(self):
        gen = IDGenerator(set(), start=1)
        gen.reserve(1)
        gen.reserve(2)
        assert gen.next_id().number == 3

    def test_peek_does_not_advance(self):
        gen = IDGenerator(set(), start=1)
        assert gen.peek_next_number() == 1
        assert gen.peek_next_number() == 1   # unchanged
        gen.next_id()
        assert gen.peek_next_number() == 2

    def test_from_lemma_id_set(self):
        existing = {LemmaID.parse("L000001"), LemmaID.parse("L000002")}
        gen = IDGenerator(existing, start=1)
        assert gen.next_id().number == 3

    def test_ids_are_unique(self):
        gen = IDGenerator({2, 4}, start=1)
        issued = [gen.next_id().number for _ in range(6)]
        assert len(set(issued)) == 6
        assert 2 not in issued
        assert 4 not in issued
