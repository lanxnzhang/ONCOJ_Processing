"""Tests for coj.corpus — CorpusLine, CommentLine, Utterance, CorpusDocument."""
import pytest
from coj.core.corpus import (
    CorpusLine, CommentLine, Utterance, CorpusDocument,
    _is_corpus_line, _classify_line,
)
from coj.core.lemma_id import LemmaID


# ── sample lines ──────────────────────────────────────────────────────────────

_ANNOTATED     = "IP-MAT,IP-ARG,C-NP,N,N,L000006a,LOG,nu"
_UNANNOTATED   = "IP-MAT,IP-ARG,C-NP,N,N,LOG,kamu"
_DISAMBIG_TAG  = "IP-MAT,IP-ARG,C-NP,N,N;@2,L000006a,LOG,nusi"   # N;@2 suffix
_NLOG_LINE     = "IP-MAT,NP,N,L050001a,NLOG,ame"
_PHON_ON_LINE  = "IP-MAT,NP,N,L050002,PHON-ON,ten"
_BPHON_LINE    = "IP-MAT,NP,N,L050003,BPHON,ro"
_HEADER        = '=N(" kamu nusi ")'
_COMMENT       = "IP-MAT,0@神主,*"
_ID_LINE       = "ID,1_EN_01"

_SIMPLE_DOC = """\
=N(" kamu nusi ")
IP-MAT,0@神主,*
IP-MAT,NP,N,LOG,kamu
IP-MAT,NP,N;@2,LOG,nusi
ID,1_EN_01

=N(" nu ")
IP-MAT,NP,N,L000006a,LOG,nu
ID,2_EN_01
"""


# ══════════════════════════════════════════════════════════════════════════════
#  CorpusLine
# ══════════════════════════════════════════════════════════════════════════════

class TestCorpusLine:
    def test_parse_fields(self):
        cl = CorpusLine.parse(_ANNOTATED)
        assert cl.fields == ["IP-MAT", "IP-ARG", "C-NP", "N", "N", "L000006a", "LOG", "nu"]

    def test_word_form_annotated(self):
        cl = CorpusLine.parse(_ANNOTATED)
        assert cl.word_form == "nu"

    def test_word_form_unannotated(self):
        cl = CorpusLine.parse(_UNANNOTATED)
        assert cl.word_form == "kamu"

    def test_phon_tag_log(self):
        cl = CorpusLine.parse(_ANNOTATED)
        assert cl.phon_tag == "LOG"

    def test_phon_tag_nlog(self):
        cl = CorpusLine.parse(_NLOG_LINE)
        assert cl.phon_tag == "NLOG"

    def test_phon_tag_phon_on(self):
        cl = CorpusLine.parse(_PHON_ON_LINE)
        assert cl.phon_tag == "PHON-ON"

    def test_phon_tag_bphon(self):
        cl = CorpusLine.parse(_BPHON_LINE)
        assert cl.phon_tag == "BPHON"

    def test_lemma_id_present(self):
        cl = CorpusLine.parse(_ANNOTATED)
        assert cl.lemma_id == LemmaID.parse("L000006a")

    def test_lemma_id_absent(self):
        cl = CorpusLine.parse(_UNANNOTATED)
        assert cl.lemma_id is None

    def test_is_annotated(self):
        assert CorpusLine.parse(_ANNOTATED).is_annotated
        assert not CorpusLine.parse(_UNANNOTATED).is_annotated

    def test_is_annotatable(self):
        assert CorpusLine.parse(_UNANNOTATED).is_annotatable
        assert not CorpusLine.parse(_ANNOTATED).is_annotatable

    def test_disambig_suffix_on_tag_does_not_break_lemma(self):
        # N;@2 in the path: lemma_id and word_form must still resolve
        cl = CorpusLine.parse(_DISAMBIG_TAG)
        assert cl.word_form == "nusi"
        assert cl.lemma_id == "L000006a"

    def test_synt_path_annotated(self):
        cl = CorpusLine.parse(_ANNOTATED)
        path = cl.synt_path
        assert "L000006a" not in path
        assert "LOG" not in path
        assert "nu" not in path

    def test_synt_path_unannotated(self):
        cl = CorpusLine.parse(_UNANNOTATED)
        path = cl.synt_path
        assert "LOG" not in path
        assert "kamu" not in path

    def test_preceding_synt_tag(self):
        cl = CorpusLine.parse(_ANNOTATED)
        assert cl.preceding_synt_tag() == "N"

    def test_to_text_round_trip(self):
        for raw in (_ANNOTATED, _UNANNOTATED, _DISAMBIG_TAG, _NLOG_LINE):
            assert CorpusLine.parse(raw).to_text() == raw

    def test_insert_lemma(self):
        cl = CorpusLine.parse(_UNANNOTATED)
        cl.insert_lemma("L000099")
        assert cl.is_annotated
        assert str(cl.lemma_id) == "L000099"
        assert cl.word_form == "kamu"   # word form unchanged

    def test_insert_lemma_already_annotated_raises(self):
        cl = CorpusLine.parse(_ANNOTATED)
        with pytest.raises(ValueError):
            cl.insert_lemma("L000099")

    def test_insert_lemma_no_word_form_raises(self):
        cl = CorpusLine.parse("IP-MAT,0@神主,*")
        with pytest.raises(ValueError):
            cl.insert_lemma("L000099")

    def test_replace_lemma(self):
        cl = CorpusLine.parse(_ANNOTATED)
        cl.replace_lemma("L000099")
        assert str(cl.lemma_id) == "L000099"

    def test_replace_lemma_not_annotated_raises(self):
        cl = CorpusLine.parse(_UNANNOTATED)
        with pytest.raises(ValueError):
            cl.replace_lemma("L000099")

    def test_remove_lemma(self):
        cl = CorpusLine.parse(_ANNOTATED)
        old = cl.remove_lemma()
        assert str(old) == "L000006a"
        assert not cl.is_annotated
        assert cl.word_form == "nu"

    def test_remove_lemma_not_annotated_returns_none(self):
        cl = CorpusLine.parse(_UNANNOTATED)
        assert cl.remove_lemma() is None

    def test_all_lemma_ids(self):
        cl = CorpusLine.parse(_ANNOTATED)
        ids = cl.all_lemma_ids()
        assert any(str(lid) == "L000006a" for lid in ids)

    def test_equality(self):
        assert CorpusLine.parse(_ANNOTATED) == CorpusLine.parse(_ANNOTATED)
        assert CorpusLine.parse(_ANNOTATED) != CorpusLine.parse(_UNANNOTATED)


