from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from compreditor.config import COLLECTIONS, SOURCE_XML, WORKSPACE
from compreditor.services.xml_tools import node_payload, word_rows

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+\.xml$")


class WorkspaceRepository:
    """Read canonical XML and write every mutation to an isolated overlay."""

    def __init__(self, source_root: Path = SOURCE_XML, workspace_root: Path = WORKSPACE):
        self.source_root = Path(source_root)
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._deleted_file = self.workspace_root / "deleted.json"

    def _validate(self, collection: str, name: str) -> None:
        if collection not in COLLECTIONS:
            raise ValueError("Unknown document collection")
        if not NAME_RE.fullmatch(name) or Path(name).name != name:
            raise ValueError("Invalid document filename")

    def _deleted(self) -> set[str]:
        if not self._deleted_file.exists():
            return set()
        return set(json.loads(self._deleted_file.read_text(encoding="utf-8")))

    def _save_deleted(self, values: set[str]) -> None:
        self._deleted_file.write_text(
            json.dumps(sorted(values), indent=2), encoding="utf-8"
        )

    def overlay_path(self, collection: str, name: str) -> Path:
        self._validate(collection, name)
        return self.workspace_root / "data" / collection / name

    def source_path(self, collection: str, name: str) -> Path:
        self._validate(collection, name)
        return self.source_root / collection / name

    def visible_path(self, collection: str, name: str) -> Path:
        key = f"{collection}/{name}"
        if key in self._deleted():
            raise FileNotFoundError(key)
        overlay = self.overlay_path(collection, name)
        source = self.source_path(collection, name)
        if overlay.is_file():
            return overlay
        if source.is_file():
            return source
        raise FileNotFoundError(key)

    def list_names(self, collection: str) -> list[str]:
        if collection not in COLLECTIONS:
            raise ValueError("Unknown document collection")
        names = {path.name for path in (self.source_root / collection).glob("*.xml")}
        names |= {
            path.name for path in (self.workspace_root / "data" / collection).glob("*.xml")
        }
        deleted = self._deleted()
        return sorted(name for name in names if f"{collection}/{name}" not in deleted)

    def outline(self) -> list[dict]:
        result = []
        for collection in COLLECTIONS:
            groups: dict[str, list[dict]] = {}
            for name in self.list_names(collection):
                stem = Path(name).stem
                family = stem.split("_", 1)[0]
                path = self.visible_path(collection, name)
                try:
                    root = ET.parse(path).getroot()
                    sentence_count = sum(child.tag == "block" for child in root)
                except ET.ParseError:
                    sentence_count = 0
                groups.setdefault(family, []).append({
                    "name": name,
                    "id": stem,
                    "sentences": sentence_count,
                    "modified": self.overlay_path(collection, name).is_file(),
                })
            result.append({
                "collection": collection,
                "label": "Texts under editing" if collection == "text" else "Uploaded trees",
                "families": [
                    {"name": family, "documents": docs}
                    for family, docs in sorted(groups.items())
                ],
            })
        return result

    def load(self, collection: str, name: str) -> ET.ElementTree:
        return ET.parse(self.visible_path(collection, name))

    def save(self, collection: str, name: str, tree: ET.ElementTree) -> Path:
        destination = self.overlay_path(collection, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        tree.getroot().set("filename", name.replace(".xml", ".txt"))
        ET.indent(tree.getroot(), space="  ")
        tree.write(destination, encoding="utf-8", xml_declaration=True)
        deleted = self._deleted()
        deleted.discard(f"{collection}/{name}")
        self._save_deleted(deleted)
        return destination

    def create(self, collection: str, name: str) -> ET.ElementTree:
        self._validate(collection, name)
        try:
            self.visible_path(collection, name)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(name)
        root = ET.Element("document", {"filename": name.replace(".xml", ".txt")})
        tree = ET.ElementTree(root)
        self.save(collection, name, tree)
        return tree

    def delete(self, collection: str, name: str) -> None:
        self.visible_path(collection, name)
        overlay = self.overlay_path(collection, name)
        if overlay.exists():
            overlay.unlink()
        deleted = self._deleted()
        deleted.add(f"{collection}/{name}")
        self._save_deleted(deleted)

    def payload(self, collection: str, name: str) -> dict:
        tree = self.load(collection, name)
        root = tree.getroot()
        sentences = []
        for index, block in enumerate(root):
            if block.tag != "block":
                continue
            sentences.append({
                "path": str(index),
                "id": block.get("id", ""),
                "header": block.get("header", ""),
                "words": len([elem for elem in block.iter() if elem.get("form") is not None]),
            })
        return {
            "collection": collection,
            "name": name,
            "source": "workspace" if self.overlay_path(collection, name).is_file() else "canonical",
            "tree": node_payload(root),
            "sentences": sentences,
            "words": word_rows(root),
        }

    @property
    def dictionary_source(self) -> Path:
        return self.source_root / "dict" / "dictionary.xml"

    @property
    def dictionary_overlay(self) -> Path:
        return self.workspace_root / "data" / "dict" / "dictionary.xml"

    @property
    def dictionary_path(self) -> Path:
        return self.dictionary_overlay if self.dictionary_overlay.is_file() else self.dictionary_source

    def save_dictionary(self, dictionary) -> Path:
        self.dictionary_overlay.parent.mkdir(parents=True, exist_ok=True)
        dictionary.to_file(str(self.dictionary_overlay))
        return self.dictionary_overlay

