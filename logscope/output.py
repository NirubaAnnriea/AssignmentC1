"""Output formatting for LogScope: JSON written to stdout and Markdown
reports written to files.

JSON schemas (documented here, exercised by tests/test_output.py)::

    summary -> {
        "command": "summary",
        "levels": {"INFO": int, "WARN": int, "ERROR": int},
        "top_errors": [{"message": str, "count": int}, ...],   # up to 5
        "first_timestamp": "YYYY-MM-DD HH:MM:SS" | null,
        "last_timestamp": "YYYY-MM-DD HH:MM:SS" | null,
        "malformed_lines": int
    }

    timeline -> {
        "command": "timeline",
        "bucket": "15m",
        "scale": int,                 # errors represented by each '#'
        "buckets": [{"start": "YYYY-MM-DD HH:MM:SS", "count": int}, ...],
        "chart": "text bar chart as a single string",
        "malformed_lines": int
    }

    grep -> {
        "command": "grep",
        "level": "ERROR" | null,
        "since": "YYYY-MM-DD HH:MM:SS" | null,
        "matches": [
            {"timestamp": "...", "level": "...", "message": "...", "line": "raw text"},
            ...
        ],
        "match_count": int,
        "malformed_lines": int
    }

Markdown reports mirror the same information in a human-readable layout and
are written to predictable filenames in the current working directory.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import IO, Optional, Union

from logscope.commands.grep import GrepRun
from logscope.commands.summary import SummaryResult
from logscope.commands.timeline import TimelineResult, render_bar_chart

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

SUMMARY_REPORT_FILENAME = "logscope-summary-report.md"
TIMELINE_REPORT_FILENAME = "logscope-timeline-report.md"
GREP_REPORT_FILENAME = "logscope-grep-report.md"


class ReportWriteError(Exception):
    """Raised when a Markdown report could not be written to disk."""


def format_timestamp(value: Optional[datetime]) -> Optional[str]:
    return value.strftime(TIMESTAMP_FORMAT) if value is not None else None


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------


def summary_to_dict(result: SummaryResult) -> dict:
    return {
        "command": "summary",
        "levels": {
            "INFO": result.info_count,
            "WARN": result.warn_count,
            "ERROR": result.error_count,
        },
        "top_errors": [
            {"message": e.message, "count": e.count} for e in result.top_errors
        ],
        "first_timestamp": format_timestamp(result.first_timestamp),
        "last_timestamp": format_timestamp(result.last_timestamp),
        "malformed_lines": result.malformed_lines,
    }


def write_summary_json(result: SummaryResult, stream: Optional[IO[str]] = None) -> None:
    stream = stream or sys.stdout
    stream.write(json.dumps(summary_to_dict(result)))
    stream.write("\n")


def write_summary_markdown(
    result: SummaryResult, file_path: Union[str, Path] = SUMMARY_REPORT_FILENAME
) -> Path:
    lines = ["# LogScope Summary Report", ""]
    lines.append(f"- INFO entries: {result.info_count}")
    lines.append(f"- WARN entries: {result.warn_count}")
    lines.append(f"- ERROR entries: {result.error_count}")
    lines.append(
        f"- First timestamp: {format_timestamp(result.first_timestamp) or 'N/A'}"
    )
    lines.append(
        f"- Last timestamp: {format_timestamp(result.last_timestamp) or 'N/A'}"
    )
    lines.append(f"- Malformed lines skipped: {result.malformed_lines}")
    lines.append("")
    lines.append("## Top ERROR Messages")
    lines.append("")
    if not result.top_errors:
        lines.append("No errors were found.")
    else:
        lines.append("| Rank | Message | Count |")
        lines.append("|---|---|---|")
        for rank, error in enumerate(result.top_errors, start=1):
            lines.append(f"| {rank} | {error.message} | {error.count} |")
    lines.append("")
    return _write_text_report(file_path, "\n".join(lines))


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------


def timeline_to_dict(result: TimelineResult) -> dict:
    return {
        "command": "timeline",
        "bucket": result.bucket_label,
        "scale": result.scale,
        "buckets": [
            {"start": format_timestamp(b.start), "count": b.count}
            for b in result.buckets
        ],
        "chart": render_bar_chart(result),
        "malformed_lines": result.malformed_lines,
    }


def write_timeline_json(result: TimelineResult, stream: Optional[IO[str]] = None) -> None:
    stream = stream or sys.stdout
    stream.write(json.dumps(timeline_to_dict(result)))
    stream.write("\n")


def write_timeline_markdown(
    result: TimelineResult, file_path: Union[str, Path] = TIMELINE_REPORT_FILENAME
) -> Path:
    lines = ["# LogScope Timeline Report", ""]
    lines.append(f"- Bucket size: {result.bucket_label}")
    lines.append(f"- Malformed lines skipped: {result.malformed_lines}")
    lines.append("")
    lines.append("## Error Chart")
    lines.append("")
    lines.append("```")
    lines.append(render_bar_chart(result))
    lines.append("```")
    lines.append("")
    return _write_text_report(file_path, "\n".join(lines))


# --------------------------------------------------------------------------
# Grep (streamed: matches are never fully buffered in memory)
# --------------------------------------------------------------------------


def stream_grep_json(
    run: GrepRun,
    level: Optional[str],
    since: Optional[datetime],
    stream: Optional[IO[str]] = None,
) -> int:
    """Write the grep result as JSON, one match at a time.

    Returns the number of matches written. Only one match is held in memory
    at any time; the full list of matches is never materialised.
    """
    stream = stream or sys.stdout
    stream.write("{")
    stream.write(f'"command": {json.dumps("grep")}, ')
    stream.write(f'"level": {json.dumps(level)}, ')
    stream.write(f'"since": {json.dumps(format_timestamp(since))}, ')
    stream.write('"matches": [')
    match_count = 0
    for entry in run.matches:
        if match_count:
            stream.write(", ")
        stream.write(
            json.dumps(
                {
                    "timestamp": format_timestamp(entry.timestamp),
                    "level": entry.level,
                    "message": entry.message,
                    "line": entry.raw,
                }
            )
        )
        match_count += 1
    stream.write("], ")
    stream.write(f'"match_count": {match_count}, ')
    stream.write(f'"malformed_lines": {run.parser.malformed_count}')
    stream.write("}\n")
    return match_count


def stream_grep_markdown(
    run: GrepRun,
    level: Optional[str],
    since: Optional[datetime],
    file_path: Union[str, Path] = GREP_REPORT_FILENAME,
) -> tuple[Path, int]:
    """Write the grep result as a Markdown report, one line at a time.

    Matching lines are written to disk as they are produced, so the full
    match set is never held in memory - only the line currently being
    written. The report file itself can still grow large on disk if there
    are many matches; that disk-space cost is unavoidable for a saved
    report and is documented in the README.
    """
    path = Path(file_path)
    try:
        handle = open(path, "w", encoding="utf-8")
    except OSError as exc:
        raise ReportWriteError(f"Could not open report file '{path}': {exc}") from exc

    match_count = 0
    try:
        with handle:
            handle.write("# LogScope Grep Report\n\n")
            handle.write(f"- Level filter: {level or 'any'}\n")
            handle.write(f"- Since: {format_timestamp(since) or 'any'}\n\n")
            handle.write("## Matching Lines\n\n")
            handle.write("```\n")
            for entry in run.matches:
                handle.write(entry.raw + "\n")
                match_count += 1
            handle.write("```\n\n")
            handle.write(f"- Matches found: {match_count}\n")
            handle.write(f"- Malformed lines skipped: {run.parser.malformed_count}\n")
    except OSError as exc:
        raise ReportWriteError(f"Error while writing report file '{path}': {exc}") from exc
    return path, match_count


def _write_text_report(file_path: Union[str, Path], content: str) -> Path:
    path = Path(file_path)
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ReportWriteError(f"Could not write report file '{path}': {exc}") from exc
    return path
