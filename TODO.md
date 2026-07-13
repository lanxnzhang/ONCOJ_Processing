# TODO

## Build script editor
An essential purpose for this repository is to facilitate editing of data, with the help of scripts. It is inconvenient for users to revise scripts, download the results, read them in txt, and edit data in different softwares.
Create a simple GUI which allows the user to run scripts, see the running results, and edit the data.

### Features

- For right now:
  1. User can import scripts, make settings, and run them.
  2. User can see the running results, in particular the processed text lines and processed dictionary entries. Show processed text lines and dictionary entries in two areas/pages. For processed text lines, the results should show their file, position, syntax tree path, categories (new or existing) and so on, like the output information in reports. For processed dictionary entries, the results should show the lemma ID and revised contents.

-Next Step:
  1. Differentiate the text lines having single or multiple search/processed results.
  2. User can use dictionary.
  3. User can see the context of processed text lines.
  4. User can render syntax trees.
  5. User can modify the result.

### After commit d77c4ce

Currently, there are still issues with .py scripts. Do not make any change to the current scripts. Copy them(compound_lemma_processor, lemmas_processor, mk_lemma_processor) under the folder scripteditor, then only revise the new copied scripts. Rename the copied scripts as compound_lemma_forgui, lemma_forgui, mk_lemma_forgui. When show the choice of scripts in the GUI, do not show the '_' and 'forgui'. For example, in drop-down menu, their name should be shown as 'compound lemma','lemma','mk lemma'.

#### Refine the lemmas_forgui.py to a version suitable for the GUI
1. First, check if the script works properly. Make sure its function is: 
  Based on the xml data (not the txt); 
  Searched items should be leaves without 'lemma' tag. For example,  <N index="1" phon="LOG" form="papuri" /> should be detected and automatically assigned a lemma ID. <P-COMP lemma="L000530" phon="PHON" form="to" /> should be kept since it has a 'lemma' tag;
  When a form is in the dictionary, the lemma should equal to its lemma in the dictionary;
  When a form is not in the dictionary, a new unique lemma ID should be generated, and the user can choose to automatically add the new form in the dictionary;
  The object searched by AUTO_POS_QUERY is the content in leaves. For example, it is N in <N index="1" phon="LOG" form="papuri" />. 
2. In GUI, for the left part about settings:
  put the settings about True/False at the top, then the settings requiring user to type something;
  Put the checkbox at the right of the setting, not below it;
  Add discriptions of settings. When users put their mouse on an icon like ⍰, they will be able to see the discriptions of this setting. The discriptions disappear when user move away their mouse.
