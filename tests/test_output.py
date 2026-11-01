"""Tests for logscope.output."""

import json
from datetime import datetime

import pytest

from logscope.commands.grep import run_grep
from logscope.commands.summary import compute_summary
from logscope.commands.timeline import compute_timeline
from logscope.output import (
    ReportWriteError,
    stream_grep_json,
    stream_grep_markdown,
    summary_to_dict,
    timeline_to_dict,
    write_summary_json,
    write_summary_markdown,
    write_timeline_json,
    write_timeline_markdown,
)


def write_log(tmp_path, text):
    log_file = tmp_path / "app.log"
    log_file.write_text(text, encoding="utf-8")
    return log_file


class _StringIOLike:
    def __init__(self):
        self.chunks = []

    def write(self, text):
        self.chunks.append(text)

    def getvalue(self):
        return "".join(self.chunks)


def test_summary_json_is_valid_and_has_expected_fields(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 INFO a\n2026-10-01 09:00:01 ERROR boom\n",
    )
    result = compute_summary(log_file)
    stream = _StringIOLike()
    write_summary_json(result, stream)
    payload = json.loads(stream.getvalue())
    assert payload["command"] == "summary"
    assert payload["levels"] == {"INFO": 1, "WARN": 0, "ERROR": 1}
    assert payload["top_errors"] == [{"message": "boom", "count": 1}]
    assert payload["first_timestamp"] == "2026-10-01 09:00:00"
    assert payload["last_timestamp"] == "2026-10-01 09:00:01"
    assert payload["malformed_lines"] == 0


def test_summary_markdown_is_written_with_expected_content(tmp_path):
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")
    result = compute_summary(log_file)
    report_path = tmp_path / "summary.md"
    write_summary_markdown(result, report_path)
    content = report_path.read_text(encoding="utf-8")
    assert "# LogScope Summary Report" in content
    assert "boom" in content
    assert "Malformed lines skipped: 0" in content


def test_summary_markdown_reports_no_errors_found(tmp_path):
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 INFO a\n")
    result = compute_summary(log_file)
    report_path = tmp_path / "summary.md"
    write_summary_markdown(result, report_path)
    content = report_path.read_text(encoding="utf-8")
    assert "No errors were found." in content


def test_timeline_json_includes_chart_and_buckets(tmp_path):
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR a\n")
    result = compute_timeline(log_file, "15m")
    stream = _StringIOLike()
    write_timeline_json(result, stream)
    payload = json.loads(stream.getvalue())
    assert payload["command"] == "timeline"
    assert payload["bucket"] == "15m"
    assert payload["buckets"] == [{"start": "2026-10-01 09:00:00", "count": 1}]
    assert "#" in payload["chart"]
    assert payload["malformed_lines"] == 0


def test_timeline_markdown_contains_chart_block(tmp_path):
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR a\n")
    result = compute_timeline(log_file, "15m")
    report_path = tmp_path / "timeline.md"
    write_timeline_markdown(result, report_path)
    content = report_path.read_text(encoding="utf-8")
    assert "# LogScope Timeline Report" in content
    assert "```" in content


def test_grep_json_streams_matches_and_counts(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 ERROR a\n"
        "2026-10-01 09:00:01 INFO b\n"
        "garbage\n"
        "2026-10-01 09:00:02 ERROR c\n",
    )
    run = run_grep(log_file, level="ERROR")
    stream = _StringIOLike()
    count = stream_grep_json(run, "ERROR", None, stream)
    assert count == 2
    payload = json.loads(stream.getvalue())
    assert payload["command"] == "grep"
    assert payload["level"] == "ERROR"
    assert payload["since"] is None
    assert [m["message"] for m in payload["matches"]] == ["a", "c"]
    assert payload["match_count"] == 2
    assert payload["malformed_lines"] == 1


def test_grep_json_with_no_matches(tmp_path):
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 INFO a\n")
    run = run_grep(log_file, level="ERROR")
    stream = _StringIOLike()
    count = stream_grep_json(run, "ERROR", None, stream)
    assert count == 0
    payload = json.loads(stream.getvalue())
    assert payload["matches"] == []


def test_grep_markdown_report_contains_matching_lines(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 ERROR a\n2026-10-01 09:00:01 INFO b\n",
    )
    run = run_grep(log_file, level="ERROR")
    report_path = tmp_path / "grep.md"
    path, count = stream_grep_markdown(run, "ERROR", None, report_path)
    assert count == 1
    content = report_path.read_text(encoding="utf-8")
    assert "2026-10-01 09:00:00 ERROR a" in content
    assert "Matches found: 1" in content


def test_report_write_error_on_unwritable_path(tmp_path):
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR a\n")
    result = compute_summary(log_file)
    bad_path = tmp_path / "missing-dir" / "summary.md"
    with pytest.raises(ReportWriteError):
        write_summary_markdown(result, bad_path)
