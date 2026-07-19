"""Tests for coj.export — XML and text-tree serialisation."""
# Hurdles fixed and covered below:
#   1. multi-sentence / multi-clause root nodes: lines starting with a
#      lowercase token were silently classified as comments and lost from
#      the tree.  Fixed in _is_corpus_line; tested in TestMultiRoot.
#   2. index="1" inference for internal nodes: disambiguation suffix @N on
#      sibling internal elements was not back-propagating index="1" to the
#      unsuffixed element.  Tested in TestIndexInference.
#   3. Embedded compound lemma IDs: a lemma-ID field occurring immediately
#      after a syntactic tag in the path (e.g. VB-ADC,L031257a,VB-STM,…)
#      was expanded into a wrapper XML element rather than a lemma= attribute
#      on the parent node.  Fixed in _build_children; tested in
#      TestEmbeddedLemma.
import xml.etree.ElementTree as ET

import pytest

from coj.core.corpus import CorpusDocument
from coj.core.dictionary import Dictionary
from coj.xml.corpus_xml import (
    corpus_from_xml,
    corpus_to_xml,
    utterance_from_xml,
    utterance_to_xml,
    utterance_to_tree_str,
)
from coj.xml.dictionary_xml import (
    dictionary_from_xml,
    dictionary_to_xml,
    entry_from_xml,
    entry_to_xml,
    entry_to_str,
)


# ── shared synthetic data ──────────────────────────────────────────────────────

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

_DICT_BLOCK = """\
---------------------------------------------------
=== L000006a
.GLOSS\tNEG
.MEANING\t[negative]
.FORM\tnu
.KANA\tヌ
.FORM\tzu
.KANA\tズ
.POS\tauxiliary
.NOTE\tnwo reflects merger of no and nwo
.CORRESP\t28989

---------------------------------------------------
=== L000012
.GLOSS\tNEG.PST
.MEANING\t[negative past]
.FORM\tzari
.KANA\tザリ
.POS\tauxiliary
.COMPOUND\tref_target=L000006a\tzu
.COMPOUND\tref_target=L030125a\tari

"""


# ══════════════════════════════════════════════════════════════════════════════
#  TestCorpusXmlUnit
# ══════════════════════════════════════════════════════════════════════════════

