"""
ONCOJ annotation tag reference.

Derived from:
  - Corpus data mining (data/text/, data/trees/trees/) — 460 unique tags observed
  - Dictionary field analysis (data/dict/dictionary.txt)
  - ONCOJ project website: https://oncoj.ninjal.ac.jp/
  - GitHub release: https://github.com/ONCOJ/data

This module is purely informational: sets and dicts used for validation,
documentation, and tooling.  The actual processing logic lives in corpus.py
and dictionary.py.

Project background
------------------
The Oxford-NINJAL Corpus of Old Japanese (ONCOJ) covers surviving Old
Japanese poetic texts, primarily 7th–8th century (Asuka/Nara periods).
Main collections: Man'yōshū (MYS), Kojiki kayō (KK), Nihon shoki kayō (NSK),
Buddha's Footprints Stones (BS), Fudoki poems (FK), Kaifūsō (KH), and others.
Phonological framework: Frellesvig-Whitman notation distinguishing kō-rui /
otsu-rui syllable types.

Table format (current since 2022): each parse tree is stored as an ordered
set of comma-separated root-to-leaf paths, one per line.  Earlier releases
used Penn Historical-style bracketed PSD format (still in data/trees/).
"""

# ── Writing-mode / pronunciation tags ────────────────────────────────────────
# These appear in penultimate position before the word-form field.
# One of these tags is required for a line to be an annotatable corpus line.

PHON_TAGS: frozenset[str] = frozenset({
    "LOG",       # logographic (man'yōgana used for meaning)
    "PHON",      # phonographic (man'yōgana used for sound)
    "PHON-KUN",  # kun (native Japanese reading) phonographic
    "PHON-ON",   # on (Sino-Japanese reading) phonographic
    "NLOG",      # non-logographic (phonographic with no logographic equivalent)
    "PLOG",      # partial logographic
    "BPHON",     # back-phonographic (reversed phonographic reading)
    "ILL",       # illegible
    "ORDLOG",    # ordinal logographic
    "NLPOG",     # non-logographic, partially obscured
})

# Tags that appear with ;@n disambiguation suffixes in the corpus
# e.g. N;@2, C-NP;@5 — the suffix is stripped for tag lookup purposes
# Any syntactic tag can in principle carry this suffix.


# ── Phrase / clause labels ────────────────────────────────────────────────────

CLAUSE_LABELS: dict[str, str] = {
    "IP-MAT":         "matrix inflectional phrase",
    "IP-SUB":         "subordinate inflectional phrase",
    "IP-REL":         "relative clause",
    "IP-ADV":         "adverbial clause",
    "IP-ARG":         "argument clause",
    "IP-NMZ":         "nominalized inflectional phrase",
    "IP-NMZ-PRD":     "nominalized IP — predicate",
    "IP-NMZ-SBJ":     "nominalized IP — subject",
    "IP-NMZ-OB1":     "nominalized IP — object",
    "IP-NMZ-FRM":     "nominalized IP — formal/nominal",
    "IP-NMZ-ADV":     "nominalized IP — adverbial",
    "IP-NMZ-ARG":     "nominalized IP — argument",
    "IP-NMZ-IHRC":    "nominalized IP — internally headed relative clause",
    "IP-NMZ-XPR":     "nominalized IP — extra-propositional",
    "IP-EPT":         "exhaustive-listing topic phrase",
    "IP-EMB":         "embedded clause",
    "IP-ZYO":         "jodai (Old Japanese) specific clause type",
    "IP-EMP":         "empty clause",
    "IP-PRP":         "purpose clause",
    "IP-RDP":         "reduplication clause",
    "CP-FINAL":       "final complementizer phrase",
    "CP-N":           "noun complementizer phrase",
    "NP":             "noun phrase",
    "NP-SBJ":         "subject NP",
    "NP-OB1":         "first object NP",
    "NP-OB2":         "second object NP",
    "NP-PRD":         "predicative NP",
    "NP-ADV":         "adverbial NP",
    "NP-VOC":         "vocative NP",
    "NP-APP":         "appositive NP",
    "NP-ZYO":         "jodai NP",
    "NP-GEN":         "genitive NP",
    "NP-AGT":         "agent NP",
    "NP-GOL":         "goal NP",
    "NP-SRC":         "source NP",
    "NP-PTH":         "path NP",
    "NP-COM":         "comitative NP",
    "NP-TOP":         "topic NP",
    "NP-QFR":         "quantifier NP",
    "NP-XPR":         "extra-propositional NP",
    "NP-HST":         "historical NP",
    "PP":             "postpositional phrase",
    "PP-SBJ":         "subject PP",
    "PP-OB1":         "first object PP",
    "PP-OB2":         "second object PP",
    "PP-GEN":         "genitive PP",
    "PP-DAT":         "dative PP",
    "PP-ADV":         "adverbial PP",
    "PP-ARG":         "argument PP",
    "PP-TOP":         "topic PP",
    "PP-FOC":         "focus PP",
    "PP-RES":         "restrictive PP",
    "PP-AGT":         "agent PP",
    "PP-GOL":         "goal PP",
    "PP-SRC":         "source PP",
    "PP-PTH":         "path PP",
    "PP-VOC":         "vocative PP",
    "PP-ZYO":         "jodai PP",
    "CONJP":          "conjunction phrase",
    "C-N":            "compound noun",
    "C-NP":           "compound noun phrase",
    "C-ADV":          "compound adverb",
    "C-PP":           "compound postpositional phrase",
    "MK":             "makura-kotoba (pillow word / epithet) block",
    "PLN":            "place name",
    "FRAG":           "fragment",
    "INTJ":           "interjection phrase",
}


