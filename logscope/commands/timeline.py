"""The ``timeline`` command: counts ERROR entries into clock-aligned time
buckets and renders them as a text bar chart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Union

from logscope.parser import LogParser

#: Maximum number of '#' characters a single bar may use. Larger counts are
#: scaled down (see ``compute_timeline``/``render_bar_chart``) so the chart
#: never floods the terminal regardless of how many errors a bucket holds.
MAX_BAR_WIDTH = 50

_BUCKET_PATTERN = re.compile(r"^(?P<value>[1-9]\d*)(?P<unit>[mh])$")


class InvalidBucketError(ValueError):
    """Raised when the --bucket value is not a positive integer + m/h."""


def parse_bucket_duration(text: str) -> timedelta:
    """Parse a bucket duration such as ``"15m"`` or ``"2h"``."""
    match = _BUCKET_PATTERN.match(text.strip())
    if not match:
        raise InvalidBucketError(
            f"Invalid bucket duration '{text}'. Expected a positive integer "
            "followed by 'm' (minutes) or 'h' (hours), e.g. '15m' or '2h'."
        )
    value = int(match.group("value"))
    unit = match.group("unit")
    return timedelta(minutes=value) if unit == "m" else timedelta(hours=value)


def _bucket_start(timestamp: datetime, bucket: timedelta) -> datetime:
    """Return the clock-aligned start of the bucket containing ``timestamp``.

    Alignment is computed from midnight of the timestamp's own day, so a
    15-minute bucket always starts at :00, :15, :30 or :45 - never at an
    offset derived from the first log entry seen.
    """
    midnight = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    bucket_seconds = int(bucket.total_seconds())
    elapsed_seconds = int((timestamp - midnight).total_seconds())
    index = elapsed_seconds // bucket_seconds
    return midnight + timedelta(seconds=index * bucket_seconds)


@dataclass(frozen=True)
class TimelineBucket:
    start: datetime
    count: int


@dataclass
class TimelineResult:
    bucket_label: str
    buckets: List[TimelineBucket] = field(default_factory=list)
    malformed_lines: int = 0
    scale: int = 1


def compute_timeline(path: Union[str, Path], bucket_label: str) -> TimelineResult:
    """Stream the file once, counting ERROR entries per clock-aligned bucket.

    Only one counter per *distinct* bucket that actually contains an error is
    kept in memory - bounded by the number of error buckets, not by the
    number of lines in the file.
    """
    bucket = parse_bucket_duration(bucket_label)
    parser = LogParser()
    counts: Dict[datetime, int] = {}

    for entry in parser.parse_file(path):
        if entry.level != "ERROR":
            continue
        start = _bucket_start(entry.timestamp, bucket)
        counts[start] = counts.get(start, 0) + 1

    max_count = max(counts.values(), default=0)
    scale = 1
    if max_count > MAX_BAR_WIDTH:
        scale = -(-max_count // MAX_BAR_WIDTH)  # ceil division, no float drift

    buckets = [
        TimelineBucket(start=start, count=counts[start]) for start in sorted(counts)
    ]

    return TimelineResult(
        bucket_label=bucket_label,
        buckets=buckets,
        malformed_lines=parser.malformed_count,
        scale=scale,
    )


def render_bar_chart(result: TimelineResult) -> str:
    """Render the bucket counts as a plain-text bar chart.

    Each ``#`` represents ``result.scale`` errors. ``scale`` is 1 unless the
    busiest bucket's count exceeds :data:`MAX_BAR_WIDTH`, in which case all
    bars are scaled down proportionally and the scale factor is documented
    on the first line of the chart.
    """
    if not result.buckets:
        return "No errors found."

    lines: List[str] = []
    if result.scale > 1:
        lines.append(f"(each '#' represents {result.scale} errors)")
    for bucket in result.buckets:
        bar_length = max(1, round(bucket.count / result.scale))
        label = bucket.start.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{label} | {'#' * bar_length} ({bucket.count})")
    return "\n".join(lines)