class TestCorpusXmlUnit:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.doc = CorpusDocument.from_text(_SIMPLE_DOC, filename="test.txt")
        self.xml_str = corpus_to_xml(self.doc)
        self.root = ET.fromstring(self.xml_str)

    def test_document_element(self):
        assert self.root.tag == "document"
        assert self.root.get("filename") == "test.txt"

    def test_block_count(self):
        blocks = self.root.findall("block")
        assert len(blocks) == 2

    def test_block_id(self):
        ids = {s.get("id") for s in self.root.findall("block")}
        assert "EN.1.1" in ids
        assert "EN.1.2" in ids

    def test_lemma_attribute_present(self):
        # Second block: IP-MAT > NP > N with lemma=L000006a
        sent2 = self.root.find(".//block[@id='EN.1.2']")
        assert sent2 is not None
        leaf = sent2.find(".//*[@lemma]")
        assert leaf is not None
        assert leaf.get("lemma") == "L000006a"

    def test_form_attribute_present(self):
        sent2 = self.root.find(".//block[@id='EN.1.2']")
        assert sent2 is not None
        leaf = sent2.find(".//*[@form='nu']")
        assert leaf is not None

    def test_disambiguation_index(self):
        # First block has N;@2 → index="2"
        sent1 = self.root.find(".//block[@id='EN.1.1']")
        assert sent1 is not None
        indexed = sent1.find(".//*[@index='2']")
        assert indexed is not None

    def test_index_1_inferred(self):
        # First block has N (plain) alongside N;@2 → implicit index="1" on the plain N
        sent1 = self.root.find(".//block[@id='EN.1.1']")
        assert sent1 is not None
        indexed_1 = sent1.find(".//*[@index='1']")
        assert indexed_1 is not None

    def test_comment_element_present(self):
        sent1 = self.root.find(".//block[@id='EN.1.1']")
        assert sent1 is not None
        comments = sent1.findall("./roundtrip-data/comment")
        assert len(comments) == 1
        assert "神主" in (comments[0].get("raw") or "")
        assert comments[0].get("position") == "0"

    def test_legacy_id_is_roundtrip_only(self):
        sent1 = self.root.find(".//block[@id='EN.1.1']")
        roundtrip = sent1.find("roundtrip-data")
        assert roundtrip is not None
        assert roundtrip.get("format") == "coj-txt"
        assert roundtrip.get("source-id") == "1_EN_01"

    def test_raw_text_has_semantic_sentence(self):
        sent1 = self.root.find(".//block[@id='EN.1.1']")
        sentence = sent1.find("./raw-text/sentence[@n='1']")
        assert sentence is not None
        assert sentence.findtext("kanji") == "神主"
        assert sentence.findtext("transcription") == "kamu nusi"

    def test_phon_attribute_set(self):
        # All leaf nodes should have a phon attribute
        for leaf in self.root.findall(".//*[@form]"):
            assert leaf.get("phon") is not None

    def test_phon_disambiguation_round_trip(self):
        source = '=N(" yo ")\nIP-MAT,PEN,LOG;@2,yo\nID,1_EN_01\n'
        doc = CorpusDocument.from_text(source)
        xml = corpus_to_xml(doc)
        leaf = ET.fromstring(xml).find(".//*[@form='yo']")
        assert leaf.get("phon") == "LOG"
        assert leaf.get("phon_index") == "2"
        assert corpus_from_xml(xml).to_text() == source

    def test_well_formed_xml(self):
        # ET.fromstring would have raised if not well-formed; double-check round-trip
        assert ET.tostring(self.root, encoding="unicode").startswith("<document")

    def test_multiple_markers_keep_source_positions(self):
        source = """\
=N(" ugonapar eru kamu nusi ")
IP-MAT,0@侍,*
IP-MAT,VB,LOG,ugonapar
IP-MAT,VB,LOG,eru
IP-MAT,1@神主,*
IP-MAT,NP,N,LOG,kamu
IP-MAT,NP,N;@2,LOG,nusi
ID,1_EN_01
"""
        xml = corpus_to_xml(CorpusDocument.from_text(source))
        root = ET.fromstring(xml)
        comments = root.findall("./block/roundtrip-data/comment")
        assert [comment.get("position") for comment in comments] == ["0", "2"]
        sentences = root.findall("./block/raw-text/sentence")
        assert [sentence.get("n") for sentence in sentences] == ["1", "2"]
        assert sentences[0].findtext("transcription") == "ugonapar eru"
        assert sentences[1].findtext("transcription") == "kamu nusi"
        assert corpus_from_xml(xml).to_text() == source


# ══════════════════════════════════════════════════════════════════════════════
#  TestCorpusXmlRealFile
# ══════════════════════════════════════════════════════════════════════════════

class TestCorpusXmlRealFile:
    @pytest.fixture(autouse=True)
    def setup(self, sample_corpus_file):
        self.doc = CorpusDocument.from_file(sample_corpus_file)
        self.xml_str = corpus_to_xml(self.doc)
        self.root = ET.fromstring(self.xml_str)

    def test_block_count(self):
        assert len(self.root.findall("block")) == 15

    def test_first_and_last_id(self):
        ids = {s.get("id") for s in self.root.findall("block")}
        assert "EN.1.1" in ids
        assert "EN.1.15" in ids

    def test_known_lemma_present(self):
        leaf = self.root.find(".//*[@lemma='L000530']")
        assert leaf is not None

    def test_disambiguation_index_exists(self):
        assert self.root.find(".//*[@index='2']") is not None

    def test_well_formed(self):
        # Re-parse from string — no exception = well formed
        root2 = ET.fromstring(self.xml_str)
        assert root2.tag == "document"


# ══════════════════════════════════════════════════════════════════════════════
#  TestUtteranceXml
# ══════════════════════════════════════════════════════════════════════════════

class TestUtteranceXml:
    def test_single_utterance_xml(self):
        doc = CorpusDocument.from_text(_SIMPLE_DOC)
        utt = doc[1]  # second utterance has a lemma
        xml_str = utterance_to_xml(utt)
        elem = ET.fromstring(xml_str)
        assert elem.tag == "block"
        leaf = elem.find(".//*[@lemma='L000006a']")
        assert leaf is not None


# ══════════════════════════════════════════════════════════════════════════════
#  TestCorpusTreeStr
# ══════════════════════════════════════════════════════════════════════════════