# ══════════════════════════════════════════════════════════════════════════════
#  CommentLine
# ══════════════════════════════════════════════════════════════════════════════

class TestCommentLine:
    def test_is_header(self):
        cl = CommentLine.parse(_HEADER)
        assert cl.is_header
        assert not CommentLine.parse(_COMMENT).is_header

    def test_is_id_line(self):
        cl = CommentLine.parse(_ID_LINE)
        assert cl.is_id_line
        assert cl.sentence_id == "1_EN_01"

    def test_is_inline_comment(self):
        cl = CommentLine.parse(_COMMENT)
        assert cl.is_inline_comment
        assert not CommentLine.parse(_HEADER).is_inline_comment

    def test_to_text_round_trip(self):
        for raw in (_HEADER, _COMMENT, _ID_LINE):
            assert CommentLine.parse(raw).to_text() == raw


# ══════════════════════════════════════════════════════════════════════════════
#  Line classifier
# ══════════════════════════════════════════════════════════════════════════════

class TestLineClassifier:
    def test_corpus_lines_classified_correctly(self):
        assert _is_corpus_line(_ANNOTATED)
        assert _is_corpus_line(_UNANNOTATED)
        assert _is_corpus_line(_DISAMBIG_TAG)

    def test_non_corpus_lines_not_misclassified(self):
        assert not _is_corpus_line(_HEADER)
        assert not _is_corpus_line(_ID_LINE)
        assert not _is_corpus_line("")

    def test_classify_returns_correct_types(self):
        assert isinstance(_classify_line(_ANNOTATED), CorpusLine)
        assert isinstance(_classify_line(_HEADER), CommentLine)
        assert isinstance(_classify_line(_ID_LINE), CommentLine)


# ══════════════════════════════════════════════════════════════════════════════
#  Utterance
# ══════════════════════════════════════════════════════════════════════════════

