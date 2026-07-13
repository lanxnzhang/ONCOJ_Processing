# COJ Script Editor

A local Flask GUI for configuring GUI-specific copies of the COJ processors,
running them against copied XML data, and reviewing structured corpus-line and
dictionary changes. The original files in `scripts/processors/` are never loaded
or modified by the GUI.

```powershell
python scripteditor/app.py
```

Open `http://127.0.0.1:5001`. Every run is stored under `scripteditor/runs/`; canonical files under `data/xml/` are never passed to a processor as writable inputs. Delete old run folders when they are no longer needed.

The editor exposes `compound lemma`, `lemma`, and `mk lemma`, backed by the
`*_forgui.py` copies in `scripteditor/scripts/`. Adding arbitrary uploaded scripts later
requires an OS-level sandbox: Python code must otherwise be considered fully
trusted.

Open **Processing scope** to run a processor on selected XML files only. After
a run, text-line results can be filtered by result type, candidate count, and
file, with a configurable maximum number of rendered results.
