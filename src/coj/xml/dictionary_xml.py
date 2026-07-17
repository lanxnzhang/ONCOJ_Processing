"""
XML serialisation, deserialisation, and text rendering for ONCOJ dictionary entries.

Public API
----------
dictionary_to_xml(dictionary)           → XML string
dictionary_to_xml_file(dictionary, path)
entry_to_xml(entry)                     → XML string for one DictEntry
entry_to_str(entry)                     → human-readable string for one DictEntry

dictionary_from_xml(xml_str)            → Dictionary
dictionary_from_xml_file(path)          → Dictionary
entry_from_xml(xml_str)                 → DictEntry
"""

from __future__ import annotations

import io
import os
import xml.etree.ElementTree as ET

from coj.core.dictionary import DictEntry, Dictionary


# ── Field mapping tables ───────────────────────────────────────────────────────

_MULTI_TAG_MAP: dict[str, tuple[str, str]] = {
    ".MEANING":  ("meanings", "meaning"),
    ".POS":      ("pos", "value"),
    ".ITYPE":    ("itype", "value"),
    ".VCLASS":   ("vclass", "value"),
    ".GEO":      ("geo", "value"),
    ".PTR":      ("ptr", "value"),
    ".NOTE":     ("notes", "note"),
    ".NOTES":    ("notes", "note"),  # alias — merged into same wrapper
}

_CROSS_REF_MAP: dict[str, str] = {
    ".COMPOUND":    "compound",
    ".RELATED":     "related",
    ".MKTARGET":    "mk-target-legacy",
    ".MKTARGETNEW": "mk-target",
    ".DERIVATION":  "derivation",
    ".TRANSREL":    "transrel",
}

_SINGULAR_MAP: dict[str, str] = {
    ".GLOSS":        "gloss",
    ".CORRESP":      "corresp",
    ".AFFIX":        "affix",
    ".ACCENTCLASS":  "accent-class",
    ".USE":          "use",
    ".TRANSITIVITY": "transitivity",
    ".INTRVCLASS":   "intrv-class",
}


def _parse_cross_ref(raw: str) -> dict[str, str]:
    """Parse 'ref_target=L000006a\\tzu' → {'target': 'L000006a', 'form': 'zu'}."""
    target = ""
    form = ""
    if "ref_target=" in raw:
        after = raw.split("ref_target=", 1)[1]
        parts = after.split(None, 1)
        target = parts[0] if parts else ""
        form = parts[1].strip() if len(parts) > 1 else ""
    return {"target": target, "form": form}


# ── XML construction ───────────────────────────────────────────────────────────


def _entry_to_elem(entry: DictEntry) -> ET.Element:
    """Convert a DictEntry to an XML <entry> element."""
    elem = ET.Element("entry")
    elem.set("id", str(entry.eid))

    # .GLOSS — singular, normally first.  Omit it when it was absent in the
    # source rather than turning a missing field into an explicitly blank one.
    if entry.has(".GLOSS"):
        gloss_elem = ET.SubElement(elem, "gloss")
        gloss_elem.text = entry.get_first(".GLOSS") or ""

    # .MEANING — multi-valued
    meanings = entry.get_all(".MEANING")
    if meanings:
        wrap = ET.SubElement(elem, "meanings")
        for m in meanings:
            ET.SubElement(wrap, "meaning").text = m

    # .FORM / .KANA — paired
    form_vals = entry.get_all(".FORM")
    kana_vals = entry.get_all(".KANA")
    forms_elem = ET.SubElement(elem, "forms")
    for i, phonemic in enumerate(form_vals):
        kana = kana_vals[i] if i < len(kana_vals) else ""
        fe = ET.SubElement(forms_elem, "form")
        fe.set("phonemic", phonemic)
        fe.set("kana", kana)

    # .POS — multi-valued
    pos_vals = entry.get_all(".POS")
    if pos_vals:
        wrap = ET.SubElement(elem, "pos")
        for p in pos_vals:
            ET.SubElement(wrap, "value").text = p

    # Remaining multi-valued fields (NOTE/NOTES share a single <notes> wrapper)
    notes_added: list[str] = []
    for tag, (wrapper_tag, child_tag) in _MULTI_TAG_MAP.items():
        if tag in (".GLOSS", ".MEANING", ".POS", ".FORM", ".KANA"):
            continue
        if tag in (".NOTE", ".NOTES"):
            notes_added.extend(entry.get_all(tag))
            continue
        vals = entry.get_all(tag)
        if vals:
            wrap = ET.SubElement(elem, wrapper_tag)
            for v in vals:
                ET.SubElement(wrap, child_tag).text = v

    if notes_added:
        wrap = ET.SubElement(elem, "notes")
        for note_text in notes_added:
            ET.SubElement(wrap, "note").text = note_text

    # Cross-reference fields
    for tag, wrapper_tag in _CROSS_REF_MAP.items():
        refs = entry.get_all(tag)
        if refs:
            wrap = ET.SubElement(elem, wrapper_tag)
            for raw_ref in refs:
                parsed = _parse_cross_ref(raw_ref)
                ref_elem = ET.SubElement(wrap, "ref")
                ref_elem.set("target", parsed["target"])
                ref_elem.set("form", parsed["form"])
                # Some source values contain relation labels before ref_target,
                # blank targets, or other legacy formatting.  Keep the exact
                # value so XML -> text is lossless while target/form remain
                # available as structured attributes.
                ref_elem.set("raw", raw_ref)

    # Singular optional fields (omit if absent)
    for tag, xml_name in _SINGULAR_MAP.items():
        if tag == ".GLOSS":
            continue  # already handled above
        val = entry.get_first(tag)
        if val:
            ET.SubElement(elem, xml_name).text = val

    return elem


