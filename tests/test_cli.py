"""Tests for logscope.cli (argument handling, error codes, end-to-end runs)."""

import json

import pytest

from logscope.cli import main

SAMPLE = (
    "2026-10-01 09:00:00 INFO start\n"
    "2026-10-01 09:00:01 ERROR boom\n"
    "garbage\n"
    "2026-10-01 09:00:02 WARN careful\n"
)


def write_log(tmp_path, text=SAMPLE):
    log_file = tmp_path / "app.log"
    log_file.write_text(text, encoding="utf-8")
    return str(log_file)


def test_summary_json_end_to_end(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = write_log(tmp_path)
    exit_code = main(["summary", log_file])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "summary"
    assert payload["malformed_lines"] == 1


def test_summary_markdown_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = write_log(tmp_path)
    exit_code = main(["summary", log_file, "--format", "md"])
    assert exit_code == 0
    assert (tmp_path / "logscope-summary-report.md").exists()


def test_timeline_json_end_to_end(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = write_log(tmp_path)
    exit_code = main(["timeline", log_file, "--bucket", "15m"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "timeline"


def test_grep_json_end_to_end(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = write_log(tmp_path)
    exit_code = main(["grep", log_file, "--level", "ERROR"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["match_count"] == 1


def test_grep_markdown_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = write_log(tmp_path)
    exit_code = main(["grep", log_file, "--format", "md"])
    assert exit_code == 0
    assert (tmp_path / "logscope-grep-report.md").exists()


def test_missing_file_returns_nonzero_and_clear_message(tmp_path, capsys):
    missing = str(tmp_path / "does-not-exist.log")
    exit_code = main(["summary", missing])
    assert exit_code != 0
    err = capsys.readouterr().err
    assert "not found" in err.lower()


def test_directory_as_logfile_returns_nonzero(tmp_path, capsys):
    exit_code = main(["summary", str(tmp_path)])
    assert exit_code != 0
    assert capsys.readouterr().err


def test_invalid_bucket_returns_nonzero(tmp_path, capsys):
    log_file = write_log(tmp_path)
    exit_code = main(["timeline", log_file, "--bucket", "not-a-bucket"])
    assert exit_code != 0
    assert "bucket" in capsys.readouterr().err.lower()


def test_invalid_level_returns_nonzero(tmp_path, capsys):
    log_file = write_log(tmp_path)
    exit_code = main(["grep", log_file, "--level", "DEBUG"])
    assert exit_code != 0
    assert "level" in capsys.readouterr().err.lower()


def test_invalid_since_returns_nonzero(tmp_path, capsys):
    log_file = write_log(tmp_path)
    exit_code = main(["grep", log_file, "--since", "not-a-date"])
    assert exit_code != 0
    assert "since" in capsys.readouterr().err.lower()


def test_invalid_format_is_rejected_by_argparse(tmp_path):
    log_file = write_log(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        main(["summary", log_file, "--format", "xml"])
    assert exc_info.value.code != 0


def test_timeline_without_bucket_is_rejected_by_argparse(tmp_path):
    log_file = write_log(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        main(["timeline", log_file])
    assert exc_info.value.code != 0


def test_empty_file_summary_does_not_crash(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = write_log(tmp_path, "")
    exit_code = main(["summary", log_file])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["levels"] == {"INFO": 0, "WARN": 0, "ERROR": 0}


def test_explain_missing_api_key_returns_nonzero(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("LOGSCOPE_LLM_API_KEY", raising=False)
    log_file = write_log(tmp_path, "2026-10-01 09:00:01 ERROR boom\n")
    exit_code = main(["explain", log_file])
    assert exit_code != 0
    assert "LOGSCOPE_LLM_API_KEY" in capsys.readouterr().err


def test_explain_json_end_to_end(tmp_path, capsys, monkeypatch):
    import logscope.commands.explain as explain_module

    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.setattr(
        explain_module,
        "_default_http_post",
        lambda endpoint, payload, api_key, timeout: {
            "choices": [{"message": {"content": "Root cause: disk full."}}]
        },
    )
    log_file = write_log(tmp_path, "2026-10-01 09:00:01 ERROR boom\n")
    exit_code = main(["explain", log_file])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "explain"
    assert payload["explanation"] == "Root cause: disk full."


def test_explain_markdown_end_to_end(tmp_path, monkeypatch):
    import logscope.commands.explain as explain_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.setattr(
        explain_module,
        "_default_http_post",
        lambda endpoint, payload, api_key, timeout: {
            "choices": [{"message": {"content": "Root cause."}}]
        },
    )
    log_file = write_log(tmp_path, "2026-10-01 09:00:01 ERROR boom\n")
    exit_code = main(["explain", log_file, "--format", "md"])
    assert exit_code == 0
    assert (tmp_path / "logscope-explain-report.md").exists()


def test_explain_no_errors_does_not_need_api_key(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("LOGSCOPE_LLM_API_KEY", raising=False)
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 INFO ok\n")
    exit_code = main(["explain", log_file])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "No ERROR entries" in payload["explanation"]
