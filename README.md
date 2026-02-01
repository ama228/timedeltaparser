# TimedeltaParser

Parse human-readable duration strings into Python `timedelta` objects with fuzzy unit matching, decimal support, and parse metadata.

## Features

- **Flexible Formats** - `"1 hour 30 minutes"`, `"2h30m"`, `".5 days"`
- **Unit Aliases** - `s/sec/secs/seconds`, `m/min/mins/minutes`, etc.
- **Decimal Support** - `"1.5 hours"`, `".5 days"` with fractional cascading
- **Fuzzy Matching** - Configurable tolerance for typos (`"houur"` -> `"hours"`)
- **Direction** - `"in 2 hours"` (positive), `"3 days ago"` (negative), `"-1 week"`
- **Parse Metadata** - Access original text, units found, parse count
- **Strict Mode** - Reject unrecognized tokens
- **Statistics** - Track parse calls and components parsed

## Quick Start

```python
from timedeltaparser import parse_duration

# Basic parsing
d = parse_duration("1 hour 30 minutes")
# timedelta(seconds=5400)

# Decimal support
d = parse_duration(".5 days")
# timedelta(hours=12)

# Compact format
d = parse_duration("2h30m15s")

# Negative / directional
d = parse_duration("3 days ago")     # timedelta(days=-3)
d = parse_duration("in 2 hours")     # timedelta(hours=2)

# Fuzzy matching
d = parse_duration("1 houur", tolerance=0.3)
# timedelta(hours=1)

# Access metadata
d = parse_duration("1h 30m 15s")
print(d.original)      # "1h 30m 15s"
print(d.units_found)   # ["hours", "minutes", "seconds"]
print(d.parse_count)   # 3
```

## Running Tests

```bash
pytest
```
