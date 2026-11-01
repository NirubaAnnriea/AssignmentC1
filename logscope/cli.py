"""Command line interface for LogScope.

Wires argument parsing to the three commands (summary, timeline, grep) and
to the JSON/Markdown output writers, and maps user-facing errors (missing
file, bad arguments, report write failures) to clear stderr messages and a
non-zero exit status.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from logscope.commands.grep import (
    InvalidLevelError,
    InvalidSinceError,
    parse_since,
    run_grep,
    validate_level,
)
from logscope.commands.summary import compute_summary
from logscope.commands.timeline import InvalidBucketError, compute_timeline
from logscope.output import (
    GREP_REPORT_FILENAME,
    ReportWriteError,
    SUMMARY_REPORT_FILENAME,
    TIMELINE_REPORT_FILENAME,
    stream_grep_json,
    stream_grep_markdown,
    write_summary_json,
    write_summary_markdown,
    write_timeline_json,
    write_timeline_markdown,
)

VALID_FORMATS = ("json", "md")


class CliError(Exception):
    """A user-facing error that should be reported on stderr with exit code 1."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logscope",
        description="Analyse application log files after an incident.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser(
        "summary", help="Summarise level counts, top errors and timestamps."
    )
    summary_parser.add_argument("logfile", help="Path to the log file to analyse.")
    summary_parser.add_argument(
        "--format", choices=VALID_FORMATS, default="json", help="Output format."
    )

    timeline_parser = subparsers.add_parser(
        "timeline", help="Show ERROR counts per clock-aligned time bucket."
    )
    timeline_parser.add_argument("logfile", help="Path to the log file to analyse.")
    timeline_parser.add_argument(
        "--bucket",
        required=True,
        help="Bucket duration, e.g. '15m' or '2h'.",
    )
    timeline_parser.add_argument(
        "--format", choices=VALID_FORMATS, default="json", help="Output format."
    )

    grep_parser = subparsers.add_parser(
        "grep", help="Filter log entries by level and/or timestamp."
    )
    grep_parser.add_argument("logfile", help="Path to the log file to analyse.")
    grep_parser.add_argument(
        "--level", help="Filter by level: INFO, WARN or ERROR."
    )
    grep_parser.add_argument(
        "--since", help="Only include entries at/after this timestamp."
    )
    grep_parser.add_argument(
        "--format", choices=VALID_FORMATS, default="json", help="Output format."
    )

    return parser


def _run_summary(args: argparse.Namespace) -> int:
    result = compute_summary(args.logfile)
    if args.format == "json":
        write_summary_json(result)
    else:
        path = write_summary_markdown(result, SUMMARY_REPORT_FILENAME)
        print(f"Summary report written to {path}")
    return 0


def _run_timeline(args: argparse.Namespace) -> int:
    try:
        result = compute_timeline(args.logfile, args.bucket)
    except InvalidBucketError as exc:
        raise CliError(str(exc)) from exc
    if args.format == "json":
        write_timeline_json(result)
    else:
        path = write_timeline_markdown(result, TIMELINE_REPORT_FILENAME)
        print(f"Timeline report written to {path}")
    return 0


def _run_grep(args: argparse.Namespace) -> int:
    level = None
    if args.level is not None:
        try:
            level = validate_level(args.level)
        except InvalidLevelError as exc:
            raise CliError(str(exc)) from exc

    since = None
    if args.since is not None:
        try:
            since = parse_since(args.since)
        except InvalidSinceError as exc:
            raise CliError(str(exc)) from exc

    run = run_grep(args.logfile, level=level, since=since)
    if args.format == "json":
        stream_grep_json(run, level, since)
    else:
        path, match_count = stream_grep_markdown(run, level, since, GREP_REPORT_FILENAME)
        print(f"Grep report written to {path} ({match_count} matches)")
    return 0


_HANDLERS = {
    "summary": _run_summary,
    "timeline": _run_timeline,
    "grep": _run_grep,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = _HANDLERS[args.command]
    try:
        return handler(args)
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ReportWriteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"Error: log file not found: {args.logfile}", file=sys.stderr)
        return 1
    except IsADirectoryError:
        print(f"Error: expected a file but found a directory: {args.logfile}", file=sys.stderr)
        return 1
    except PermissionError:
        print(f"Error: permission denied reading: {args.logfile}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: could not read '{args.logfile}': {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
