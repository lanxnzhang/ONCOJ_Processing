"""
ASCII syntax-tree renderer for ONCOJ utterances.

Public API
----------
ascii_tree(utt, *, show_comments=True, show_annotations=True)  → str
print_tree(utt, *, show_comments=True, show_annotations=True)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from oncoj.core.corpus import Utterance, _utterance_to_elem

# Box-drawing characters
_TEE    = "├── "
_CORNER = "└── "
_BLANK  = "    "
_CONT   = "│   "


def _node_label(elem: ET.Element, show_annotations: bool) -> str:
    """
    Human-readable label for a single XML element.

    The syntactic tag is always the primary label, directly attached to the
    graph edge.  Any word-level annotations (form, phon, lemma) are appended
    in parentheses when *show_annotations* is True.

    Internal nodes:  TAG
                     TAG  [lemma]               ← embedded compound/MK lemma
    Leaf nodes:      TAG  ( form  phon  [lemma] )
    """
    tag = elem.get("raw_tag") or elem.tag

    form  = elem.get("form")
    phon  = elem.get("phon")
    lemma = elem.get("lemma")

    if form is not None:
        # Leaf node
        if not show_annotations:
            return tag
        parts: list[str] = [form]
        if phon:
            parts.append(phon)
        if lemma:
            parts.append(f"[{lemma}]")
        return f"{tag}  ( {'  '.join(parts)} )"

    # Internal node
    if not show_annotations or not lemma:
        return tag
    return f"{tag}  [{lemma}]"


def _render(
    elem: ET.Element,
    prefix: str,
    is_last: bool,
    lines: list[str],
    show_annotations: bool,
) -> None:
    """Recursively append rendered lines for *elem* and its subtree."""
    connector = _CORNER if is_last else _TEE
    lines.append(prefix + connector + _node_label(elem, show_annotations))

    children = [c for c in elem if c.tag != "comment"]
    if not children:
        return

    child_prefix = prefix + (_BLANK if is_last else _CONT)
    for i, child in enumerate(children):
        _render(child, child_prefix, i == len(children) - 1, lines, show_annotations)


def ascii_tree(
    utt: Utterance,
    *,
    show_comments: bool = True,
    show_annotations: bool = True,
) -> str:
    """
    Render *utt* as an ASCII syntax tree and return the string.

    Parameters
    ----------
    utt:
        The utterance to render.
    show_comments:
        When True (default), emit comment lines (original-script glosses)
        before the tree, prefixed with ``#``.
    show_annotations:
        When True (default), append word-level annotations in parentheses on
        leaf nodes  ``TAG  ( form  phon  [lemma] )``  and embedded lemmas in
        brackets on internal nodes  ``TAG  [lemma]``.
        When False, show only the syntactic tag on every node.

    Layout
    ------
    Line 1:   sentence ID and the ``=N("…")`` header
    Lines 2…: comment lines (only when show_comments=True)
    Remaining: the syntax tree, one node per line

    Example
    -------
    MYS.1.4  =N(" tamakiparu … ")
    # CP-FINAL,IP-SUB,0@玉尅春,*
    └── CP-FINAL
        └── IP-SUB
            └── IP-ADV
                └── PP
                    ├── NP
                    │   └── P-CASE-DAT  ( ni  PHON  [L000519] )
                    └── …
    """
    if utt._block_elem is not None:
        block = utt._block_elem
    else:
        block = _utterance_to_elem(utt)

    sid = block.get("id") or ""
    hdr = block.get("header") or ""
    title = "  ".join(part for part in (sid, hdr) if part)
    lines: list[str] = [title]

    if show_comments:
        for child in block:
            if child.tag == "comment":
                lines.append("# " + (child.get("raw") or ""))

    tree_children = [c for c in block if c.tag != "comment"]
    for i, child in enumerate(tree_children):
        _render(child, "", i == len(tree_children) - 1, lines, show_annotations)

    return "\n".join(lines)


def print_tree(
    utt: Utterance,
    *,
    show_comments: bool = True,
    show_annotations: bool = True,
) -> None:
    """Print the ASCII syntax tree of *utt* to stdout."""
    print(ascii_tree(utt, show_comments=show_comments, show_annotations=show_annotations))