class TestUtterance:
    @pytest.fixture
    def utt(self):
        return Utterance.from_lines([
            _HEADER,
            _COMMENT,
            _UNANNOTATED,
            _ANNOTATED,
            _ID_LINE,
        ])

    def test_sentence_id(self, utt):
        assert utt.sentence_id == "1_EN_01"

    def test_header(self, utt):
        assert utt.header is not None
        assert utt.header.is_header

    def test_corpus_lines(self, utt):
        cls = utt.corpus_lines()
        assert len(cls) == 2

    def test_comment_lines(self, utt):
        cmt = utt.comment_lines()
        assert any(c.is_header for c in cmt)
        assert any(c.is_id_line for c in cmt)

    def test_unannotated_lines(self, utt):
        ua = utt.unannotated_lines()
        assert len(ua) == 1
        assert ua[0].word_form == "kamu"

    def test_annotated_lines(self, utt):
        ann = utt.annotated_lines()
        assert len(ann) == 1
        assert str(ann[0].lemma_id) == "L000006a"

    def test_find_by_form(self, utt):
        hits = utt.find_by_form("nu")
        assert len(hits) == 1

    def test_find_by_lemma(self, utt):
        hits = utt.find_by_lemma("L000006a")
        assert len(hits) == 1

    def test_all_lemma_ids(self, utt):
        ids = utt.all_lemma_ids()
        assert any(str(lid) == "L000006a" for lid in ids)

    def test_to_text_round_trip(self, utt):
        text = utt.to_text()
        utt2 = Utterance.from_lines(text.splitlines())
        assert utt2.sentence_id == utt.sentence_id
        assert len(utt2.corpus_lines()) == len(utt.corpus_lines())


# ══════════════════════════════════════════════════════════════════════════════
#  CorpusDocument
# ══════════════════════════════════════════════════════════════════════════════

class TestCorpusDocument:
    @pytest.fixture
    def doc(self):
        return CorpusDocument.from_text(_SIMPLE_DOC)

    def test_utterance_count(self, doc):
        assert len(doc) == 2

    def test_getitem(self, doc):
        assert isinstance(doc[0], Utterance)

    def test_find_utterance(self, doc):
        utt = doc.find_utterance("1_EN_01")
        assert utt is not None
        assert utt.sentence_id == "EN.1.1"
        assert doc.find_utterance("EN.1.1") is not None

    def test_find_utterance_missing(self, doc):
        assert doc.find_utterance("MISSING") is None

    def test_all_corpus_lines(self, doc):
        lines = doc.all_corpus_lines()
        assert len(lines) >= 3

    def test_find_by_form(self, doc):
        hits = doc.find_by_form("kamu")
        assert len(hits) == 1
        utt, cl = hits[0]
        assert cl.word_form == "kamu"

    def test_find_by_lemma(self, doc):
        hits = doc.find_by_lemma("L000006a")
        assert len(hits) == 1

    def test_all_lemma_ids(self, doc):
        ids = doc.all_lemma_ids()
        assert LemmaID.parse("L000006a") in ids

    def test_unannotated_forms(self, doc):
        ua = doc.unannotated_forms()
        assert "kamu" in ua
        assert "nusi" in ua

    def test_to_text_round_trip(self, doc):
        text = doc.to_text()
        doc2 = CorpusDocument.from_text(text)
        assert len(doc2) == len(doc)
        for u1, u2 in zip(doc, doc2):
            assert u1.sentence_id == u2.sentence_id
            assert len(u1.corpus_lines()) == len(u2.corpus_lines())


class TestCorpusDocumentRealFile:
    """Integration tests against the actual EN_01.txt corpus file."""

    @pytest.fixture(scope="class")
    def doc(self, sample_corpus_file):
        return CorpusDocument.from_file(sample_corpus_file)

    def test_utterance_count(self, doc):
        assert len(doc) == 15

    def test_corpus_line_count(self, doc):
        assert len(doc.all_corpus_lines()) > 1000

    def test_known_lemma_present(self, doc):
        hits = doc.find_by_lemma("L000520")
        assert len(hits) >= 1

    def test_annotated_line_structure(self, doc):
        # Every annotated line must have: word_form, phon_tag, lemma_id
        for cl in doc.all_corpus_lines():
            if cl.is_annotated:
                assert cl.word_form is not None
                assert cl.phon_tag is not None
                assert cl.lemma_id is not None

    def test_round_trip_utterance_count(self, doc):
        doc2 = CorpusDocument.from_text(doc.to_text())
        assert len(doc2) == len(doc)

    def test_round_trip_corpus_line_count(self, doc):
        doc2 = CorpusDocument.from_text(doc.to_text())
        assert len(doc2.all_corpus_lines()) == len(doc.all_corpus_lines())
