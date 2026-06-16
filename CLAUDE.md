# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Scripts

No build system. Each script is a standalone Python 3 file with no external dependencies:

```bash
python3 src/lemmas_processor_2.0.4.py
python3 src/compound_lemma_processor_1.0.1.py
python3 src/mk_lemma_processor_1.0.1.py
```

All configurable paths and behaviour flags are defined in a clearly marked `# USER SETTINGS` block near the top of each file. There are no CLI arguments.

## Data Format

**Corpus lines** are comma-separated tree paths from root to leaf:

```
IP-MAT,NP,N,LOG,kamu
IP-MAT,NP,N,L000006a,LOG,nu
```

- Last field: romanised phonemic word form
- Penultimate field: syntactic/phonetic tag (`LOG`, `PHON`, `VB-STM`, `N`, etc.)
- Optional lemma ID (e.g., `L050877`) inserted between the syntactic path and the tag

**Dictionary** (`data/dict/dictionary.txt`): entries separated by `---` (51 dashes), each starting with `=== L<number>`. Required canonical fields in order: `.GLOSS`, `.MEANING`, `.FORM`, `.KANA`, `.POS`. Multi-valued fields (can repeat per entry): `.FORM`, `.KANA`, `.MEANING`, `.COMPOUND`, `.RELATED`, `.DERIVATION`, `.TRANSREL`, `.NOTE`, `.VCLASS`, `.ITYPE`, `.POS`, `.GEO`, `.PTR`. All other fields (`.CORRESP`, `.AFFIX`, `.ACCENTCLASS`, `.USE`) are singular.

**Writing-mode tags** (penultimate field before a word form): `LOG`, `PHON`, `NLOG`, `PHON-KUN`, `PHON-ON`, `PLOG`, `BPHON`, `ILL`, `ORDLOG`, `NLPOG`. Any syntactic tag may carry a `;@N` disambiguation suffix (e.g. `N;@2`, `C-NP;@5`) identifying the Nth sister with the same path — strip this before tag comparison.

**Corpus texts**: BS (Buddha's Footprints Stones), EN (Engi-shiki Norito), FK (Fudoki), JSHT, KH (Kaifūsō), KK (Kojiki kayō), MYS (Man'yōshū), NSK (Nihon shoki kayō), SM (Senmyō), SNK. Full tag/field reference: `src/oncoj/tags.py`.

## Architecture

All three scripts follow the same pattern: parse the dictionary into an in-memory structure, scan corpus text files, mutate lines, then write output and report files.

### `lemmas_processor_2.0.4.py` — Standard Lemma Annotator

Two-pass processing per corpus file:
1. **Pass 1** (`process_file_standard`): look up each unannotated token in the dictionary and insert the matching lemma ID.
2. **Pass 2** (`process_unknown_words`): assign new IDs (prefixed `N`) to tokens absent from the dictionary.

Key internals: `load_dictionary()` builds `form_to_lemma` and `form_to_candidates` maps. `disambiguate()` uses a 0–3 scoring heuristic against the preceding syntactic tag when multiple dictionary entries share a `.FORM`. `normalize_dictionary()` rewrites dictionary entries in-place to ensure canonical field order.

### `compound_lemma_processor_1.0.1.py` — Compound Noun Inserter

Detects adjacent line pairs representing two-part N+N compound nouns. Three pattern matchers (`match_core_pair`, `match_expanded1_pair`, `match_expanded2_pair`) handle structural variations. `build_new_entry()` creates a new dictionary block by concatenating component `.GLOSS`/`.MEANING`/`.FORM`/`.KANA` fields and adding `.COMPOUND` back-references.

### `mk_lemma_processor_1.0.1.py` — Makura-kotoba Processor

Handles Old Japanese poetic pillow words marked with the sentinel `L099999`. Replaces each sentinel with a real unique ID, creates a dictionary entry with `.POS makura kotoba`. Optional second pass (`NORMALISE_EXISTING=True`) fills missing `.COMPOUND`/`.RELATED` cross-references in existing MK entries by re-scanning the full corpus.

## Core Data Model (`src/oncoj/`)

A shared Python package formalising the domain objects. Use `sys.path.insert(0, 'src')` to import.

| Module | Key exports |
|---|---|
| `kana.py` | `phonemic_to_kana(form)` — romanised OJ → historical katakana |
| `lemma_id.py` | `LemmaID` (immutable, hashable), `IDGenerator` |
| `dictionary.py` | `DictEntry`, `Dictionary` (load/save/query/mutate) |
| `corpus.py` | `CorpusLine`, `CommentLine`, `Utterance`, `CorpusDocument` |
| `tags.py` | `PHON_TAGS`, `MULTI_VALUE_FIELDS`, `REQUIRED_FIELDS`, tag/POS/ITYPE reference dicts, `strip_disambig()` |

## Shared Conventions

- **Lemma ID format**: `<PREFIX><zero-padded-6-digit-number>[optional-letter-suffix]` — e.g., `L000006a`, `N000001`
- **Phonemic-to-katakana**: `phonemic_to_kana()` in `src/oncoj/kana.py`; previously duplicated in all three scripts
- **Output mode**: controlled by `OVERWRITE_SOURCE` — either overwrite corpus files in place or write `*_processed.txt` files to `OUTPUT_FOLDER`; report files are always produced separately