class TestCorpusTreeStr:
    def test_returns_nonempty(self):
        doc = CorpusDocument.from_text(_SIMPLE_DOC)
        s = utterance_to_tree_str(doc[0])
        assert isinstance(s, str) and s

    def test_contains_tag_name(self):
        doc = CorpusDocument.from_text(_SIMPLE_DOC)
        s = utterance_to_tree_str(doc[0])
        assert "NP" in s or "IP-MAT" in s

    def test_contains_form_value(self):
        doc = CorpusDocument.from_text(_SIMPLE_DOC)
        s = utterance_to_tree_str(doc[0])
        assert "kamu" in s

    def test_no_crash_real_file(self, sample_corpus_file):
        doc = CorpusDocument.from_file(sample_corpus_file)
        for utt in doc:
            s = utterance_to_tree_str(utt)
            assert isinstance(s, str) and s


# ══════════════════════════════════════════════════════════════════════════════
#  TestDictionaryXmlUnit
# ══════════════════════════════════════════════════════════════════════════════

class TestDictionaryXmlUnit:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.dictionary = Dictionary.from_text(_DICT_BLOCK)
        self.xml_str = dictionary_to_xml(self.dictionary)
        self.root = ET.fromstring(self.xml_str)

    def test_root_element(self):
        assert self.root.tag == "dictionary"
        assert self.root.get("version") == "1.0"

    def test_entry_count(self):
        assert len(self.root.findall("entry")) == 2

    def test_entry_id(self):
        ids = {e.get("id") for e in self.root.findall("entry")}
        assert "L000006a" in ids

    def test_gloss(self):
        e = self.root.find(".//entry[@id='L000006a']")
        assert e is not None
        gloss = e.find("gloss")
        assert gloss is not None
        assert gloss.text == "NEG"

    def test_form_kana_pair(self):
        e = self.root.find(".//entry[@id='L000006a']")
        assert e is not None
        forms = e.findall("./forms/form")
        phonemics = [f.get("phonemic") for f in forms]
        kanas = [f.get("kana") for f in forms]
        assert "nu" in phonemics
        assert "ヌ" in kanas
        # Verify pairing: nu↔ヌ
        nu_idx = phonemics.index("nu")
        assert kanas[nu_idx] == "ヌ"

    def test_note_present(self):
        e = self.root.find(".//entry[@id='L000006a']")
        assert e is not None
        note = e.find("./notes/note")
        assert note is not None
        assert "nwo" in (note.text or "")

    def test_corresp_present(self):
        e = self.root.find(".//entry[@id='L000006a']")
        assert e is not None
        corresp = e.find("corresp")
        assert corresp is not None
        assert corresp.text == "28989"

    def test_compound_refs(self):
        e = self.root.find(".//entry[@id='L000012']")
        assert e is not None
        refs = e.findall("./compound/ref")
        targets = {r.get("target") for r in refs}
        assert "L000006a" in targets
        assert "L030125a" in targets

    def test_compound_ref_form(self):
        e = self.root.find(".//entry[@id='L000012']")
        assert e is not None
        ref = e.find("./compound/ref[@target='L000006a']")
        assert ref is not None
        assert ref.get("form") == "zu"

    def test_absent_singular_omitted(self):
        # L000006a has no .AFFIX field → no <affix> element
        e = self.root.find(".//entry[@id='L000006a']")
        assert e is not None
        assert e.find("affix") is None

    def test_well_formed(self):
        root2 = ET.fromstring(self.xml_str)
        assert root2.tag == "dictionary"


# ══════════════════════════════════════════════════════════════════════════════
#  TestDictionaryXmlRealFile
# ══════════════════════════════════════════════════════════════════════════════

class TestDictionaryXmlRealFile:
    @pytest.fixture(autouse=True)
    def setup(self, dict_file):
        self.dictionary = Dictionary.from_file(dict_file)
        self.xml_str = dictionary_to_xml(self.dictionary)
        self.root = ET.fromstring(self.xml_str)

    def test_entry_count(self):
        assert len(self.root.findall("entry")) > 7000

    def test_known_entry_gloss(self):
        e = self.root.find(".//entry[@id='L000006a']")
        assert e is not None
        gloss = e.find("gloss")
        assert gloss is not None and gloss.text == "NEG"

    def test_compound_ref_parsed(self):
        # Find any entry that has compound refs
        compound = self.root.find(".//compound/ref[@target]")
        assert compound is not None

    def test_well_formed(self):
        root2 = ET.fromstring(self.xml_str)
        assert root2.tag == "dictionary"


