from __future__ import annotations

from compreditor.config import COLLECTIONS
from compreditor.services.xml_tools import element_at, iter_with_paths, sentence_for_path


def _candidate(elem, path: str, collection: str, name: str, root) -> dict[str, str]:
    sentence_id, sentence = sentence_for_path(root, path)
    attributes = " ".join(f"{key}={value}" for key, value in elem.attrib.items())
    return {
        "tag": elem.tag,
        "form": elem.get("form", ""),
        "lemma": elem.get("lemma", ""),
        "phon": elem.get("phon", ""),
        "text": elem.text or elem.get("raw", ""),
        "attributes": attributes,
        "collection": collection,
        "file": name,
        "sentence": sentence,
        "sentence_id": sentence_id,
        "path": path,
    }


def _matches(candidate: dict[str, str], criterion: dict) -> bool:
    field = str(criterion.get("field", "any"))
    operator = str(criterion.get("operator", "contains"))
    needle = str(criterion.get("value", "")).casefold()
    values = list(candidate.values()) if field == "any" else [candidate.get(field, "")]
    values = [str(value).casefold() for value in values]
    if operator == "equals":
        result = any(value == needle for value in values)
    elif operator == "starts":
        result = any(value.startswith(needle) for value in values)
    elif operator == "exists":
        result = any(bool(value) for value in values)
    else:
        result = any(needle in value for value in values)
    return not result if criterion.get("exclude") else result


def _structure_matches(root, path: str, structure: str) -> bool:
    tags = [tag.strip() for tag in structure.split(">") if tag.strip()]
    if not tags:
        return True
    indexes = [int(item) for item in path.split(".") if item != ""]
    chain = [root.tag]
    for depth in range(1, len(indexes) + 1):
        chain.append(element_at(root, ".".join(str(i) for i in indexes[:depth])).tag)
    return len(chain) >= len(tags) and chain[-len(tags):] == tags


def search(repository, payload: dict) -> list[dict]:
    query = str(payload.get("query", "")).strip()
    scope = str(payload.get("scope", "all"))
    criteria = payload.get("criteria", [])
    if not isinstance(criteria, list):
        raise ValueError("Search criteria must be a list")
    if query:
        criteria = [{"field": "any", "operator": "contains", "value": query}] + criteria
    logic = str(payload.get("logic", "all"))
    structure = str(payload.get("structure", "")).strip()
    limit = min(1000, max(1, int(payload.get("limit", 300))))
    current = payload.get("current") or {}
    collections = COLLECTIONS if scope in ("all", "corpus") else (scope,)
    if scope == "current":
        collections = (str(current.get("collection", "text")),)

    results = []
    for collection in collections:
        if collection not in COLLECTIONS:
            continue
        names = repository.list_names(collection)
        if scope == "current":
            names = [name for name in names if name == current.get("name")]
        for name in names:
            root = repository.load(collection, name).getroot()
            for elem, path in iter_with_paths(root):
                candidate = _candidate(elem, path, collection, name, root)
                decisions = [_matches(candidate, item) for item in criteria]
                accepted = (all(decisions) if logic == "all" else any(decisions)) if decisions else True
                if accepted and _structure_matches(root, path, structure):
                    results.append(candidate | {"label": elem.get("form") or elem.get("id") or elem.tag})
                    if len(results) >= limit:
                        return results
    return results

