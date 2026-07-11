"""
ANSI escape-code constants and single-character colouring helpers.

Usage
-----
from coj.common.ansi import bold, blue, magenta, yellow

s = bold("NP", colour=True)   # "\033[1mNP\033[0m"  when colour is True
s = bold("NP", colour=False)  # "NP"                 when colour is False
"""

from __future__ import annotations

_BOLD    = "\033[1m"
_BLUE    = "\033[34m"
_MAGENTA = "\033[35m"
_YELLOW  = "\033[33m"
_RESET   = "\033[0m"


def bold(s: str, colour: bool) -> str:
    """Return *s* wrapped in bold ANSI codes when *colour* is True."""
    return f"{_BOLD}{s}{_RESET}" if colour else s


def blue(s: str, colour: bool) -> str:
    """Return *s* in blue when *colour* is True."""
    return f"{_BLUE}{s}{_RESET}" if colour else s


def magenta(s: str, colour: bool) -> str:
    """Return *s* in magenta when *colour* is True."""
    return f"{_MAGENTA}{s}{_RESET}" if colour else s


def yellow(s: str, colour: bool) -> str:
    """Return *s* in yellow when *colour* is True."""
    return f"{_YELLOW}{s}{_RESET}" if colour else s
