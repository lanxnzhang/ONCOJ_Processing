from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coj.core.corpus import CorpusDocument
from coj.core.dictionary import Dictionary

LOCKED = {"TEXT_FOLDER", "DICT_FILE", "OUTPUT_FOLDER", "OVERWRITE_SOURCE"}


def inspect_settings(path: Path) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = []
    in_settings = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if "USER SETTINGS" in line:
            in_settings = not in_settings
        if in_settings and line.lstrip().startswith("# ") and "IMPORTS" in line:
            break
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if not isinstance(target, ast.Name) or target.id in LOCKED:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(value, (str, int, float, bool)):
            choices = None
            if target.id == "AUTO_MATCH_MODE": choices = ["strict", "loose"]
            result.append({"name": target.id, "value": value,
                           "type": type(value).__name__, "choices": choices})
    return result


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("coj_user_processor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load processor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line_records(before_dir: Path, output: Path) -> list[dict]:
    records = []
    for produced in sorted(output.glob("*_processed.xml")):
        source_name = produced.name.removesuffix("_processed.xml") + ".xml"
        source = before_dir / source_name
        if not source.exists():
            continue
        old_doc, new_doc = CorpusDocument.from_file(str(source)), CorpusDocument.from_file(str(produced))
        for ui, (old_utt, new_utt) in enumerate(zip(old_doc, new_doc), 1):
            old_lines, new_lines = old_utt.corpus_lines(), new_utt.corpus_lines()
            for li, (old, new) in enumerate(zip(old_lines, new_lines), 1):
                if old.to_text() == new.to_text():
                    continue
                old_id = str(old.lemma_id) if old.lemma_id else None
                new_id = str(new.lemma_id) if new.lemma_id else None
                records.append({
                    "file": source_name, "utterance": old_utt.sentence_id or str(ui),
                    "position": li, "form": new.word_form or old.word_form or "",
                    "path": new.synt_path, "category": "new" if not old_id and new_id else "existing",
                    "old_lemma": old_id, "new_lemma": new_id,
                    "before": old.to_text(), "after": new.to_text(),
                })
    return records


def dict_records(source: Path, output: Path) -> list[dict]:
    candidates = [output / "dictionary_processed.xml", output / "dictionary.xml"]
    produced = next((p for p in candidates if p.exists()), None)
    if produced is None:
        return []
    old, new = Dictionary.from_file(str(source)), Dictionary.from_file(str(produced))
    records = []
    ids = sorted({str(e.eid) for e in old} | {str(e.eid) for e in new})
    for eid in ids:
        a, b = old.get(eid), new.get(eid)
        if a == b:
            continue
        kind = "added" if a is None else "deleted" if b is None else "revised"
        fields = [] if b is None else [
            {"tag": tag, "values": b.get_all(tag)} for tag in b.tags()
        ]
        records.append({"id": eid, "category": kind, "fields": fields,
                        "before": a.to_text() if a else "", "after": b.to_text() if b else ""})
    return records


def run(path: Path, run_dir: Path, config_path: Path) -> None:
    module = load_module(path)
    allowed = {item["name"]: item for item in inspect_settings(path)}
    requested = json.loads(config_path.read_text(encoding="utf-8"))
    for name, value in requested.items():
        if name not in allowed:
            continue
        expected = allowed[name]["type"]
        if expected == "bool" and not isinstance(value, bool):
            raise ValueError(f"{name} must be a boolean")
        if expected == "int" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"{name} must be an integer")
        if expected == "str" and not isinstance(value, str):
            raise ValueError(f"{name} must be text")
        setattr(module, name, value)

    module.TEXT_FOLDER = str(run_dir / "data" / "text")
    module.DICT_FILE = str(run_dir / "data" / "dict" / "dictionary.xml")
    module.OUTPUT_FOLDER = str(run_dir / "output")
    module.OVERWRITE_SOURCE = False
    entrypoint = getattr(module, "process_files", None) or getattr(module, "main", None)
    if entrypoint is None:
        raise RuntimeError("Processor must define process_files() or main()")
    entrypoint()

    output_files = [p.name for p in sorted((run_dir / "output").iterdir()) if p.is_file()]
    result = {
        "lines": line_records(run_dir / "data" / "text", run_dir / "output"),
        "dictionary": dict_records(run_dir / "data" / "dict" / "dictionary.xml", run_dir / "output"),
        "files": output_files,
    }
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "inspect":
        print(json.dumps(inspect_settings(Path(sys.argv[2]))))
    elif sys.argv[1] == "run":
        run(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
