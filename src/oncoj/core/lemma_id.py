"""LemmaID — immutable value type for lemma identifiers, plus IDGenerator."""

from __future__ import annotations
import re

# Matches any valid lemma ID: one or more letters, digits, optional letter suffix
# e.g. L000006a, N000001, T050877, F000052
_LEMMA_RE = re.compile(r'^([A-Za-z]+)(\d+)([a-z]*)$')


class LemmaID:
    """
    Immutable value type representing a lemma identifier such as ``L000006a``.

    Attributes
    ----------
    prefix  : str   — letter prefix, e.g. "L", "N", "T", "F"
    number  : int   — numeric part as an integer
    suffix  : str   — optional lower-case letter suffix, e.g. "a", "b", ""
    digits  : int   — zero-padding width used for serialisation (default 6)
    """

    __slots__ = ("prefix", "number", "suffix", "digits")

    def __init__(self, prefix: str, number: int,
                 suffix: str = "", digits: int = 6) -> None:
        if not prefix.isalpha():
            raise ValueError(f"LemmaID prefix must be alphabetic, got {prefix!r}")
        if number < 0:
            raise ValueError(f"LemmaID number must be non-negative, got {number}")
        if suffix and not suffix.islower():
            raise ValueError(f"LemmaID suffix must be lower-case, got {suffix!r}")
        object.__setattr__(self, "prefix", prefix)
        object.__setattr__(self, "number", number)
        object.__setattr__(self, "suffix", suffix)
        object.__setattr__(self, "digits", digits)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("LemmaID is immutable")

    # ── parsing ───────────────────────────────────────────────────────────────

    @classmethod
    def parse(cls, text: str, digits: int = 6) -> "LemmaID":
        """
        Parse a string such as ``"L000006a"`` into a LemmaID.
        Raises ``ValueError`` if the format does not match.
        """
        m = _LEMMA_RE.match(text.strip())
        if not m:
            raise ValueError(f"Not a valid lemma ID: {text!r}")
        return cls(m.group(1), int(m.group(2)), m.group(3),
                   digits=max(digits, len(m.group(2))))

    @classmethod
    def is_valid(cls, text: str) -> bool:
        return bool(_LEMMA_RE.match(text.strip()))

    # ── serialisation ─────────────────────────────────────────────────────────

    def __str__(self) -> str:
        return f"{self.prefix}{self.number:0{self.digits}d}{self.suffix}"

    def __repr__(self) -> str:
        return f"LemmaID({str(self)!r})"

    # ── comparison / hashing (by canonical string) ────────────────────────────

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LemmaID):
            return str(self) == str(other)
        if isinstance(other, str):
            return str(self) == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(str(self))

    def __lt__(self, other: "LemmaID") -> bool:
        return (self.number, self.suffix, self.prefix) < (other.number, other.suffix, other.prefix)

    def __le__(self, other: "LemmaID") -> bool:
        return self == other or self < other

    # ── convenience ───────────────────────────────────────────────────────────

    def with_prefix(self, prefix: str) -> "LemmaID":
        """Return a new LemmaID with a different prefix, same number/suffix."""
        return LemmaID(prefix, self.number, self.suffix, self.digits)


class IDGenerator:
    """
    Produces unique lemma IDs that never clash with a pre-existing set.

    Parameters
    ----------
    existing  : iterable of int or LemmaID  — numeric parts already in use
    start     : int   — minimum value for generated IDs (default 1)
    prefix    : str   — default prefix for generated IDs (default "L")
    digits    : int   — zero-padding width (default 6)
    """

    def __init__(self, existing: "set[int] | set[LemmaID] | set" = frozenset(),
                 start: int = 1,
                 prefix: str = "L",
                 digits: int = 6) -> None:
        self._used: set[int] = set()
        for item in existing:
            if isinstance(item, LemmaID):
                self._used.add(item.number)
            else:
                self._used.add(int(item))
        self._next = max(start, 1)
        self.prefix = prefix
        self.digits = digits

    def reserve(self, number: int) -> None:
        """Mark *number* as taken so it will never be issued."""
        self._used.add(number)

    def next_id(self, prefix: str | None = None) -> LemmaID:
        """Return the next available LemmaID, advancing the internal counter."""
        while self._next in self._used:
            self._next += 1
        n = self._next
        self._used.add(n)
        self._next += 1
        return LemmaID(prefix or self.prefix, n, digits=self.digits)

    def peek_next_number(self) -> int:
        """Return what the next numeric value would be without consuming it."""
        n = self._next
        while n in self._used:
            n += 1
        return n
