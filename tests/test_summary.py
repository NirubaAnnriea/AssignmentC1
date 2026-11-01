"""Tests for logscope.commands.summary."""

from datetime import datetime

from logscope.commands.summary import compute_summary


def write_log(tmp_path, text):
    log_file = tmp_path / "app.log"
    log_file.write_text(text, encoding="utf-8")
    return log_file


def test_counts_each_level(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 INFO a\n"
        "2026-10-01 09:00:01 WARN b\n"
        "2026-10-01 09:00:02 ERROR c\n"
        "2026-10-01 09:00:03 INFO d\n",
    )
    result = compute_summary(log_file)
    assert result.info_count == 2
    assert result.warn_count == 1
    assert result.error_count == 1


def test_first_and_last_timestamps(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 INFO a\n"
        "2026-10-01 10:00:00 ERROR b\n"
        "2026-10-01 11:30:00 WARN c\n",
    )
    result = compute_summary(log_file)
    assert result.first_timestamp == datetime(2026, 10, 1, 9, 0, 0)
    assert result.last_timestamp == datetime(2026, 10, 1, 11, 30, 0)


def test_top_five_errors_ranked_by_frequency_then_alphabetically(tmp_path):
    lines = []
    lines += ["2026-10-01 09:00:00 ERROR Zeta failure\n"] * 3
    lines += ["2026-10-01 09:00:00 ERROR Alpha failure\n"] * 3
    lines += ["2026-10-01 09:00:00 ERROR Beta failure\n"] * 2
    lines += ["2026-10-01 09:00:00 ERROR Gamma failure\n"] * 1
    lines += ["2026-10-01 09:00:00 ERROR Delta failure\n"] * 1
    lines += ["2026-10-01 09:00:00 ERROR Epsilon failure\n"] * 1
    log_file = write_log(tmp_path, "".join(lines))
    result = compute_summary(log_file)
    messages = [e.message for e in result.top_errors]
    assert messages == [
        "Alpha failure",
        "Zeta failure",
        "Beta failure",
        "Delta failure",
        "Epsilon failure",
    ]
    assert [e.count for e in result.top_errors] == [3, 3, 2, 1, 1]


def test_fewer_than_five_distinct_errors_reports_only_those(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 ERROR Only error\n",
    )
    result = compute_summary(log_file)
    assert len(result.top_errors) == 1
    assert result.top_errors[0].message == "Only error"


def test_no_errors_reports_empty_top_errors(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 INFO a\n2026-10-01 09:00:01 WARN b\n",
    )
    result = compute_summary(log_file)
    assert result.top_errors == []
    assert result.error_count == 0


def test_malformed_lines_are_counted(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 INFO a\nnot a log line\n2026-10-01 09:00:01 WARN b\n",
    )
    result = compute_summary(log_file)
    assert result.malformed_lines == 1


def test_empty_file_produces_zeroed_result(tmp_path):
    log_file = write_log(tmp_path, "")
    result = compute_summary(log_file)
    assert result.info_count == 0
    assert result.warn_count == 0
    assert result.error_count == 0
    assert result.top_errors == []
    assert result.first_timestamp is None
    assert result.last_timestamp is None
    assert result.malformed_lines == 0


def test_file_with_only_malformed_lines(tmp_path):
    log_file = write_log(tmp_path, "garbage\nmore garbage\n")
    result = compute_summary(log_file)
    assert result.error_count == 0
    assert result.first_timestamp is None
    assert result.malformed_lines == 2