# ══════════════════════════════════════════════════════════════════════════════
#  TestEntryXml
# ══════════════════════════════════════════════════════════════════════════════

class TestEntryXml:
    def test_entry_to_xml(self):
        d = Dictionary.from_text(_DICT_BLOCK)
        e = d["L000006a"]
        xml_str = entry_to_xml(e)
        elem = ET.fromstring(xml_str)
        assert elem.tag == "entry"
        assert elem.get("id") == "L000006a"


# ══════════════════════════════════════════════════════════════════════════════
#  TestEntryStr
# ══════════════════════════════════════════════════════════════════════════════

class TestEntryStr:
    def test_contains_entry_id(self):
        d = Dictionary.from_text(_DICT_BLOCK)
        s = entry_to_str(d["L000006a"])
        assert "L000006a" in s

    def test_contains_form(self):
        d = Dictionary.from_text(_DICT_BLOCK)
        s = entry_to_str(d["L000006a"])
        assert "nu" in s

    def test_compound_ref_in_str(self):
        d = Dictionary.from_text(_DICT_BLOCK)
        s = entry_to_str(d["L000012"])
        assert "L000006a" in s or "zu" in s

    def test_real_entry(self, dict_file):
        d = Dictionary.from_file(dict_file)
        e = d["L000006a"]
        s = entry_to_str(e)
        assert "L000006a" in s
        assert len(s) > 0


# ══════════════════════════════════════════════════════════════════════════════
#  Hurdle 1 — multi-sentence / multi-clause root nodes
#
#  Before the fix, lines starting with a lowercase token (e.g. "multi-sentence,")
#  were classified as CommentLines and silently omitted from the XML tree.
#  After the fix (_MULTIROOT_RE in _is_corpus_line), they are correctly parsed
#  as CorpusLines and become elements in the output.
# ══════════════════════════════════════════════════════════════════════════════

_MULTI_ROOT_DOC = """\
=N(" kamu nusi ")
multi-sentence,IP-MAT,NP,N,LOG,kamu
multi-sentence,IP-MAT,NP,N;@2,LOG,nusi
ID,1_MULTI
"""

_MULTI_CLAUSE_DOC = """\
=N(" tori ")
multi-clause,IP-MAT,VB,VB-STM,LOG,tori
ID,1_CLAUSE
"""


