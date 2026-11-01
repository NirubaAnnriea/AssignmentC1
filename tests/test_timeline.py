"""Tests for logscope.commands.timeline."""

from datetime import datetime, timedelta

import pytest

from logscope.commands.timeline import (
    InvalidBucketError,
    compute_timeline,
    parse_bucket_duration,
    render_bar_chart,
)


def write_log(tmp_path, text):
    log_file = tmp_path / "app.log"
    log_file.write_text(text, encoding="utf-8")
    return log_file


def test_parse_bucket_duration_minutes():
    assert parse_bucket_duration("15m") == timedelta(minutes=15)


def test_parse_bucket_duration_hours():
    assert parse_bucket_duration("2h") == timedelta(hours=2)


@pytest.mark.parametrize("value", ["0m", "-5m", "15", "15x", "m", "", "1.5h"])
def test_parse_bucket_duration_rejects_invalid_values(value):
    with pytest.raises(InvalidBucketError):
        parse_bucket_duration(value)


def test_buckets_are_aligned_to_the_clock(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:07:30 ERROR a\n"
        "2026-10-01 09:14:59 ERROR b\n"
        "2026-10-01 09:15:00 ERROR c\n",
    )
    result = compute_timeline(log_file, "15m")
    starts = [b.start for b in result.buckets]
    assert starts == [
        datetime(2026, 10, 1, 9, 0, 0),
        datetime(2026, 10, 1, 9, 15, 0),
    ]
    counts = {b.start: b.count for b in result.buckets}
    assert counts[datetime(2026, 10, 1, 9, 0, 0)] == 2
    assert counts[datetime(2026, 10, 1, 9, 15, 0)] == 1


def test_only_error_entries_are_counted(tmp_path):
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 INFO a\n"
        "2026-10-01 09:00:01 WARN b\n"
        "2026-10-01 09:00:02 ERROR c\n",
    )
    result = compute_timeline(log_file, "1h")
    assert len(result.buckets) == 1
    assert result.buckets[0].count == 1


def test_empty_file_has_no_buckets(tmp_path):
    log_file = write_log(tmp_path, "")
    result = compute_timeline(log_file, "15m")
    assert result.buckets == []
    assert render_bar_chart(result) == "No errors found."


def test_file_with_no_errors_has_no_buckets(tmp_path):
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 INFO a\n")
    result = compute_timeline(log_file, "15m")
    assert result.buckets == []


def test_malformed_lines_are_counted(tmp_path):
    log_file = write_log(
        tmp_path, "garbage\n2026-10-01 09:00:00 ERROR a\n"
    )
    result = compute_timeline(log_file, "15m")
    assert result.malformed_lines == 1


def test_large_counts_are_scaled_down(tmp_path):
    lines = ["2026-10-01 09:00:00 ERROR a\n"] * 200
    log_file = write_log(tmp_path, "".join(lines))
    result = compute_timeline(log_file, "15m")
    assert result.scale > 1
    chart = render_bar_chart(result)
    bar_line = [line for line in chart.splitlines() if "2026-10-01 09:00:00" in line][0]
    bar_chars = bar_line.split("|")[1].split("(")[0].strip()
    assert len(bar_chars) <= 50


def test_render_bar_chart_includes_label_and_count(tmp_path):
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR a\n")
    result = compute_timeline(log_file, "15m")
    chart = render_bar_chart(result)
    assert "2026-10-01 09:00:00" in chart
    assert "(1)" in chart
    assert "#" in chart