# ── Lexical / word-level POS tags ─────────────────────────────────────────────

LEXICAL_TAGS: dict[str, str] = {
    "N":              "noun",
    "N-DVB":          "deverbal noun",
    "N-COMP":         "compound noun member",
    "N-PRD":          "predicative noun",
    "DVN":            "deverbal nominal",
    "PRO-N":          "pronominal noun (demonstrative/interrogative/personal)",
    "PRO-ADV":        "pronominal adverb",
    "NUM":            "numeral",
    "NUMCL":          "numeral classifier",
    "CL":             "classifier",
    "ADV":            "adverb",
    "ADJ":            "adjective (base form)",
    "ADJ-STM":        "adjective stem",
    "ADJ-INF":        "adjective infinitive",
    "ADJ-ADN":        "adjective adnominal",
    "ADJ-CLS":        "adjective conclusive",
    "ADJ-IFC":        "adjective irrealis/conditional focus",
    "ADJ-CSS":        "adjective concessive",
    "ADJ-CND":        "adjective conditional",
    "ADJ-EXC":        "adjective exclamatory",
    "ADJ-NML":        "adjective nominalized",
    "ADJ-GER":        "adjective gerund",
    "ADJ-PRV":        "adjective provisional",
    "VB":             "verb (uninflected citation)",
    "VB-STM":         "verb stem",
    "VB-INF":         "verb infinitive",
    "VB-ADC":         "verb adnominal connective",
    "VB-ADN":         "verb adnominal",
    "VB-CLS":         "verb conclusive",
    "VB-EXC":         "verb exclamatory",
    "VB-GER":         "verb gerund",
    "VB-IFC":         "verb irrealis/conditional focus",
    "VB-IMP":         "verb imperative",
    "VB-CND":         "verb conditional",
    "VB-CSS":         "verb concessive",
    "VB-NML":         "verb nominalized",
    "VB-CTT":         "verb citational",
    "VB-PRV":         "verb provisional",
    "VB-ADI":         "verb adjectival infinitive",
    "VB-OPT":         "verb optative",
    "VB-NGC":         "verb negative conclusive",
    "VB-DVB":         "verb deverbal",
    "VB-ADV":         "verb adverbial",
    "VB-STV-STM":     "stative verb stem",
    "PFX":            "prefix",
    "PFX-HON":        "honorific prefix",
    "PFX-MPH":        "morphophonological prefix",
    "PFX-PHB":        "prohibitive prefix",
    "PFX-POT":        "potential prefix",
    "PFX-RCP":        "reciprocal prefix",
    "PFX-STV":        "stative prefix",
    "SFX":            "suffix",
    "ACP":            "adjectival copula",
    "ACP-INF":        "adjectival copula infinitive",
    "ACP-ADN":        "adjectival copula adnominal",
    "ACP-CLS":        "adjectival copula conclusive",
    "COP":            "copula",
    "COP-INF":        "copula infinitive",
    "COP-ADI":        "copula adjectival infinitive",
    "COP-ADN":        "copula adnominal",
    "COP-CLS":        "copula conclusive",
    "XTN":            "extension",
}


# ── Particle tags ─────────────────────────────────────────────────────────────

PARTICLE_TAGS: dict[str, str] = {
    "P-CASE-GEN":     "genitive case particle (no, ga, tu)",
    "P-CASE-DAT":     "dative case particle (ni)",
    "P-CASE-ACC":     "accusative case particle (wo)",
    "P-CASE-COM":     "comitative case particle (to, site)",
    "P-CASE-ABL":     "ablative case particle",
    "P-CASE-ALL":     "allative case particle",
    "P-CASE-NOM":     "nominative case particle",
    "P-TOP":          "topic particle (pa, pa)",
    "P-FOC":          "focus particle",
    "P-RES":          "restrictive particle (dani, nomi, sape)",
    "P-COMP":         "complementizer particle (to, to site)",
    "P-CONN":         "conjunctional particle",
    "P-FNL-MPH":      "final modal-phatic particle",
    "P-FNL-EVD":      "final evidential particle",
    "P-FNL-DES":      "final desiderative particle",
    "P-FNL-PHB":      "final prohibitive particle",
    "P-FNL-PRB":      "final probabilitive particle",
    "P-FNL-XCL":      "final exclamatory particle",
}


