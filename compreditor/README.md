# COJ Comprehensive Editor

A modular local GUI for structured corpus and dictionary editing. It reads the
canonical files under `data/xml/`, but every edit, new file, dictionary change,
and deletion marker is stored under `compreditor/workspace/`. Canonical COJ data
is never written by this application.

```powershell
python -m pip install -r compreditor/requirements.txt
python compreditor/app.py
```

Open `http://127.0.0.1:5002`.

## Editor model

- The outline navigates collection, text family, text, sentence, and word layers.
- Text mode presents the XML hierarchy as readable selectable rows.
- Table mode displays every XML item and bulk-edits tag, text, form, phon, and lemma values.
- Tree mode presents selectable branches and words as a syntax tree.
- The central toolbar inserts, deletes, copies, pastes, reorders, and reparents nodes or branches.
- The inspector edits tags, text, attributes, and annotations in every mode.
- Sentence transcription remains visible as context when editing a sentence or word.

The right tools panel contains modular search, dictionary, and validation tools.
Search supports corpus/dictionary scopes, tag/form/lemma/phon criteria, AND/OR,
per-criterion exclusion, and parent-child structure expressions such as `NP > N`.
Dictionary entries support create/read/update/delete. Word-level lemma insertion
offers existing form candidates or creates a new entry using a configurable
starting number.

Validation runs whenever a document is opened or changed. Problems include XML
parse errors, missing attributes, invalid or unknown lemma IDs, duplicate sentence
IDs, malformed document structure, and dictionary issues. Selecting a document
problem navigates to its node.

## Modules

```text
compreditor/
  app.py                         application factory
  routes/                        document, dictionary, and search HTTP modules
  services/
    repository.py               canonical-read/workspace-write overlay
    editor.py                   shared structured CRUD operations
    search_service.py           scoped and advanced search
    dictionary_service.py       dictionary CRUD helpers and ID generation
    validation.py               continuous problem detection
    xml_tools.py                stable paths and XML/JSON tree conversion
  static/js/                     API, state, outline, modes, tools, orchestration
  workspace/                     ignored local changes, created automatically
```

Run the editor tests with:

```powershell
python -m pytest compreditor/tests -q
```
