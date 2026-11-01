"""Tests for logscope.parser."""

from datetime import datetime

from logscope.parser import LogEntry, LogParser


def test_parses_valid_info_line():
    parser = LogParser()
    entry = parser.parse_line("2026-10-01 09:00:05 INFO Service started\n")
    assert entry == LogEntry(
        timestamp=datetime(2026, 10, 1, 9, 0, 5),
        level="INFO",
        message="Service started",
        raw="2026-10-01 09:00:05 INFO Service started",
    )
    assert parser.malformed_count == 0


def test_parses_valid_warn_and_error_lines():
    parser = LogParser()
    warn = parser.parse_line("2026-10-01 09:01:00 WARN Disk usage high\n")
    error = parser.parse_line("2026-10-01 09:02:00 ERROR Connection refused\n")
    assert warn.level == "WARN"
    assert error.level == "ERROR"
    assert parser.malformed_count == 0


def test_blank_line_is_ignored_not_malformed():
    parser = LogParser()
    assert parser.parse_line("\n") is None
    assert parser.parse_line("   \n") is None
    assert parser.malformed_count == 0


def test_unknown_level_is_malformed():
    parser = LogParser()
    assert parser.parse_line("2026-10-01 09:00:00 DEBUG Something happened\n") is None
    assert parser.malformed_count == 1


def test_invalid_calendar_date_is_malformed():
    parser = LogParser()
    assert parser.parse_line("2026-02-30 09:00:00 ERROR Impossible date\n") is None
    assert parser.malformed_count == 1


def test_invalid_time_is_malformed():
    parser = LogParser()
    assert parser.parse_line("2026-10-01 25:00:00 ERROR Bad hour\n") is None
    assert parser.malformed_count == 1


def test_missing_message_is_malformed():
    parser = LogParser()
    assert parser.parse_line("2026-10-01 09:00:00 ERROR\n") is None
    assert parser.malformed_count == 1


def test_missing_level_is_malformed():
    parser = LogParser()
    assert parser.parse_line("2026-10-01 09:00:00 Something went wrong\n") is None
    assert parser.malformed_count == 1


def test_completely_garbage_line_is_malformed():
    parser = LogParser()
    assert parser.parse_line("not a log line at all") is None
    assert parser.malformed_count == 1


def test_message_may_contain_extra_whitespace_and_colons():
    parser = LogParser()
    entry = parser.parse_line("2026-10-01 09:00:00 ERROR key=value: timeout after 30s\n")
    assert entry.message == "key=value: timeout after 30s"


def test_parse_file_streams_entries_and_counts_malformed(tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text(
        "2026-10-01 09:00:00 INFO Start\n"
        "garbage line\n"
        "2026-10-01 09:00:05 ERROR Boom\n"
        "\n"
        "2026-10-01 09:00:10 WARN Careful\n",
        encoding="utf-8",
    )
    parser = LogParser()
    entries = list(parser.parse_file(log_file))
    assert [e.level for e in entries] == ["INFO", "ERROR", "WARN"]
    assert parser.malformed_count == 1


def test_parse_file_handles_empty_file(tmp_path):
    log_file = tmp_path / "empty.log"
    log_file.write_text("", encoding="utf-8")
    parser = LogParser()
    entries = list(parser.parse_file(log_file))
    assert entries == []
    assert parser.malformed_count == 0


def test_parse_file_handles_only_malformed_lines(tmp_path):
    log_file = tmp_path / "bad.log"
    log_file.write_text("nope\nnope again\n", encoding="utf-8")
    parser = LogParser()
    entries = list(parser.parse_file(log_file))
    assert entries == []
    assert parser.malformed_count == 2
