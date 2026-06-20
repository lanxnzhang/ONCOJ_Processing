# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Scripts

No build system. All scripts are standalone Python 3 files. There are no CLI arguments; all configurable paths and behaviour flags are in a clearly marked `# USER SETTINGS` block near the top of each file.

Two editions exist for each script:

| Edition | Files | Who uses it |
|---|---|---|
| Package-based (recommended) | `lemmas_processor.py`, `compound_lemma_processor.py`, `mk_lemma_processor.py` | Developers — imports `src/oncoj` |
| Standalone | `lemmas_processor_standalone.py`, `compound_lemma_processor_standalone.py`, `mk_lemma_processor_standalone.py` | Linguists — zero non-stdlib dependencies |

```bash
# Package-based (requires src/ on the path, handled internally)
python3 scripts/lemmas_processor.py
python3 scripts/compound_lemma_processor.py
python3 scripts/mk_lemma_processor.py

# Standalone (no imports beyond stdlib)
python3 scripts/lemmas_processor_standalone.py
python3 scripts/compound_lemma_processor_standalone.py
python3 scripts/mk_lemma_processor_standalone.py
```

## Tests

```bash
python3 -m pytest tests/                        # all 221 tests
python3 -m pytest tests/test_dictionary.py      # single file
python3 -m pytest tests/test_corpus.py::TestCorpusLine  # single class
```

`conftest.py` adds `src/` to `sys.path` and exposes session-scoped fixtures: `dict_file` (`data/xml/dict/dictionary.xml`), `text_dir` (`data/xml/text/`), `sample_corpus_file` (`data/xml/text/EN_01.xml`).

## Data Format

**Corpus lines** are comma-separated tree paths from root to leaf:

```
IP-MAT,NP,N,LOG,kamu
IP-MAT,NP,N,L000006a,LOG,nu
```

- Last field: romanised phonemic word form
- Penultimate field: syntactic/phonetic tag (`LOG`, `PHON`, `VB-STM`, `N`, etc.)
- Optional lemma ID (e.g., `L050877`) inserted between the syntactic path and the tag

**Dictionary** (`data/txt/dict/dictionary.txt`): entries separated by `---` (51 dashes), each starting with `=== L<number>`. Required canonical fields in order: `.GLOSS`, `.MEANING`, `.FORM`, `.KANA`, `.POS`. Multi-valued fields (can repeat per entry): `.FORM`, `.KANA`, `.MEANING`, `.COMPOUND`, `.RELATED`, `.DERIVATION`, `.TRANSREL`, `.NOTE`, `.VCLASS`, `.ITYPE`, `.POS`, `.GEO`, `.PTR`. All other fields (`.CORRESP`, `.AFFIX`, `.ACCENTCLASS`, `.USE`) are singular.

**Writing-mode tags** (penultimate field before a word form): `LOG`, `PHON`, `NLOG`, `PHON-KUN`, `PHON-ON`, `PLOG`, `BPHON`, `ILL`, `ORDLOG`, `NLPOG`. Any syntactic tag may carry a `;@N` disambiguation suffix (e.g. `N;@2`, `C-NP;@5`) identifying the Nth sister with the same path — strip this before tag comparison.

**Utterance headers**: the `=N(" words ")` format exists only in the `.txt` derived format. The XML `<block>` element stores just the bare word string in its `header` attribute; the wrapper is added back automatically when converting to `.txt`.

**Corpus texts**: BS (Buddha's Footprints Stones), EN (Engi-shiki Norito), FK (Fudoki), JSHT, KH (Kaifūsō), KK (Kojiki kayō), MYS (Man'yōshū), NSK (Nihon shoki kayō), SM (Senmyō), SNK. Full tag/field reference: `src/oncoj/tags.py`.

## Architecture

All scripts follow the same pattern: load the dictionary, scan corpus text files, mutate lines, then write output and report files. The package-based editions delegate all I/O to `src/oncoj`; the standalone editions embed the same logic locally.

### `lemmas_processor` — Standard Lemma Annotator

Two-pass processing per corpus file:
1. **Pass 1** (`process_file_standard`): look up each unannotated token in the dictionary and insert the matching lemma ID.
2. **Pass 2** (`process_unknown_words`): assign new IDs (prefixed `N`) to tokens absent from the dictionary.

Key internals: `disambiguate()` uses a 0–3 scoring heuristic against the preceding syntactic tag when multiple dictionary entries share a `.FORM`. `dictionary.normalise_all()` rewrites dictionary entries to canonical field order.

### `compound_lemma_processor` — Compound Noun Inserter

