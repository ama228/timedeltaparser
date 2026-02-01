"""Parse human-readable duration strings into timedelta objects.

Supports formats like:
    "1 hour 30 minutes"
    "2h 30m"
    ".5 days"
    "-3 weeks"
    "in 2 hours"
    "1.5 hours ago"
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any


class ParseError(Exception):
    """Raised when a duration string cannot be parsed.

    Attributes:
        position: Character index where the error was detected.
        reason: Short machine-readable description.
        text: The original input text.
    """

    def __init__(self, message: str, position: int = -1, reason: str = "", text: str = ""):
        super().__init__(message)
        self.position = position
        self.reason = reason
        self.text = text


class ParsedDuration(timedelta):
    """A timedelta with parse metadata attached.

    Attributes:
        original: The original input string.
        units_found: List of unit names found during parsing.
        is_negative: Whether the duration is negative.
        parse_count: How many components were parsed.
    """

    def __new__(
        cls,
        *args: Any,
        original: str = "",
        units_found: list[str] | None = None,
        is_negative: bool = False,
        parse_count: int = 0,
        **kwargs: Any,
    ) -> ParsedDuration:
        instance = super().__new__(cls, *args, **kwargs)
        instance.original = original  # type: ignore[attr-defined]
        instance.units_found = units_found or []  # type: ignore[attr-defined]
        instance.is_negative = is_negative  # type: ignore[attr-defined]
        instance.parse_count = parse_count  # type: ignore[attr-defined]
        return instance


# ── Unit aliases ───────────────────────────────────────────────────────────

_UNIT_MAP: dict[str, str] = {}

_UNIT_ALIASES = {
    "microseconds": ["microsecond", "microseconds", "us", "usec", "usecs"],
    "milliseconds": ["millisecond", "milliseconds", "ms", "msec", "msecs"],
    "seconds": ["second", "seconds", "sec", "secs", "s"],
    "minutes": ["minute", "minutes", "min", "mins", "m"],
    "hours": ["hour", "hours", "hr", "hrs", "h"],
    "days": ["day", "days", "d"],
    "weeks": ["week", "weeks", "wk", "wks", "w"],
}

for canonical, aliases in _UNIT_ALIASES.items():
    for alias in aliases:
        _UNIT_MAP[alias] = canonical

# Conversion factors to microseconds
_TO_MICROSECONDS: dict[str, float] = {
    "microseconds": 1,
    "milliseconds": 1_000,
    "seconds": 1_000_000,
    "minutes": 60_000_000,
    "hours": 3_600_000_000,
    "days": 86_400_000_000,
    "weeks": 604_800_000_000,
}

# ── Fuzzy matching ─────────────────────────────────────────────────────────


def _levenshtein(s1: str, s2: str) -> int:
    """Simple Levenshtein distance."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr_row.append(min(
                curr_row[j] + 1,
                prev_row[j + 1] + 1,
                prev_row[j] + cost,
            ))
        prev_row = curr_row
    return prev_row[-1]


def _fuzzy_match_unit(token: str, tolerance: float) -> str | None:
    """Match a token to a unit name with fuzzy matching."""
    token_lower = token.lower()

    # Exact match first
    if token_lower in _UNIT_MAP:
        return _UNIT_MAP[token_lower]

    if tolerance <= 0:
        return None

    # Fuzzy match
    best_match: str | None = None
    best_distance = float("inf")

    for alias in _UNIT_MAP:
        max_dist = max(1, int(len(alias) * tolerance))
        dist = _levenshtein(token_lower, alias)
        if dist <= max_dist and dist < best_distance:
            best_distance = dist
            best_match = _UNIT_MAP[alias]

    return best_match


# ── Tokenizer ──────────────────────────────────────────────────────────────

_COMPONENT_RE = re.compile(
    r"(?P<number>-?\.?\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z]+)",
)


# ── Statistics ─────────────────────────────────────────────────────────────

