# ONCOJ Processing

Tools and data model for the [Oxford-NINJAL Corpus of Old Japanese (ONCOJ)](https://oncoj.ninjal.ac.jp/) — a parsed corpus of mainly 7th–8th century Japanese texts (_Man'yōshū_, _Kojiki kayō_, _Nihon shoki kayō_, and others) totalling ~100,000 lexical items. Licensed CC BY 4.0.

---

## Repository layout

```
data/
  dict/dictionary.txt             — ~7,000-entry lexical dictionary
  text/                           — texts still needing editing (EN and SM)
  trees/                          — texts already uploaded to the corpus
scripts/
  lemmas_processor.py             — standard lemma annotator (package-based)
  compound_lemma_processor.py     — compound noun inserter (package-based)
  mk_lemma_processor.py           — makura-kotoba processor (package-based)
  lemmas_processor_standalone.py             — same scripts, zero extra deps
  compound_lemma_processor_standalone.py
  mk_lemma_processor_standalone.py
src/oncoj/              — Python package: core data model
notebooks/
  oncoj_usage.ipynb               — src/oncoj package walkthrough
  lemmas_processor.ipynb          — demo of the lemma annotator algorithm
  compound_lemma_processor.ipynb  — demo of the compound noun algorithm
  mk_lemma_processor.ipynb        — demo of the makura-kotoba algorithm
tests/                  — pytest test suite (150 tests)
pyproject.toml          — ruff linter configuration
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
IP-MAT,NP,N,L000006a,LOG,nu
```

- Last field: romanised phonemic word form
- Penultimate field: script type tag (`LOG`, `PHON`, `NLOG`, `PHON-ON`, `BPHON`, …)
- Lemma ID (e.g. `L000006a`) inserted between the syntactic path and the tag
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

Each processing task has two script editions:

- **Package-based** (`lemmas_processor.py`, `compound_lemma_processor.py`, `mk_lemma_processor.py`): imports `src/oncoj`; recommended for developers extending the tools.
- **Standalone** (`*_standalone.py`): self-contained with no external dependencies beyond the Python standard library; intended for linguist users.

Both editions share the same `# USER SETTINGS` block interface and produce identical output. Run directly — no build step required:

```bash
python3 scripts/lemmas_processor.py
python3 scripts/compound_lemma_processor.py
python3 scripts/mk_lemma_processor.py
```

| Script | Purpose |
|---|---|
| `lemmas_processor` | Two-pass annotator: look up forms in dictionary (pass 1), assign new IDs to unknowns (pass 2) |
| `compound_lemma_processor` | Detects adjacent N+N compound groups, pairs them in layers, inserts compound IDs |
| `mk_lemma_processor` | Replaces `L099999` sentinel IDs with real IDs for makura-kotoba entries |

See `notebooks/` for a runnable demonstration of each script's algorithm against real corpus data.

---

## Tests and linting

```bash
python3 -m pytest tests/    # 150 unit and integration tests
ruff check .                # lint (config in pyproject.toml)
```

Requires only the Python standard library, `pytest`, and `ruff`.

---

## Corpus texts

| Code | Text |
|---|---|
| MYS | _Man'yōshū_ 万葉集 |
| KK | _Kojiki kayō_ 古事記歌謡 |
| NSK | _Nihon shoki kayō_ 日本書紀歌謡 |
| FK | _Fudoki kayō_ 風土記歌謡 |
| BS | _Bussokuseki-ka_ 仏足石歌 |
| KH | _Kakyō hyōshiki_ 歌経標式 |
| JSHT | _Jōgū shōtoku hōō teisetsu_ 上宮聖徳法王帝説 |
| SNK | _Shoku nihongi kayō_ 続日本紀歌謡 |
| SM | _Senmyō_ 宣命 |
| EN | _Engishiki Norito_ 延喜式祝詞 |

