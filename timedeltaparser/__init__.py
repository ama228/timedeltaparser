"""TimedeltaParser - Parse human-readable duration strings into timedelta objects."""

from .parser import parse_duration, ParseError, ParsedDuration

__version__ = "0.1.0"
__all__ = ["parse_duration", "ParseError", "ParsedDuration"]
