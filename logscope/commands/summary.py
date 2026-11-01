"""The ``summary`` command: counts levels, ranks top errors, finds the
first/last timestamps - all computed in a single streaming pass over the
file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from logscope.parser import LogParser

TOP_ERROR_LIMIT = 5


@dataclass(frozen=True)
class ErrorFrequency:
    message: str
    count: int


@dataclass
class SummaryResult:
    info_count: int = 0
    warn_count: int = 0
    error_count: int = 0
    top_errors: List[ErrorFrequency] = field(default_factory=list)
    first_timestamp: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None
    malformed_lines: int = 0


def compute_summary(path: Union[str, Path]) -> SummaryResult:
    """Stream the log file once and compute summary statistics.

    Only bounded data is kept in memory: three level counters, a dict of
    distinct ERROR messages (far smaller than the number of log lines in
    practice) and two timestamps. The raw lines themselves are never stored.
    """
    parser = LogParser()
    level_counts: Dict[str, int] = {"INFO": 0, "WARN": 0, "ERROR": 0}
    error_message_counts: Dict[str, int] = {}
    first_timestamp: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None

    for entry in parser.parse_file(path):
        level_counts[entry.level] += 1
        if entry.level == "ERROR":
            error_message_counts[entry.message] = (
                error_message_counts.get(entry.message, 0) + 1
            )
        if first_timestamp is None:
            first_timestamp = entry.timestamp
        last_timestamp = entry.timestamp

    ranked = sorted(
        error_message_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[:TOP_ERROR_LIMIT]
    top_errors = [ErrorFrequency(message=msg, count=count) for msg, count in ranked]

    return SummaryResult(
        info_count=level_counts["INFO"],
        warn_count=level_counts["WARN"],
        error_count=level_counts["ERROR"],
        top_errors=top_errors,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
        malformed_lines=parser.malformed_count,
    )