Detects groups of adjacent `N` / `N;@2` / `N;@3` … sibling lines sharing a bare marker-`N` column, then pairs their component lemma IDs left-to-right in layers. `build_compound_entry()` creates a new dictionary block by concatenating component `.GLOSS`/`.MEANING`/`.FORM`/`.KANA` fields and adding `.COMPOUND` back-references. Optional `NP_EXPANSION` pre-pass detects NP-grouped N-at siblings and inserts a grouping bare `N` before running the main detector.

### `mk_lemma_processor` — Makura-kotoba Processor

Handles Old Japanese poetic pillow words marked with the sentinel `L099999`. Replaces each sentinel with a real unique ID, creates a dictionary entry with `.POS makura kotoba`. Optional second pass (`NORMALISE_EXISTING=True`) fills missing `.COMPOUND`/`.MKTARGETNEW` cross-references in existing MK entries by re-scanning the full corpus.

## Core Data Model (`src/oncoj/`)

A shared Python package formalising the domain objects. Use `sys.path.insert(0, 'src')` to import.

The package has two sub-packages:

### `oncoj.core` — domain model

| Module | Key exports |
|---|---|
| `oncoj.core.kana` | `phonemic_to_kana(form)` — romanised OJ → historical katakana |
| `oncoj.core.lemma_id` | `LemmaID` (immutable, hashable), `IDGenerator` |
| `oncoj.core.dictionary` | `DictEntry`, `Dictionary` (load/save/query/mutate) |
| `oncoj.core.corpus` | `CorpusLine`, `CommentLine`, `Utterance`, `CorpusDocument` |
| `oncoj.core.tags` | `PHON_TAGS`, `MULTI_VALUE_FIELDS`, `REQUIRED_FIELDS`, tag/POS/ITYPE reference dicts, `strip_disambig()` |

All code imports directly from `oncoj.core.*` or `oncoj.xml.*`.

### `oncoj.xml` — XML serialisation helpers (thin wrappers)

| Module | Key exports |
|---|---|
| `oncoj.xml.corpus_xml` | `corpus_to_xml_file(doc, path)`, `corpus_to_xml(doc)`, `utterance_to_xml(utt)`, `utterance_to_tree_str(utt)` |
| `oncoj.xml.dictionary_xml` | `dictionary_to_xml_file(d, path)`, `dictionary_to_xml(d)`, `entry_to_xml(entry)`, `entry_to_str(entry)` |

### `oncoj.visual` — visualisation

| Module | Key exports |
|---|---|
| `oncoj.visual.ascii_tree` | `ascii_tree(utt, *, show_comments=True, show_annotations=True, colour=False) → str` |
| | `print_tree(utt, *, show_comments=True, show_annotations=True, colour=None)` |

`ascii_tree` renders an `Utterance` as a box-drawing syntax tree. The sentence ID and bare word-list header appear on the first line; sibling indices (`;@N`) are suppressed in the visual output. All annotated nodes (leaf and internal) use the same `TAG  ( annotations… )` parenthesis format. Pass `colour=True` to enable ANSI highlighting (tags bold, word forms cyan, phon/script tags dim, lemma IDs yellow). `print_tree` auto-detects TTY when `colour=None` (default).

## Shared Conventions

- **Lemma ID format**: `<PREFIX><zero-padded-6-digit-number>[optional-letter-suffix]` — e.g., `L000006a`, `N000001`
- **Phonemic-to-katakana**: `phonemic_to_kana()` in `oncoj.core.kana`; the standalone scripts embed an identical copy locally (package postdates them).
- **Output mode**: controlled by `OVERWRITE_SOURCE` — either overwrite corpus files in place or write `*_processed.txt` files to `OUTPUT_FOLDER`; report files are always produced separately.
- **Sentinel IDs**: `L099999` = makura-kotoba placeholder (replaced by `mk_lemma_processor`); `L099997` is also reserved and excluded from normalisation.
- **Script/package split**: `*_standalone.py` scripts embed all logic locally and have zero non-stdlib dependencies. The package-based scripts (`lemmas_processor.py`, etc.) import `src/oncoj` via `sys.path.insert` at the top. The `src/oncoj` package is the clean API used by `tests/` and `notebooks/`. New code and refactors should use `src/oncoj`.
- **Import path**: `sys.path.insert(0, 'src')` before `from oncoj.core.X import Y`. Scripts use `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))`.
- **Linting**: `ruff` is configured in `pyproject.toml`. Run `ruff check .` to lint; E402/E741/E501 are suppressed globally (intentional `sys.path` pattern, corpus loop variables, and long data-table lines respectively).
