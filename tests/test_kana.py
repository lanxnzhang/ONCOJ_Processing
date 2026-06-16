"""Tests for oncoj.kana — phonemic_to_kana conversion."""
import pytest
from oncoj.kana import phonemic_to_kana


class TestPhonemicToKana:
    def test_basic_cv_syllables(self):
        assert phonemic_to_kana("ka") == "カ"
        assert phonemic_to_kana("mi") == "ミ"
        assert phonemic_to_kana("nu") == "ヌ"

    def test_bare_vowels(self):
        assert phonemic_to_kana("a") == "ア"
        assert phonemic_to_kana("i") == "イ"
        assert phonemic_to_kana("u") == "ウ"
        assert phonemic_to_kana("e") == "エ"
        assert phonemic_to_kana("o") == "オ"

    def test_three_char_syllables_matched_before_shorter(self):
        # "kwo" must match as コ, not キ+ウ+オ
        assert phonemic_to_kana("kwo") == "コ"
        assert phonemic_to_kana("mwo") == "モ"
        assert phonemic_to_kana("two") == "ト"

    def test_multichar_word(self):
        assert phonemic_to_kana("kamu") == "カム"
        assert phonemic_to_kana("nusi") == "ヌシ"
        assert phonemic_to_kana("takama") == "タカマ"

    def test_case_insensitive(self):
        assert phonemic_to_kana("KAMU") == phonemic_to_kana("kamu")
        assert phonemic_to_kana("Nu") == "ヌ"

    def test_unrecognised_char_flagged(self):
        result = phonemic_to_kana("k_a")
        assert "⟨_⟩" in result

    def test_empty_string(self):
        assert phonemic_to_kana("") == ""

    def test_known_corpus_forms(self):
        # Forms taken directly from EN_01.txt
        assert phonemic_to_kana("para") == "ハラ"
        assert phonemic_to_kana("motite") == "モチテ"   # ti → チ (not ティ)
        assert phonemic_to_kana("wope") == "ヲヘ"