class TestMultiRoot:
    def test_multi_sentence_produces_element(self):
        doc = CorpusDocument.from_text(_MULTI_ROOT_DOC)
        xml_str = corpus_to_xml(doc)
        root = ET.fromstring(xml_str)
        blk = root.find("block")
        assert blk is not None
        # The root syntactic node must be "multi-sentence" (sanitised to same name)
        multi = blk.find("multi-sentence")
        assert multi is not None, "multi-sentence element missing — was the line silently dropped?"

    def test_multi_sentence_has_children(self):
        doc = CorpusDocument.from_text(_MULTI_ROOT_DOC)
        xml_str = corpus_to_xml(doc)
        root = ET.fromstring(xml_str)
        multi = root.find(".//multi-sentence")
        assert multi is not None
        # Should contain at least one descendant with a form attribute
        leaf = multi.find(".//*[@form]")
        assert leaf is not None, "multi-sentence subtree is empty — child lines were not grouped"

    def test_multi_sentence_leaf_forms(self):
        doc = CorpusDocument.from_text(_MULTI_ROOT_DOC)
        xml_str = corpus_to_xml(doc)
        root = ET.fromstring(xml_str)
        forms = {e.get("form") for e in root.findall(".//*[@form]")}
        assert "kamu" in forms
        assert "nusi" in forms

    def test_multi_clause_produces_element(self):
        doc = CorpusDocument.from_text(_MULTI_CLAUSE_DOC)
        xml_str = corpus_to_xml(doc)
        root = ET.fromstring(xml_str)
        multi = root.find(".//multi-clause")
        assert multi is not None, "multi-clause element missing"

    def test_multi_root_not_classified_as_comment(self):
        # The block should have corpus content — if lines were silently treated as
        # comments the block would contain only a <comment> element and no tree nodes
        doc = CorpusDocument.from_text(_MULTI_ROOT_DOC)
        utt = doc[0]
        from coj.core.corpus import CorpusLine
        assert any(isinstance(ln, CorpusLine) for ln in utt.lines), (
            "multi-sentence lines were classified as CommentLines"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Hurdle 2 — index="1" inference on *internal* nodes
#
#  The existing test (test_index_1_inferred) verified the leaf case.  Internal
#  nodes (non-leaf elements) also need index="1" when a sibling at the same
#  depth carries a ;@2+ suffix.
# ══════════════════════════════════════════════════════════════════════════════

_INDEX_INTERNAL_DOC = """\
=N(" kamu nusi ")
IP-MAT,NP,N,LOG,kamu
IP-MAT,NP;@2,N,LOG,nusi
ID,1_IDX
"""


class TestIndexInference:
    @staticmethod
    def _xml_root(text: str) -> ET.Element:
        doc = CorpusDocument.from_text(text)
        return ET.fromstring(corpus_to_xml(doc))

    def test_index_2_present(self):
        root = self._xml_root(_INDEX_INTERNAL_DOC)
        assert root.find(".//*[@index='2']") is not None

    def test_index_1_inferred_on_internal_node(self):
        # NP (plain) alongside NP;@2 → internal <NP index="1"> must appear
        root = self._xml_root(_INDEX_INTERNAL_DOC)
        nps = root.findall(".//NP")
        indices = {e.get("index") for e in nps}
        assert "1" in indices, (
            f"index='1' not inferred on plain NP; found indices: {indices}"
        )
        assert "2" in indices

    def test_leaf_index_1_inferred(self):
        # Leaf case (existing coverage, kept here for completeness as a regression guard)
        root = self._xml_root(_SIMPLE_DOC)
        blk1 = root.find(".//block[@id='EN.1.1']")
        assert blk1 is not None
        assert blk1.find(".//*[@index='1']") is not None

    def test_no_spurious_index_on_unique_tag(self):
        # When a tag appears only once (no ;@N sibling), index must NOT be added
        root = self._xml_root(_INDEX_INTERNAL_DOC)
        ip_mat = root.find(".//IP-MAT")
        assert ip_mat is not None
        assert ip_mat.get("index") is None, "unique IP-MAT incorrectly received an index attribute"


# ══════════════════════════════════════════════════════════════════════════════
#  Hurdle 3 — embedded compound lemma IDs as lemma= attributes
#
#  A path like "IP-MAT,VB-ADC,L031257a,VB-STM,LOG,tori" embeds a compound
#  lemma ID between two syntactic tags.  Before the fix, L031257a was treated
#  as a syntactic node name and became a wrapper XML element <L031257a>.
#  After the fix (_node_key / child_depth logic in _build_children), it becomes
#  a lemma= attribute on the parent syntactic node.
# ══════════════════════════════════════════════════════════════════════════════

_EMBEDDED_LEMMA_DOC = """\
=N(" tori ")
IP-MAT,VB-ADC,L031257a,VB-STM,LOG,tori
ID,1_EMB
"""

_EMBEDDED_LEMMA_DOC2 = """\
=N(" tori nori ")
IP-MAT,VB-ADC,L031257a,VB-STM,LOG,tori
IP-MAT,VB-ADC,L031257a,VB-IMP,LOG,nori
ID,1_EMB2
"""


class TestEmbeddedLemma:
    @staticmethod
    def _xml_root(text: str) -> ET.Element:
        doc = CorpusDocument.from_text(text)
        return ET.fromstring(corpus_to_xml(doc))

    def test_no_lemma_wrapper_element(self):
        root = self._xml_root(_EMBEDDED_LEMMA_DOC)
        # No element should be named like a lemma ID
        import re
        lemma_pat = re.compile(r'^[A-Za-z]\d+[a-z]*$')
        for elem in root.iter():
            assert not lemma_pat.match(elem.tag), (
                f"Element <{elem.tag}> looks like a lemma ID — should be an attribute, not a node"
            )

    def test_embedded_lemma_becomes_attribute(self):
        root = self._xml_root(_EMBEDDED_LEMMA_DOC)
        vb_adc = root.find(".//VB-ADC")
        assert vb_adc is not None, "<VB-ADC> element not found"
        assert vb_adc.get("lemma") == "L031257a", (
            f"Expected lemma='L031257a' on <VB-ADC>, got {vb_adc.get('lemma')!r}"
        )

    def test_embedded_lemma_child_structure(self):
        # VB-ADC should contain VB-STM as a child, not L031257a as an intermediate
        root = self._xml_root(_EMBEDDED_LEMMA_DOC)
        vb_adc = root.find(".//VB-ADC")
        assert vb_adc is not None
        child_tags = [c.tag for c in vb_adc]
        assert "VB-STM" in child_tags, (
            f"Expected VB-STM child of VB-ADC, got: {child_tags}"
        )

    def test_embedded_lemma_leaf_form(self):
        root = self._xml_root(_EMBEDDED_LEMMA_DOC)
        leaf = root.find(".//*[@form='tori']")
        assert leaf is not None
        assert leaf.tag == "VB-STM"

    def test_multiple_children_under_embedded_lemma_parent(self):
        # When VB-ADC,L031257a groups multiple children (VB-STM, VB-IMP),
        # they should all appear under one <VB-ADC lemma="L031257a"> element
        root = self._xml_root(_EMBEDDED_LEMMA_DOC2)
        vb_adcs = root.findall(".//VB-ADC")
        assert len(vb_adcs) == 1, (
            f"Expected 1 <VB-ADC> grouping both children, got {len(vb_adcs)}"
        )
        child_tags = [c.tag for c in vb_adcs[0]]
        assert "VB-STM" in child_tags
        assert "VB-IMP" in child_tags


# ══════════════════════════════════════════════════════════════════════════════
#  Round-trip tests — corpus XML ↔ CorpusDocument
# ══════════════════════════════════════════════════════════════════════════════

def _corpus_lines(doc: CorpusDocument) -> list[str]:
    return [ln.to_text() for utt in doc for ln in utt.corpus_lines()]


class TestCorpusRoundTrip:
    def test_simple_doc_corpus_lines_preserved(self):
        orig = CorpusDocument.from_text(_SIMPLE_DOC)
        rt = corpus_from_xml(corpus_to_xml(orig))
        assert _corpus_lines(orig) == _corpus_lines(rt)

    def test_utterance_count_preserved(self):
        orig = CorpusDocument.from_text(_SIMPLE_DOC)
        rt = corpus_from_xml(corpus_to_xml(orig))
        assert len(rt) == len(orig)

    def test_sentence_ids_preserved(self):
        orig = CorpusDocument.from_text(_SIMPLE_DOC)
        rt = corpus_from_xml(corpus_to_xml(orig))
        orig_ids = [u.sentence_id for u in orig]
        rt_ids = [u.sentence_id for u in rt]
        assert orig_ids == rt_ids

    def test_lemma_id_preserved(self):
        orig = CorpusDocument.from_text(_SIMPLE_DOC)
        rt = corpus_from_xml(corpus_to_xml(orig))
        orig_lemmas = [str(ln.lemma_id) for u in orig for ln in u.corpus_lines() if ln.lemma_id]
        rt_lemmas = [str(ln.lemma_id) for u in rt for ln in u.corpus_lines() if ln.lemma_id]
        assert orig_lemmas == rt_lemmas

    def test_disambiguation_suffix_preserved(self):
        orig = CorpusDocument.from_text(_SIMPLE_DOC)
        rt = corpus_from_xml(corpus_to_xml(orig))
        orig_tags = [ln.synt_path[-1] for u in orig for ln in u.corpus_lines()]
        rt_tags = [ln.synt_path[-1] for u in rt for ln in u.corpus_lines()]
        assert orig_tags == rt_tags

    def test_multi_root_round_trip(self):
        orig = CorpusDocument.from_text(_MULTI_ROOT_DOC)
        rt = corpus_from_xml(corpus_to_xml(orig))
        assert _corpus_lines(orig) == _corpus_lines(rt)

    def test_embedded_lemma_round_trip(self):
        orig = CorpusDocument.from_text(_EMBEDDED_LEMMA_DOC2)
        rt = corpus_from_xml(corpus_to_xml(orig))
        assert _corpus_lines(orig) == _corpus_lines(rt)

    def test_utterance_round_trip(self):
        orig = CorpusDocument.from_text(_SIMPLE_DOC)
        utt = orig[0]
        rt_utt = utterance_from_xml(utterance_to_xml(utt))
        orig_lines = [ln.to_text() for ln in utt.corpus_lines()]
        rt_lines = [ln.to_text() for ln in rt_utt.corpus_lines()]
        assert orig_lines == rt_lines

    def test_real_file_round_trip(self, sample_corpus_file):
        orig = CorpusDocument.from_file(sample_corpus_file)
        rt = corpus_from_xml(corpus_to_xml(orig))
        assert _corpus_lines(orig) == _corpus_lines(rt)

    def test_real_trees_round_trip(self, text_dir):
        # Use MYS_01.txt from the trees folder, which has multi-root and embedded lemmas
        import os
        trees_dir = os.path.join(os.path.dirname(text_dir), "trees")
        mys_path = os.path.join(trees_dir, "MYS_01.txt")
        if not os.path.isfile(mys_path):
            pytest.skip("MYS_01.txt not found")
        orig = CorpusDocument.from_file(mys_path)
        rt = corpus_from_xml(corpus_to_xml(orig))
        assert _corpus_lines(orig) == _corpus_lines(rt)


# ══════════════════════════════════════════════════════════════════════════════
#  Round-trip tests — dictionary XML ↔ Dictionary
# ══════════════════════════════════════════════════════════════════════════════

class TestDictionaryRoundTrip:
    def test_entry_count_preserved(self):
        orig = Dictionary.from_text(_DICT_BLOCK)
        rt = dictionary_from_xml(dictionary_to_xml(orig))
        assert len(rt) == len(orig)

    def test_gloss_preserved(self):
        orig = Dictionary.from_text(_DICT_BLOCK)
        rt = dictionary_from_xml(dictionary_to_xml(orig))
        assert rt["L000006a"].get_first(".GLOSS") == orig["L000006a"].get_first(".GLOSS")

    def test_forms_preserved(self):
        orig = Dictionary.from_text(_DICT_BLOCK)
        rt = dictionary_from_xml(dictionary_to_xml(orig))
        assert rt["L000006a"].get_all(".FORM") == orig["L000006a"].get_all(".FORM")

    def test_kana_preserved(self):
        orig = Dictionary.from_text(_DICT_BLOCK)
        rt = dictionary_from_xml(dictionary_to_xml(orig))
        assert rt["L000006a"].get_all(".KANA") == orig["L000006a"].get_all(".KANA")

    def test_compound_refs_preserved(self):
        orig = Dictionary.from_text(_DICT_BLOCK)
        rt = dictionary_from_xml(dictionary_to_xml(orig))
        assert rt["L000012"].get_all(".COMPOUND") == orig["L000012"].get_all(".COMPOUND")

    def test_entry_round_trip(self):
        orig = Dictionary.from_text(_DICT_BLOCK)
        e_orig = orig["L000006a"]
        e_rt = entry_from_xml(entry_to_xml(e_orig))
        assert e_rt.get_all(".FORM") == e_orig.get_all(".FORM")
        assert e_rt.get_all(".KANA") == e_orig.get_all(".KANA")
        assert e_rt.get_first(".GLOSS") == e_orig.get_first(".GLOSS")

    def test_real_dictionary_round_trip(self, dict_file):
        orig = Dictionary.from_file(dict_file)
        rt = dictionary_from_xml(dictionary_to_xml(orig))
        assert len(rt) == len(orig)
        e_o = orig["L000006a"]
        e_r = rt["L000006a"]
        assert e_r.get_all(".FORM") == e_o.get_all(".FORM")
        assert e_r.get_all(".KANA") == e_o.get_all(".KANA")
        assert e_r.get_first(".GLOSS") == e_o.get_first(".GLOSS")
        # Compound refs with tab-separated form strings
        e_o12 = orig["L000012"]
        e_r12 = rt["L000012"]
        assert e_r12.get_all(".COMPOUND") == e_o12.get_all(".COMPOUND")

    def test_legacy_and_nonstandard_cross_refs_preserved(self):
        source = """---------------------------------------------------
=== L080501
.FORM\tparu-puyu
.KANA\t
.POS\tnoun
.COMPOUND\t(dvandva)\tref_target=L051724\tparu
.MKTARGET\tref_target=L090004\tmikasa

"""
        orig = Dictionary.from_text(source)
        rt = dictionary_from_xml(dictionary_to_xml(orig))
        assert rt["L080501"].get_all(".COMPOUND") == [
            "(dvandva)\tref_target=L051724\tparu"
        ]
        assert rt["L080501"].get_all(".MKTARGET") == [
            "ref_target=L090004\tmikasa"
        ]
        assert not rt["L080501"].has(".GLOSS")
