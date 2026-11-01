"""The ``grep`` command: streams log entries matching an optional level
and/or an optional ``--since`` timestamp, preserving original file order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Union

from logscope.parser import VALID_LEVELS, LogEntry, LogParser

_SINCE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")


class InvalidSinceError(ValueError):
    """Raised when --since cannot be parsed as a timestamp."""


class InvalidLevelError(ValueError):
    """Raised when --level is not one of INFO, WARN or ERROR."""


def parse_since(text: str) -> datetime:
    """Parse a ``--since`` value, accepting either second or minute precision."""
    candidate = text.strip()
    for fmt in _SINCE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    raise InvalidSinceError(
        f"Invalid --since timestamp '{text}'. Expected 'YYYY-MM-DD HH:MM' "
        "or 'YYYY-MM-DD HH:MM:SS'."
    )


def validate_level(level: str) -> str:
    """Normalise and validate a ``--level`` value."""
    normalized = level.strip().upper()
    if normalized not in VALID_LEVELS:
        raise InvalidLevelError(
            f"Invalid --level '{level}'. Expected one of {', '.join(VALID_LEVELS)}."
        )
    return normalized


@dataclass
class GrepRun:
    """Pairs the parser with the lazy match generator.

    ``parser.malformed_count`` only reflects the final total once
    ``matches`` has been fully iterated, since both are driven by the same
    single pass over the file.
    """

    parser: LogParser
    matches: Iterator[LogEntry]


def run_grep(
    path: Union[str, Path],
    level: Optional[str] = None,
    since: Optional[datetime] = None,
) -> GrepRun:
    """Stream matching entries from ``path`` in their original file order.

    Nothing is buffered beyond the entry currently being examined: matches
    are produced lazily so callers can stream them straight to the chosen
    output instead of collecting them all in a list first.
    """
    parser = LogParser()

    def _iter_matches() -> Iterator[LogEntry]:
        for entry in parser.parse_file(path):
            if level is not None and entry.level != level:
                continue
            if since is not None and entry.timestamp < since:
                continue
            yield entry

    return GrepRun(parser=parser, matches=_iter_matches())