# ── Verbal auxiliary (VAX) tags ───────────────────────────────────────────────
# Pattern: VAX-<SEMANTIC>-<INFLECTION>
# Semantics: NEG=negative, STV=stative, PRF=perfective, SPST=simple past,
#            MPST=modal past, CJR=conjectural, PASS=passive, CTV=causative,
#            RSP=respect, SJV=subjunctive

VAX_SEMANTICS: dict[str, str] = {
    "NEG":   "negative",
    "STV":   "stative",
    "PRF":   "perfective",
    "SPST":  "simple past",
    "MPST":  "modal past",
    "CJR":   "conjectural",
    "PASS":  "passive/potential",
    "CTV":   "causative",
    "RSP":   "respect/honorific",
    "SJV":   "subjunctive",
}

# Inflectional suffixes shared across VAX, VB, ADJ, ACP, COP paradigms
INFLECTION_SUFFIXES: dict[str, str] = {
    "STM":  "stem",
    "INF":  "infinitive",
    "CLS":  "conclusive",
    "ADN":  "adnominal",
    "ADC":  "adnominal connective",
    "EXC":  "exclamatory",
    "IFC":  "irrealis/conditional focus",
    "IMP":  "imperative",
    "GER":  "gerund",
    "CND":  "conditional",
    "CSS":  "concessive",
    "NML":  "nominalized",
    "PRV":  "provisional",
    "CTT":  "citational",
    "OPT":  "optative",
    "NGC":  "negative conclusive",
    "ADI":  "adjectival infinitive",
    "ADV":  "adverbial",
}


# ── Disambiguation marker ─────────────────────────────────────────────────────
# Tags may carry a ;@N suffix identifying the Nth sister node with the same
# preceding path, e.g. N;@2, C-NP;@5.  This suffix is stripped before
# comparing a field to a tag name.

import re as _re
_DISAMBIG_RE = _re.compile(r'^([A-Z][A-Z0-9\-]*)(?:;@\d+)?$')


def strip_disambig(tag: str) -> str:
    """Return the base tag with any ;@N suffix removed."""
    m = _DISAMBIG_RE.match(tag)
    return m.group(1) if m else tag


def is_phon_tag(tag: str) -> bool:
    """True if *tag* (possibly with ;@N suffix) is a writing-mode tag."""
    return strip_disambig(tag) in PHON_TAGS


# ── Dictionary field reference ────────────────────────────────────────────────

DICT_FIELDS: dict[str, str] = {
    ".GLOSS":        "abbreviated gloss / functional label (e.g. NEG, PRF, CJR)",
    ".MEANING":      "full English meaning/gloss (multi-valued for polysemous entries)",
    ".FORM":         "romanised phonemic form(s) (multi-valued for irregular paradigms)",
    ".KANA":         "historical katakana spelling (parallel to .FORM, auto-generated)",
    ".POS":          "part of speech (free-text, e.g. 'noun', 'auxiliary', 'makura kotoba')",
    ".COMPOUND":      "compound back-reference: ref_target=<ID>  <form> (multi-valued)",
    ".RELATED":      "related entry: ref_target=<ID>  <form> (multi-valued)",
    ".MKTARGETNEW":  "makura-kotoba target word: ref_target=<ID>  <form> (multi-valued; replaces .RELATED for MK entries)",
    ".DERIVATION":   "derivational relation: ref_target=<ID>  <morpheme> (multi-valued)",
    ".TRANSREL":     "transitive/intransitive counterpart: ref_target=<ID>  <form>",
    ".ITYPE":        "inflection type (e.g. quadrigrade, lower_bigrade, KU-adjective)",
    ".AFFIX":        "stem allomorph class used by suffixes (aStem, iStem, bStem)",
    ".VCLASS":       "verb semantic class (e.g. motion, caused motion, psych, speech)",
    ".TRANSITIVITY": "transitivity (intransitive, transitive, intransitive subtype=…)",
    ".INTRVCLASS":   "intransitive verb sub-class (s, l, e, p, Em, b, w, …)",
    ".CORRESP":      "WALS/external correspondence number",
    ".NOTE":         "free-text note (multi-valued if repeated)",
    ".NOTES":        "free-text note (alternate spelling, treated as .NOTE)",
    ".GEO":          "geographic/dialect restriction (EOJ=Eastern, NEOJ/SEOJ/CEOJ/UEOJ)",
    ".ACCENTCLASS":  "accent class",
    ".USE":          "usage restriction",
    ".PTR":          "pointer to another entry",
}

