"""
ASCII syntax-tree renderer for ONCOJ utterances.

Public API
----------
ascii_tree(utt, *, show_comments=True, show_annotations=True, colour=False)  → str
print_tree(utt, *, show_comments=True, show_annotations=True, colour=None)
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

from oncoj.common.ansi import bold as _b, blue as _bl, magenta as _mg, yellow as _yl
from oncoj.core.corpus import Utterance, _utterance_to_elem

# Box-drawing characters
_TEE    = "├── "
_CORNER = "└── "
_BLANK  = "    "
_CONT   = "│   "


def _node_label(elem: ET.Element, show_annotations: bool, colour: bool) -> str:
    """
    Human-readable label for a single XML element.

    The syntactic tag is always the primary label, directly attached to the
    graph edge.  Any word-level annotations (form, phon, lemma) are appended
    in parentheses when *show_annotations* is True.

    Internal nodes:  TAG
                     TAG  ( [lemma] … )         ← annotations in parens, same as leaves
    Leaf nodes:      TAG  ( form  phon  [lemma] )
    """
    tag = elem.get("raw_tag") or elem.tag

    form  = elem.get("form")
    phon  = elem.get("phon")
    lemma = elem.get("lemma")

    if form is not None:
        # Leaf node
        if not show_annotations:
            return _b(tag, colour)
        parts: list[str] = [_bl(form, colour)]
        if phon:
            parts.append(_mg(phon, colour))
        if lemma:
            parts.append(_yl(f"[{lemma}]", colour))
        return f"{_b(tag, colour)}  ( {'  '.join(parts)} )"

    # Internal node
    if not show_annotations:
        return _b(tag, colour)
    parts = []
    if lemma:
        parts.append(_yl(f"[{lemma}]", colour))
    if not parts:
        return _b(tag, colour)
    return f"{_b(tag, colour)}  ( {'  '.join(parts)} )"


def _render(
    elem: ET.Element,
    prefix: str,
    is_last: bool,
    lines: list[str],
    show_annotations: bool,
    colour: bool,
) -> None:
    """Recursively append rendered lines for *elem* and its subtree."""
    connector = _CORNER if is_last else _TEE
    lines.append(prefix + connector + _node_label(elem, show_annotations, colour))

    children = [c for c in elem if c.tag != "comment"]
    if not children:
        return

    child_prefix = prefix + (_BLANK if is_last else _CONT)
    for i, child in enumerate(children):
        _render(child, child_prefix, i == len(children) - 1, lines, show_annotations, colour)


def ascii_tree(
    utt: Utterance,
    *,
    show_comments: bool = True,
    show_annotations: bool = True,
    colour: bool = False,
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
        all nodes: ``TAG  ( form  phon  [lemma] )`` for leaves,
        ``TAG  ( [lemma] )`` for internal compound/MK nodes.
        When False, show only the syntactic tag on every node.
    colour:
        When True, apply ANSI colour: tags bold, word forms blue, phon/script
        tags magenta, lemma IDs yellow.  Defaults to False so that captured
        strings remain plain text.  Use ``print_tree`` with ``colour=None``
        for automatic TTY detection.

    Layout
    ------
    Line 1:   sentence ID (bold when colour=True) and header word list
    Lines 2…: comment lines (only when show_comments=True)
    Remaining: the syntax tree, one node per line
    """
    if utt._block_elem is not None:
        block = utt._block_elem
    else:
        block = _utterance_to_elem(utt)

    sid = block.get("id") or ""
    hdr = block.get("header") or ""
    title = "  ".join(part for part in (_b(sid, colour), hdr) if part)
    lines: list[str] = [title]

    if show_comments:
        for child in block:
            if child.tag == "comment":
                lines.append("# " + (child.get("raw") or ""))

    tree_children = [c for c in block if c.tag != "comment"]
    for i, child in enumerate(tree_children):
        _render(child, "", i == len(tree_children) - 1, lines, show_annotations, colour)

    return "\n".join(lines)


def print_tree(
    utt: Utterance,
    *,
    show_comments: bool = True,
    show_annotations: bool = True,
    colour: "bool | None" = None,
) -> None:
    """
    Print the ASCII syntax tree of *utt* to stdout.

    *colour* defaults to None, which enables ANSI colour automatically when
    stdout is a TTY.  Pass True to force colour on, False to force it off.
    """
    resolved: bool = sys.stdout.isatty() if colour is None else colour
    print(ascii_tree(utt, show_comments=show_comments,
                     show_annotations=show_annotations, colour=resolved))
