from __future__ import annotations

from coj.core.dictionary import DictEntry, Dictionary
from coj.core.kana import phonemic_to_kana
from coj.core.lemma_id import LemmaID
from coj.core.tags import MULTI_VALUE_FIELDS


def entry_payload(entry: DictEntry) -> dict:
    return {
        "id": str(entry.eid),
        "fields": [
            {"tag": tag, "values": entry.get_all(tag)}
            for tag in entry.tags()
        ],
        "forms": entry.get_all(".FORM"),
        "gloss": entry.get_first(".GLOSS") or "",
        "pos": entry.get_all(".POS"),
    }


def entry_from_payload(raw: dict) -> DictEntry:
    entry_id = str(raw.get("id", "")).strip()
    if not LemmaID.is_valid(entry_id):
        raise ValueError("Use a dictionary ID such as L000001")
    entry = DictEntry(entry_id)
    fields = raw.get("fields", [])
    if not isinstance(fields, list):
        raise ValueError("Dictionary fields must be a list")
    for field in fields:
        tag = str(field.get("tag", "")).strip().upper()
        if not tag.startswith("."):
            tag = "." + tag
        values = field.get("values", [])
        if not isinstance(values, list):
            raise ValueError(f"Values for {tag} must be a list")
        cleaned = [str(value) for value in values]
        entry.set(tag, cleaned if tag in MULTI_VALUE_FIELDS else (cleaned[0] if cleaned else ""))
    return entry


def search_dictionary(dictionary: Dictionary, query: str, limit: int = 100) -> list[dict]:
    needle = query.casefold().strip()
    results = []
    for entry in dictionary:
        values = [str(entry.eid)]
        for tag in entry.tags():
            values.extend(entry.get_all(tag))
        score = 0
        for value in values:
            folded = value.casefold()
            if folded == needle:
                score = max(score, 3)
            elif folded.startswith(needle):
                score = max(score, 2)
            elif needle in folded:
                score = max(score, 1)
        if score:
            results.append((score, entry))
    results.sort(key=lambda item: (-item[0], str(item[1].eid)))
    return [entry_payload(entry) for _, entry in results[:limit]]


def suggest_id(dictionary: Dictionary, start: int = 1) -> str:
    used = dictionary.used_numbers()
    number = max(1, start)
    while number in used:
        number += 1
    return f"L{number:06d}"


def blank_entry(entry_id: str, form: str) -> dict:
    return {
        "id": entry_id,
        "fields": [
            {"tag": ".GLOSS", "values": [""]},
            {"tag": ".MEANING", "values": [""]},
            {"tag": ".FORM", "values": [form]},
            {"tag": ".KANA", "values": [phonemic_to_kana(form)]},
            {"tag": ".POS", "values": [""]},
        ],
    }

