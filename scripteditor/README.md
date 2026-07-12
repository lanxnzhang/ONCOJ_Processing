# COJ Script Editor

A local Flask GUI for configuring COJ processors, running them against copied XML data, and reviewing structured corpus-line and dictionary changes.

```powershell
python scripteditor/app.py
```

Open `http://127.0.0.1:5001`. Every run is stored under `scripteditor/runs/`; canonical files under `data/xml/` are never passed to a processor as writable inputs. Delete old run folders when they are no longer needed.

The initial version intentionally exposes the three package-based COJ processors rather than executing arbitrary uploaded Python. Adding uploaded scripts later requires an OS-level sandbox: Python code must otherwise be considered fully trusted.
