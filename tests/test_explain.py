"""Tests for logscope.commands.explain."""

import pytest

from logscope.commands.explain import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    ExplainError,
    NO_ERRORS_EXPLANATION,
    build_prompt,
    run_explain,
)
from logscope.commands.summary import ErrorFrequency


def write_log(tmp_path, text):
    log_file = tmp_path / "app.log"
    log_file.write_text(text, encoding="utf-8")
    return log_file


def test_no_errors_short_circuits_without_calling_llm(tmp_path, monkeypatch):
    monkeypatch.delenv("LOGSCOPE_LLM_API_KEY", raising=False)
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 INFO all good\n")
    calls = []

    def fake_post(endpoint, payload, api_key, timeout):
        calls.append((endpoint, payload, api_key, timeout))
        return {"explanation": "should not be reached"}

    result = run_explain(log_file, http_post=fake_post)
    assert result.explanation == NO_ERRORS_EXPLANATION
    assert result.endpoint is None
    assert result.model is None
    assert calls == []


def test_missing_api_key_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("LOGSCOPE_LLM_API_KEY", raising=False)
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")
    with pytest.raises(ExplainError) as exc_info:
        run_explain(log_file)
    assert "LOGSCOPE_LLM_API_KEY" in str(exc_info.value)


def test_endpoint_and_model_default_to_sea_lion_when_not_set(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.delenv("LOGSCOPE_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LOGSCOPE_LLM_MODEL", raising=False)
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")
    captured = {}

    def fake_post(endpoint, payload, api_key, timeout):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {"explanation": "x"}

    result = run_explain(log_file, http_post=fake_post)
    assert result.endpoint == DEFAULT_ENDPOINT
    assert result.model == DEFAULT_MODEL
    assert captured["endpoint"] == DEFAULT_ENDPOINT
    assert captured["payload"]["model"] == DEFAULT_MODEL


def test_custom_endpoint_env_var_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.setenv("LOGSCOPE_LLM_ENDPOINT", "https://example.invalid/explain")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")

    def fake_post(endpoint, payload, api_key, timeout):
        assert endpoint == "https://example.invalid/explain"
        return {"explanation": "x"}

    result = run_explain(log_file, http_post=fake_post)
    assert result.endpoint == "https://example.invalid/explain"


def test_sends_top_errors_as_chat_messages_and_returns_explanation(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    log_file = write_log(
        tmp_path,
        "2026-10-01 09:00:00 ERROR disk full\n"
        "2026-10-01 09:00:01 ERROR disk full\n"
        "2026-10-01 09:00:02 ERROR timeout\n",
    )
    captured = {}

    def fake_post(endpoint, payload, api_key, timeout):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        captured["api_key"] = api_key
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": "Likely a disk-space exhaustion issue."}}]}

    result = run_explain(log_file, http_post=fake_post)
    assert result.explanation == "Likely a disk-space exhaustion issue."
    assert captured["api_key"] == "secret-key"
    assert captured["timeout"] == 60.0
    assert captured["payload"]["max_completion_tokens"] == 2000
    messages = captured["payload"]["messages"]
    assert messages == [{"role": "user", "content": messages[0]["content"]}]
    assert "disk full" in messages[0]["content"]
    assert "timeout" in messages[0]["content"]
    assert result.top_errors[0].message == "disk full"
    assert result.top_errors[0].count == 2


def test_custom_model_env_var_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.setenv("LOGSCOPE_LLM_MODEL", "some-other-model")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")
    captured = {}

    def fake_post(endpoint, payload, api_key, timeout):
        captured["payload"] = payload
        return {"explanation": "x"}

    result = run_explain(log_file, http_post=fake_post)
    assert result.model == "some-other-model"
    assert captured["payload"]["model"] == "some-other-model"


def test_custom_max_tokens_env_var_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.setenv("LOGSCOPE_LLM_MAX_TOKENS", "50")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")
    captured = {}

    def fake_post(endpoint, payload, api_key, timeout):
        captured["payload"] = payload
        return {"explanation": "x"}

    run_explain(log_file, http_post=fake_post)
    assert captured["payload"]["max_completion_tokens"] == 50


def test_invalid_max_tokens_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.setenv("LOGSCOPE_LLM_MAX_TOKENS", "not-a-number")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")

    def fake_post(endpoint, payload, api_key, timeout):
        return {"explanation": "x"}

    with pytest.raises(ExplainError):
        run_explain(log_file, http_post=fake_post)


def test_custom_timeout_env_var_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.setenv("LOGSCOPE_LLM_TIMEOUT", "5")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")
    captured = {}

    def fake_post(endpoint, payload, api_key, timeout):
        captured["timeout"] = timeout
        return {"explanation": "x"}

    run_explain(log_file, http_post=fake_post)
    assert captured["timeout"] == 5.0


def test_invalid_timeout_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    monkeypatch.setenv("LOGSCOPE_LLM_TIMEOUT", "not-a-number")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")

    def fake_post(endpoint, payload, api_key, timeout):
        return {"explanation": "x"}

    with pytest.raises(ExplainError):
        run_explain(log_file, http_post=fake_post)


def test_openai_style_response_is_accepted(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")

    def fake_post(endpoint, payload, api_key, timeout):
        return {"choices": [{"message": {"content": "Probably a crash."}}]}

    result = run_explain(log_file, http_post=fake_post)
    assert result.explanation == "Probably a crash."


def test_simple_explanation_field_is_also_accepted(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")

    def fake_post(endpoint, payload, api_key, timeout):
        return {"explanation": "Probably a crash."}

    result = run_explain(log_file, http_post=fake_post)
    assert result.explanation == "Probably a crash."


def test_unrecognised_response_shape_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")

    def fake_post(endpoint, payload, api_key, timeout):
        return {"unexpected": "shape"}

    with pytest.raises(ExplainError):
        run_explain(log_file, http_post=fake_post)


def test_reasoning_model_with_empty_content_falls_back_to_reasoning(tmp_path, monkeypatch):
    """A reasoning model (like SEA-LION's default) can spend its whole
    token budget on hidden 'thinking' and return null/empty content; we
    should still surface the reasoning text instead of erroring out.
    """
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    log_file = write_log(tmp_path, "2026-10-01 09:00:00 ERROR boom\n")

    def fake_post(endpoint, payload, api_key, timeout):
        return {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "reasoning_content": "Thinking: this looks like a crash on boom.",
                    }
                }
            ]
        }

    result = run_explain(log_file, http_post=fake_post)
    assert result.explanation == "Thinking: this looks like a crash on boom."


def test_malformed_lines_are_still_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGSCOPE_LLM_API_KEY", "secret-key")
    log_file = write_log(tmp_path, "garbage\n2026-10-01 09:00:00 ERROR boom\n")

    def fake_post(endpoint, payload, api_key, timeout):
        return {"explanation": "x"}

    result = run_explain(log_file, http_post=fake_post)
    assert result.malformed_lines == 1


def test_build_prompt_lists_errors_in_rank_order():
    top_errors = [
        ErrorFrequency(message="disk full", count=3),
        ErrorFrequency(message="timeout", count=1),
    ]
    prompt = build_prompt(top_errors)
    assert "1. (3x) disk full" in prompt
    assert "2. (1x) timeout" in prompt