duration_parse_stats: dict[str, int] = {}


def get_stats() -> dict[str, int]:
    return dict(duration_parse_stats)


def reset_stats() -> None:
    duration_parse_stats.clear()


# ── Public API ─────────────────────────────────────────────────────────────


def parse_duration(
    text: str,
    *,
    tolerance: float = 0.0,
    strict: bool = False,
) -> ParsedDuration:
    """Parse a human-readable duration string.

    Parameters
    ----------
    text:
        Duration string like ``"1 hour 30 minutes"`` or ``"2h30m"``.
    tolerance:
        Fuzzy matching tolerance (0.0 to 1.0).
        ``0.0`` requires exact unit names.
        ``0.3`` allows minor typos.
    strict:
        When ``True``, raise on any unrecognized tokens.

    Returns
    -------
    A :class:`ParsedDuration` (subclass of ``timedelta``) with metadata.

    Raises
    ------
    ParseError
        If the string cannot be parsed.

    Examples
    --------
    >>> parse_duration("1 hour 30 minutes")
    ParsedDuration(seconds=5400)

    >>> parse_duration("2.5 days")
    ParsedDuration(days=2, seconds=43200)

    >>> parse_duration(".5 hours")
    ParsedDuration(seconds=1800)

    >>> parse_duration("-3 weeks")
    ParsedDuration(days=-21)
    """
    if tolerance < 0 or tolerance > 1:
        raise ParseError(
            "tolerance must be between 0.0 and 1.0",
            reason="invalid_tolerance",
            text=text,
        )

    duration_parse_stats["total_calls"] = duration_parse_stats.get("total_calls", 0) + 1

    # Strip "in" prefix and "ago" suffix
    cleaned = text.strip()
    is_negative = False

    if cleaned.lower().startswith("in "):
        cleaned = cleaned[3:]
    if cleaned.lower().endswith(" ago"):
        cleaned = cleaned[:-4]
        is_negative = True

    # Check for leading negative sign
    if cleaned.startswith("-"):
        is_negative = not is_negative
        cleaned = cleaned[1:].strip()

    matches = list(_COMPONENT_RE.finditer(cleaned))

    if not matches:
        raise ParseError(
            f"No duration components found in: {text!r}",
            position=0,
            reason="no_components",
            text=text,
        )

    total_microseconds = 0.0
    units_found: list[str] = []
    parse_count = 0

    for match in matches:
        number_str = match.group("number")
        unit_str = match.group("unit")
        pos = match.start()

        # Parse number (supports .5 without leading zero)
        try:
            number = float(number_str)
        except ValueError:
            raise ParseError(
                f"Invalid number: {number_str!r}",
                position=pos,
                reason="invalid_number",
                text=text,
            )

        # Match unit
        canonical = _fuzzy_match_unit(unit_str, tolerance)
        if canonical is None:
            if strict:
                raise ParseError(
                    f"Unknown unit: {unit_str!r}",
                    position=match.start("unit"),
                    reason="unknown_unit",
                    text=text,
                )
            duration_parse_stats["unknown_units"] = duration_parse_stats.get("unknown_units", 0) + 1
            continue

        # Cascade fractional values to microseconds
        total_microseconds += number * _TO_MICROSECONDS[canonical]
        units_found.append(canonical)
        parse_count += 1

    if parse_count == 0:
        raise ParseError(
            f"No recognized units in: {text!r}",
            position=0,
            reason="no_units",
            text=text,
        )

    # Round to nearest microsecond (round-half-up)
    total_microseconds = int(total_microseconds + 0.5)

    if is_negative:
        total_microseconds = -total_microseconds

    duration_parse_stats["components_parsed"] = (
        duration_parse_stats.get("components_parsed", 0) + parse_count
    )

    return ParsedDuration(
        microseconds=total_microseconds,
        original=text,
        units_found=units_found,
        is_negative=is_negative,
        parse_count=parse_count,
    )