# ── Public API ─────────────────────────────────────────────────────────────────


def dictionary_to_xml(dictionary: Dictionary) -> str:
    """Serialise a Dictionary to an XML string."""
    root = ET.Element("dictionary")
    root.set("version", "1.0")
    for entry in dictionary:
        root.append(_entry_to_elem(entry))
    ET.indent(root, space="  ")
    buf = io.BytesIO()
    ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


def dictionary_to_xml_file(dictionary: Dictionary, path: str) -> None:
    """Write dictionary XML to *path*."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(dictionary_to_xml(dictionary))


def entry_to_xml(entry: DictEntry) -> str:
    """Serialise a single DictEntry to an XML string."""
    elem = _entry_to_elem(entry)
    ET.indent(elem, space="  ")
    return ET.tostring(elem, encoding="unicode")


# ── Text rendering ─────────────────────────────────────────────────────────────


# ── XML → Dictionary ──────────────────────────────────────────────────────────

# Inverse maps: XML wrapper element name → dict field tag
_XML_TO_MULTI: dict[str, str] = {
    "meanings":  ".MEANING",
    "pos":       ".POS",
    "itype":     ".ITYPE",
    "vclass":    ".VCLASS",
    "geo":       ".GEO",
    "ptr":       ".PTR",
    "notes":     ".NOTE",
}

_XML_TO_CROSS_REF: dict[str, str] = {
    "compound":         ".COMPOUND",
    "related":          ".RELATED",
    "mk-target-legacy": ".MKTARGET",
    "mk-target":        ".MKTARGETNEW",
    "derivation":       ".DERIVATION",
    "transrel":         ".TRANSREL",
}

_XML_TO_SINGULAR: dict[str, str] = {
    "corresp":      ".CORRESP",
    "affix":        ".AFFIX",
    "accent-class": ".ACCENTCLASS",
    "use":          ".USE",
    "transitivity": ".TRANSITIVITY",
    "intrv-class":  ".INTRVCLASS",
}


def _entry_from_elem(elem: ET.Element) -> DictEntry:
    """Convert an <entry> XML element back to a DictEntry."""
    eid = elem.get("id") or ""
    entry = DictEntry(eid)

    for child in elem:
        tag = child.tag

        if tag == "gloss":
            entry.set(".GLOSS", child.text or "")

        elif tag == "meanings":
            for m in child:
                entry.append(".MEANING", m.text or "")

        elif tag == "forms":
            for fe in child:
                entry.append(".FORM", fe.get("phonemic") or "")
                entry.append(".KANA", fe.get("kana") or "")

        elif tag in _XML_TO_MULTI:
            field = _XML_TO_MULTI[tag]
            for item in child:
                entry.append(field, item.text or "")

        elif tag in _XML_TO_CROSS_REF:
            field = _XML_TO_CROSS_REF[tag]
            for ref in child:
                raw_value = ref.get("raw")
                if raw_value is not None:
                    entry.append(field, raw_value)
                    continue
                target = ref.get("target") or ""
                form = ref.get("form") or ""
                raw = f"ref_target={target}\t{form}" if form else f"ref_target={target}"
                entry.append(field, raw)

        elif tag in _XML_TO_SINGULAR:
            entry.set(_XML_TO_SINGULAR[tag], child.text or "")

    return entry


def dictionary_from_xml(xml_str: str) -> Dictionary:
    """Parse an XML string back into a Dictionary."""
    root = ET.fromstring(xml_str)
    d: Dictionary = Dictionary()
    for child in root:
        if child.tag == "entry":
            d.add(_entry_from_elem(child))
    return d


def dictionary_from_xml_file(path: str) -> Dictionary:
    """Read an XML file and return a Dictionary."""
    with open(path, encoding="utf-8") as fh:
        return dictionary_from_xml(fh.read())


def entry_from_xml(xml_str: str) -> DictEntry:
    """Parse an XML string containing a single <entry> element into a DictEntry."""
    return _entry_from_elem(ET.fromstring(xml_str))


# ── Text rendering ─────────────────────────────────────────────────────────────


def entry_to_str(entry: DictEntry) -> str:
    """Return a compact human-readable summary of a DictEntry."""
    eid = str(entry.eid)
    pos = entry.get_first(".POS") or ""
    gloss = entry.get_first(".GLOSS") or ""
    meanings = entry.get_all(".MEANING")
    meaning_str = " / ".join(meanings) if meanings else ""

    form_vals = entry.get_all(".FORM")
    kana_vals = entry.get_all(".KANA")
    form_parts = []
    for i, f in enumerate(form_vals):
        k = kana_vals[i] if i < len(kana_vals) else ""
        form_parts.append(f"{f} ({k})" if k else f)
    forms_str = " | ".join(form_parts)

    lines = [f"{eid}  {pos}  {gloss} — {meaning_str}"]
    if forms_str:
        lines.append(f"  Forms:    {forms_str}")

    for ref_tag, label in (
        (".COMPOUND", "Compound"),
        (".RELATED", "Related"),
        (".MKTARGETNEW", "MK-target"),
        (".DERIVATION", "Derivation"),
    ):
        refs = entry.get_all(ref_tag)
        if refs:
            ref_parts = []
            for raw in refs:
                parsed = _parse_cross_ref(raw)
                ref_parts.append(f"{parsed['form']} ({parsed['target']})")
            lines.append(f"  {label}: {' | '.join(ref_parts)}")

    return "\n".join(lines)
