"""Streaming parser for LogScope's log file format.

Expected line format::

    YYYY-MM-DD HH:MM:SS LEVEL Message text

Where LEVEL is one of INFO, WARN or ERROR. Lines that do not match this
format, or whose timestamp is not a real calendar date/time, are counted as
malformed and skipped. The parser never loads the whole file into memory: it
reads and yields one line at a time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Union

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
VALID_LEVELS = ("INFO", "WARN", "ERROR")

_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s"
    r"(?P<level>INFO|WARN|ERROR)\s"
    r"(?P<message>.+)$"
)


@dataclass(frozen=True)
class LogEntry:
    """A single successfully-parsed log line."""

    timestamp: datetime
    level: str
    message: str
    raw: str


class LogParser:
    """Parses a log file line by line, tracking malformed lines as it goes.

    Usage::

        parser = LogParser()
        for entry in parser.parse_file(path):
            ...
        malformed = parser.malformed_count
    """

    def __init__(self) -> None:
        self.malformed_count = 0

    def parse_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single raw line (including its trailing newline, if any).

        Returns a ``LogEntry`` for a valid line, or ``None`` for a blank line
        or a malformed line (malformed lines increment ``malformed_count``).
        """
        stripped = line.rstrip("\r\n")
        if not stripped.strip():
            # Blank lines carry no data; they are ignored, not "malformed".
            return None

        match = _LINE_PATTERN.match(stripped)
        if not match:
            self.malformed_count += 1
            return None

        message = match.group("message").strip()
        if not message:
            self.malformed_count += 1
            return None

        try:
            timestamp = datetime.strptime(match.group("timestamp"), TIMESTAMP_FORMAT)
        except ValueError:
            self.malformed_count += 1
            return None

        return LogEntry(
            timestamp=timestamp,
            level=match.group("level"),
            message=message,
            raw=stripped,
        )

    def parse_file(self, path: Union[str, Path]) -> Iterator[LogEntry]:
        """Stream-parse a log file, yielding one ``LogEntry`` per valid line."""
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                entry = self.parse_line(line)
                if entry is not None:
                    yield entry