# Fields that are genuinely multi-valued (appear >1 time per entry in the corpus)
MULTI_VALUE_FIELDS: frozenset[str] = frozenset({
    ".FORM",
    ".KANA",
    ".MEANING",
    ".COMPOUND",
    ".RELATED",
    ".MKTARGETNEW",
    ".DERIVATION",
    ".TRANSREL",
    ".NOTE",
    ".VCLASS",
    ".ITYPE",
    ".POS",
    ".GEO",
    ".PTR",
})

# The five required fields in canonical order for a well-formed entry
REQUIRED_FIELDS: tuple[str, ...] = (".GLOSS", ".MEANING", ".FORM", ".KANA", ".POS")


# ── Dictionary .POS vocabulary (major values) ─────────────────────────────────

POS_VALUES: dict[str, str] = {
    "noun":                   "common noun",
    "noun (deverbal)":        "deverbal noun",
    "noun (covert)":          "covert/empty noun",
    "noun (exposed)":         "exposed noun head",
    "noun (deictic)":         "deictic noun",
    "personal name":          "personal name",
    "place name":             "place name",
    "verb":                   "verb",
    "adjective":              "adjective",
    "adverb":                 "adverb",
    "auxiliary":              "inflectional auxiliary",
    "prefix":                 "prefix",
    "suffix":                 "suffix",
    "case particle":          "case-marking particle",
    "topic particle":         "topic-marking particle",
    "focus particle":         "focus particle",
    "restrictive particle":   "restrictive particle",
    "conjunctional particle": "conjunctional particle",
    "interjectional particle":"interjectional particle",
    "final particle":         "sentence-final particle",
    "complementizer particle":"complementizer particle",
    "copula":                 "copula",
    "adjectival copula":      "adjectival copula",
    "pronoun (personal)":     "personal pronoun",
    "pronoun (demonstrative (proximal))": "proximal demonstrative pronoun",
    "pronoun (demonstrative (mesial))":   "mesial demonstrative pronoun",
    "pronoun (demonstrative (distal))":   "distal demonstrative pronoun",
    "pronoun (interrogative)":            "interrogative pronoun",
    "pronoun (reflexive)":                "reflexive pronoun",
    "numeral":                "numeral",
    "classifier":             "numeral classifier",
    "interjection":           "interjection",
    "extension":              "extension (XTN) morpheme",
    "makura kotoba":          "makura-kotoba (pillow word / fixed epithet)",
}


# ── Inflection type vocabulary ────────────────────────────────────────────────

ITYPE_VALUES: dict[str, str] = {
    "quadrigrade":                    "yodan (four-grade) conjugation",
    "lower_bigrade":                  "shimo-nidan (lower two-grade) conjugation",
    "upper_bigrade":                  "kami-nidan (upper two-grade) conjugation",
    "upper_monograde":                "kami-ichidan (upper one-grade) conjugation",
    "KU-adjective":                   "ku-katsuyō adjective",
    "SIKU-adjective":                 "shiku-katsuyō adjective",
    "R-irregular":                    "ra-hen irregular (ari, wori, haberi, …)",
    "N-irregular":                    "na-hen irregular",
    "K-irregular":                    "ka-hen irregular (ku, ko, ki)",
    "S-irregular":                    "sa-hen irregular (su, se, si)",
    "irregular":                      "irregular (other)",
    "non-inflecting":                 "uninflected (particles, some nouns)",
}


# ── Geographic/dialect codes ──────────────────────────────────────────────────

GEO_VALUES: dict[str, str] = {
    "EOJ":  "Eastern Old Japanese",
    "NEOJ": "North-Eastern Old Japanese",
    "SEOJ": "South-Eastern Old Japanese",
    "CEOJ": "Central-Eastern Old Japanese",
    "UEOJ": "Upper-Eastern Old Japanese",
}


# ── Text collection codes ─────────────────────────────────────────────────────

TEXT_COLLECTIONS: dict[str, str] = {
    "BS":   "Buddha's Footprints Stones (21 texts)",
    "EN":   "Engi-shiki Norito",
    "FK":   "Fudoki poems (Hitachi, Harima, Hizen, Tango, Ise)",
    "JSHT": "Jōgū Shōtoku Hōtei Setsu (4 texts)",
    "KH":   "Kaifūsō / related texts (40 texts)",
    "KK":   "Kojiki kayō — songs embedded in the Kojiki (112 poems)",
    "MYS":  "Man'yōshū — Japan's earliest poetry anthology (4,685 poems)",
    "NSK":  "Nihon shoki kayō — songs embedded in the Nihon shoki (133 poems)",
    "SM":   "Shoku-Nihongi Senmyō",
    "SNK":  "Shoku Nihon Kōki or related texts",
}
