# ONCOJ Processing

Tools and data model for the [Oxford-NINJAL Corpus of Old Japanese (ONCOJ)](https://oncoj.ninjal.ac.jp/) — a parsed corpus of 7th–8th century Japanese texts (Man'yōshū, Kojiki kayō, Nihon shoki kayō, Senmyō, and others) totalling ~100,000 lexical items. Licensed CC BY 4.0.

---

## Repository layout

```
data/
  dict/dictionary.txt   — ~7,000-entry lexical dictionary
  text/                 — corpus text files (one per source text)
scripts/
  lemmas_processor_2.0.4.py         — standard lemma annotator
  compound_lemma_processor_1.0.1.py — compound noun inserter
  mk_lemma_processor_1.0.1.py       — makura-kotoba processor
src/oncoj/              — Python package: core data model
notebooks/
  oncoj_usage.ipynb     — interactive usage examples
tests/                  — pytest test suite
```

---

## `src/oncoj` — core data model

A pure Python 3 package (no external dependencies) formalising the ONCOJ domain objects.

| Module | Key exports |
|---|---|
| `kana.py` | `phonemic_to_kana(form)` — Frellesvig-Whitman romanisation → historical katakana |
| `lemma_id.py` | `LemmaID` (immutable, hashable, orderable), `IDGenerator` |
| `dictionary.py` | `DictEntry`, `Dictionary` — load, query, mutate, serialise |
| `corpus.py` | `CorpusLine`, `CommentLine`, `Utterance`, `CorpusDocument` |
| `tags.py` | `PHON_TAGS`, `MULTI_VALUE_FIELDS`, `REQUIRED_FIELDS`, reference dicts, `strip_disambig()` |

### Quick start

```python
import sys
sys.path.insert(0, 'src')

from oncoj.dictionary import Dictionary
from oncoj.corpus import CorpusDocument
from oncoj.kana import phonemic_to_kana

# Load the dictionary
d = Dictionary.from_file('data/dict/dictionary.txt')
print(len(d), "entries")                    # 7006 entries
e = d["L000006a"]
print(e.get_first(".GLOSS"), e.get_all(".FORM"))  # NEG  ['nu', 'zu']

# Phonemic → katakana
print(phonemic_to_kana("kamu nusi"))        # カム ヌシ

# Load a corpus document
doc = CorpusDocument.from_file('data/text/EN_01.txt')
print(len(doc), "utterances")
hits = doc.find_by_form("para")
for utt, cl in hits:
    print(utt.sentence_id, cl)
```

See [`notebooks/oncoj_usage.ipynb`](notebooks/oncoj_usage.ipynb) for a fully executed walkthrough of all five modules.

---

## Data formats

### Corpus lines

Comma-separated root-to-leaf tree paths, one per syntactic node:

```
IP-MAT,NP,N,LOG,kamu
IP-MAT,NP,N,L000006a,LOG,nu
```

- Last field: romanised phonemic word form
- Penultimate field: writing-mode tag (`LOG`, `PHON`, `NLOG`, `PHON-ON`, `BPHON`, …)
- Optional lemma ID (e.g. `L000006a`) inserted between the syntactic path and the tag
- Tags may carry a `;@N` disambiguation suffix (e.g. `N;@2`) — strip with `tags.strip_disambig()`

Utterances are separated by blank lines; headers follow the pattern `=N("…")`.

### Dictionary

Entries delimited by 51-dash separators (`---…---`), each opening with `=== L<number>`:

```
---------------------------------------------------
=== L000006a
.GLOSS	NEG
.MEANING	[negative]
.FORM	nu
.KANA	ヌ
.FORM	zu
.KANA	ズ
.POS	auxiliary
```

Required fields (canonical order): `.GLOSS`, `.MEANING`, `.FORM`, `.KANA`, `.POS`.
Multi-valued fields (may repeat per entry): `.FORM`, `.KANA`, `.MEANING`, `.COMPOUND`, `.RELATED`, `.DERIVATION`, `.TRANSREL`, `.NOTE`, `.VCLASS`, `.ITYPE`, `.POS`, `.GEO`, `.PTR`.

### Lemma IDs

Format: `<PREFIX><zero-padded-6-digit-number>[optional-letter-suffix]`  
Examples: `L000006a`, `N000001`, `T050877`

---

## Processing scripts

All three scripts in `scripts/` are standalone Python 3 files with no external dependencies. Configurable paths and behaviour flags are in a `# USER SETTINGS` block near the top of each file. Run directly:

```bash
python3 scripts/lemmas_processor_2.0.4.py
python3 scripts/compound_lemma_processor_1.0.1.py
python3 scripts/mk_lemma_processor_1.0.1.py
```

| Script | Purpose |
|---|---|
| `lemmas_processor_2.0.4.py` | Two-pass annotator: look up forms in dictionary (pass 1), assign new IDs to unknowns (pass 2) |
| `compound_lemma_processor_1.0.1.py` | Detects adjacent N+N compound pairs and inserts new compound entries |
| `mk_lemma_processor_1.0.1.py` | Replaces `L099999` sentinel IDs with real IDs for makura-kotoba entries |

---

## Tests

```bash
python3 -m pytest tests/
```

138 unit and integration tests across all five `oncoj` modules. Requires only the Python standard library and `pytest`.

---

## Corpus texts

| Code | Text |
|---|---|
| MYS | Man'yōshū |
| KK | Kojiki kayō |
| NSK | Nihon shoki kayō |
| SM | Senmyō |
| EN | Engi-shiki Norito |
| FK | Fudoki |
| BS | Buddha's Footprints Stones |
| KH | Kaifūsō |
| JSHT | — |
| SNK | — |

