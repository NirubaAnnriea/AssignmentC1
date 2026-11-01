"""Tests for logscope.commands.grep."""

from datetime import datetime

import pytest

from logscope.commands.grep import (
    InvalidLevelError,
    InvalidSinceError,
    parse_since,
    run_grep,
    validate_level,
)


def write_log(tmp_path, text):
    log_file = tmp_path / "app.log"
    log_file.write_text(text, encoding="utf-8")
    return log_file


SAMPLE = (
    "2026-10-01 08:59:00 INFO before window\n"
    "2026-10-01 09:00:00 ERROR first error\n"
    "2026-10-01 09:05:00 WARN a warning\n"
    "2026-10-01 09:10:00 ERROR second error\n"
    "garbage line\n"
    "2026-10-01 09:15:00 INFO all done\n"
)


def test_parse_since_minute_precision():
    assert parse_since("2026-10-01 09:00") == datetime(2026, 10, 1, 9, 0, 0)


def test_parse_since_second_precision():
    assert parse_since("2026-10-01 09:00:30") == datetime(2026, 10, 1, 9, 0, 30)


def test_parse_since_rejects_garbage():
    with pytest.raises(InvalidSinceError):
        parse_since("not-a-date")


def test_validate_level_accepts_known_levels():
    assert validate_level("error") == "ERROR"
    assert validate_level("WARN") == "WARN"


def test_validate_level_rejects_unknown_level():
    with pytest.raises(InvalidLevelError):
        validate_level("DEBUG")


def test_filters_by_level(tmp_path):
    log_file = write_log(tmp_path, SAMPLE)
    run = run_grep(log_file, level="ERROR")
    messages = [e.message for e in run.matches]
    assert messages == ["first error", "second error"]
    assert run.parser.malformed_count == 1


def test_filters_by_since_inclusive(tmp_path):
    log_file = write_log(tmp_path, SAMPLE)
    run = run_grep(log_file, since=datetime(2026, 10, 1, 9, 10, 0))
    messages = [e.message for e in run.matches]
    assert messages == ["second error", "all done"]


def test_filters_by_level_and_since_together(tmp_path):
    log_file = write_log(tmp_path, SAMPLE)
    run = run_grep(
        log_file, level="ERROR", since=datetime(2026, 10, 1, 9, 10, 0)
    )
    messages = [e.message for e in run.matches]
    assert messages == ["second error"]


def test_no_filters_returns_all_valid_entries_in_order(tmp_path):
    log_file = write_log(tmp_path, SAMPLE)
    run = run_grep(log_file)
    messages = [e.message for e in run.matches]
    assert messages == [
        "before window",
        "first error",
        "a warning",
        "second error",
        "all done",
    ]


def test_no_matches_returns_empty(tmp_path):
    log_file = write_log(tmp_path, SAMPLE)
    run = run_grep(log_file, since=datetime(2030, 1, 1, 0, 0, 0))
    assert list(run.matches) == []


def test_empty_file_returns_no_matches(tmp_path):
    log_file = write_log(tmp_path, "")
    run = run_grep(log_file)
    assert list(run.matches) == []
    assert run.parser.malformed_count == 0
