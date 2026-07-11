# COJ

Processing tools for the [Oxford-NINJAL Corpus of Old Japanese (ONCOJ)](https://coj.ninjal.ac.jp/) — a parsed corpus of mainly 7th–8th century Japanese texts (_Man'yōshū_, _Kojiki kayō_, _Nihon shoki kayō_, and others) totalling ~100,000 lexical items. Licensed CC BY 4.0.

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

---

## Data

Corpus and dictionary files are stored in two equivalent formats under `data/`:

- `data/xml/` — canonical XML (primary)
- `data/txt/` — derived plain text (generated from XML by `scripts/data_conversion/xml2txt.py`)

The plain-text format represents each syntactic node as a comma-separated root-to-leaf path:

```
IP-MAT,NP,N,L000006a,LOG,nu
```

Dictionary entries in `data/txt/dict/dictionary.txt` are delimited by 51-dash separators and open with `=== L<number>`.

---

## Processing scripts

Three annotation tasks, each available as a self-contained standalone script (no dependencies beyond the Python standard library):

| Script | Purpose |
|---|---|
| `scripts/standalone_processors/lemmas_processor_standalone.py` | Look up word forms in the dictionary and insert lemma IDs; assign new IDs to unknowns |
| `scripts/standalone_processors/compound_lemma_processor_standalone.py` | Detect adjacent compound noun groups and insert compound lemma IDs |
| `scripts/standalone_processors/mk_lemma_processor_standalone.py` | Replace `L099999` makura-kotoba sentinels with real unique IDs |

All configurable paths and behaviour flags are in a `# USER SETTINGS` block near the top of each file. Run directly:

```bash
python3 scripts/standalone_processors/lemmas_processor_standalone.py
```