3. For realisation of functions in GUI:
  Move all lemma id settings to advanced settings (LEMMA_PREFIX  = "N"    # prefix for newly generated IDs  (L, N, F, T, …)LEMMA_DIGITS  = 6      # zero-padded width  (6 → N000001)LEMMA_START   = 1      # minimum numeric value for new IDs DICT_ID_PREFIX = "T"   # prefix applied when inserting an existing dict ID);
  The default lemma prefix is L, digits=6, start=1;
  Differentiate existing lemma been added and newly generated lemma in the output result, such as mark them or put them in different categories. Same as for dictionary entries - differenciate the existing and newly created;
  NORMALIZE_DICT is not needed. Do not run it in this script. But it may be added back in the future at another place or in another script.
4. For the realisation of ADVANCED_DISAMBIG in GUI: 
  Move it to the advanced settings. The default status is true.
  Mark the result with multiple candidates in the result.

### After commit 1c41a33

Create a new folder named scripts under scripteditor, and move the py scripts into this new folder.
Since the output results of processed lines are too many, user needs some methods to manage them. Add a filter to sort through different types of results. Advanced filter would allow user to limit the scope of files processed by the script, as well as the scope and quantity of the displayed results. 

### After commit 9b52355
The processing files should also include files in COJ/data/xml/trees, such as BS.xml. Add them in processing scope. Categorise them, since there are lots of files and it would be inconvenient for the users to browse and choose. 
For lemma_forgui.py:
  1. The disambig logic in lemma_forgui.py is wrong. The content in leaf should be matched with the pos part in the dictionary. For example, nwo has two candidates L000520, L051650. Since the leaf <N phon="LOG" form="nwo" /> is N, the first choice should be <entry id="L051650"> with <pos> <value>noun</value> but not  <entry id="L000520"> <value>case particle</value>. N means noun - there should be a mapping table for POS (part of speech) abbreviations in this repository. Candidates should be ranked from highest to lowest score. But the scores do not need to be shown in GUI at the current stage.
  2. LEMMA PREFIX, LEMMA DIGITS, LEMMA START, DICT ID PREFIX - these functions are currently unused. Remove them without affecting any other functionality.
In filter, add the function to customise displayed result scope in advanced filters. For example, showing 100-200 of 380 matching changes. This function should not go against with 'Maximum displayed'. Consider refine them and make it more convenient for user to browse the result.

### After commit 9b7f7a9
Now we need to add a dictionary in the GUI. The dictionary should be able to open and hide. Basically, the user can search for form or lemma id in the dictionary. When they do so, the result should display a complete dictionary entry, in a reader-friendly format (I mean not in the raw xml data format). Also add advanced search function, which currently allows user to customise the type of data they search in the dictionary(gloss, note...), and should be compatible with more complex future functions.
The user can click the lemma id in the candidates to directly open that entry format. It should facilitate the review and search.

### After commit 389b645
Results automatically generated by the script may be inaccurate and require manual verification. Therefore, we need to add a manual review function for the output.
This function includes the following:
  1. Confirm. User thinks this item of output is problem-free. User can check the box or mark a button to confirm. Only confirmed results will be written to the final output file. A "select all" function is required, supporting selection by category. The interface needs to be clean and intuitive.
  In addition, add an optional feature allowing users to choose whether to hide confirmed result items from the results list.
  2. Choose. For results with multiple candidates, if the user finds that the highest-scoring result is not a match, they can select and switch to one of the other candidates.
  3. Add. If the user determines that there is no matching result among the candidates, they need to add a new dictionary entry. In this case, the program automatically assigns a unique new dictionary ID to the resulting form and generates the content for the "form" and "kana" tags in this dictionary entry, along with empty tags for standard dictionary entries (such as pos). User can revise, add, or delete tags.
  User can manually modify the ID number, but the system must display a warning if the numeric portion conflicts with an existing dictionary ID. 
  User can also edit the entry's content and click "Save" to add this new entry to the dictionary; however, manual confirmation is still required to commit the entries to the final output. Dictionary entries added via this method are selected by default within the dictionary output categories, though users can deselect them.


## Build interactive editor

An essential purpose for this repository is to facilitate research for linguists. The conventional text-declarative way of uploading and editing data poses a significant hurdle.
Create a simple GUI which allows the user to perform CRUD on the database. In particular, provide an interactive editor of corpora and syntax trees.

### Features

- For right now:
  1. User can browse the corpora database, with syntax trees rendered
  2. User can view the dictionary
  3. User can search for corpus by keyword
  4. User can query the dictionary

- Next step:
  1. User can create / modify / delete entries in the dictionary
  2. User can create / modify / delete corpora.

### After commit c9e699cc

This is a great starting point.
Next commit should focus on improving tree rendering.
Linguists view syntax trees very differently from computers. A verbatim presentation of the XML is actually *not* a good visualisation of the trees.
For linguists, the basis of all the trees are the *words themselves*. The word forms, e.g. mi, kusa, ramu, should be what gets displayed as the leaf level nodes. The intermediate nodes in the hierarchy are combinations of the leaves.
Ideally, the bottom layer of the syntax tree is just the original sentence, displayed flat. The tokens in the sentence could have flexibly calculated spacings to fit the intermediate nodes in display. To make this work, the tree has to be rotated from the current vertical layout.
Let's also enable element toggle, i.e. user can select what to show and hide in the tree view.
A diagram for how it would ideally look is given at `8096.png`.

### After commit 878aa270

Basically correct.
A major issue is that currently leaf-level tags are ignored. Render them above the actual word forms. In other words, keep the original tag-tree fully rendered, and align the word forms with each leaf-level tag in the end.

### After commit 467d3067

1. Visual clutter. Check the screenshot for details. Adjust horizontal spacing.
2. Option of bottom-up vertical aligning. The current align is top-down: nodes same level from the *root* gets aligned. Include another option of bottom-up align which may have greater visual appeal to linguists. Allow the user to toggle align mode, but make bottom-up default.

### After commit 908015ac

Horizontal spacing: This is a purely aesthetic optimisation. The current tree could benefit from a horizontal adjustment of non-leaf node positions, where the x-coordinate is determined not by the mean of its direct children, but the mean of all its recursive leaf node content. This will hopefully make the tree appear more "upright" and therefore more pleasant.

### After commit bd67a7bd

Vertical spacing: Sometimes the lines intersect. Usually it's not a problem, but let's try to address it anyway by allowing the user to customise vertical spacing with a slider.

### After commit 2debd889

## Automated reasoner

Inactive (TBD).

# Completed

<details><summary> Click to expand </summary>

## Collect constants

Created `src/oncoj/common/` sub-package. ANSI escape codes and colour helpers (`bold`, `blue`,
`magenta`, `yellow`) extracted from `ascii_tree.py` into `oncoj.common.ansi`; `ascii_tree.py`
now imports from there. Linguistic constants remain in `oncoj.core.tags` (already centralised).

## Convert to Python Package

Added `[build-system]` and `[project]` tables to `pyproject.toml`. Package name `coj`,
version `0.1.0`, `requires-python = ">=3.11"`, no runtime dependencies. `src/` layout
declared via `[tool.setuptools.packages.find]`. Installable with `pip install -e .`;
dev extras (`pytest`, `ruff`) via `pip install -e ".[dev]"`.

## XML-native rewrite

Rewrote the entire codebase so that XML is the canonical format:

- `data/xml/` is primary; `data/txt/` is derived (generated by `xml2txt.py`).
- All in-memory objects (`CorpusLine`, `Utterance`, `CorpusDocument`) wrap
  `xml.etree.ElementTree` elements directly — mutations write through to the XML tree.
- `CorpusDocument.from_file` auto-detects `.xml` vs `.txt` by extension.
- `Dictionary.from_file` / `to_file` likewise auto-detect format.
- All three package-based processors (`lemmas_processor.py`,
  `compound_lemma_processor.py`, `mk_lemma_processor.py`) moved to
  `scripts/processors/` and rewritten to read/write `data/xml/`.
- `compound_lemma_processor` fully XML-native: group detection and NP expansion walk
  the `ET.Element` tree; compound ID insertion is `bare_n_elem.set("lemma", id)`.
- 221 tests pass; ruff lint clean.

## Data Representation Schema Redesign

Proposed and implemented a structured XML format for both corpus and dictionary data.
Two separate formats:
- Corpus/trees: `<document>` → `<block>` → nested syntactic elements, leaf nodes carry
  `form`, `phon`, `lemma` attributes.
- Dictionary: `<dictionary>` → `<entry id="…">` → typed field sub-elements.

Conversion scripts in `scripts/data_conversion/`: `txt2xml.py`, `xml2txt.py`, `export.py`.
Round-trips are lossless (verified by test suite).

## MK Lemma Processor

Finds `L099999` occurrences in text files, replaces them with real unique IDs, creates
corresponding makura-kotoba dictionary entries, and optionally normalises existing MK
entries missing `.COMPOUND` / `.MKTARGETNEW` lines.

## Lemmas Processor

Two-pass annotator: look up word forms in the dictionary (pass 1, with disambiguation
heuristic), assign new IDs to unknown words (pass 2). Optional dictionary normalisation.

## Compound Noun Lemma Processor

Detects adjacent `N` / `N;@2` / … sibling groups sharing a bare marker-`N`, pairs
component lemma IDs left-to-right in layers, inserts the outermost compound ID.
Optional NP expansion pre-pass wraps direct `N`-at children of `<NP>` in a bare `<N>`.

</details>
