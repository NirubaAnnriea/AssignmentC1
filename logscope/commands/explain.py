"""The ``explain`` command: sends the top ERROR messages from a log file to
an LLM endpoint (configured via environment variables) and reports a
probable root-cause summary.

This is the stretch goal described in SPEC.md section 12. The log file is
still processed as a single streaming pass (via ``compute_summary``) -
only the already-bounded top-5 error list is ever sent over the network,
never the raw log file. No endpoint URL or API key is hardcoded; both are
read from environment variables at run time.

The request is sent in the OpenAI-compatible "chat completions" shape used
by SEA-LION (https://api.sea-lion.ai/v1/chat/completions) and many other
providers::

    POST <endpoint>
    Authorization: Bearer <api key>
    {
        "model": "<model>",
        "max_completion_tokens": <int>,
        "messages": [{"role": "user", "content": "<prompt>"}]
    }

and expects an OpenAI-style response::

    {"choices": [{"message": {"content": "<explanation text>"}}]}

A simpler ``{"explanation": str}`` response is also accepted, for any
custom/mock endpoint that prefers that shape.

Environment variables::

    LOGSCOPE_LLM_ENDPOINT     Required. Chat-completions URL. Defaults to
                              SEA-LION's endpoint
                              (https://api.sea-lion.ai/v1/chat/completions)
                              if not set, so only the API key needs to be
                              configured to use SEA-LION out of the box.
    LOGSCOPE_LLM_API_KEY      Required by most providers (including
                              SEA-LION). Sent as "Authorization: Bearer
                              <key>" if set.
    LOGSCOPE_LLM_MODEL        Optional model name. Defaults to
                              "aisingapore/Qwen-SEA-LION-v4.5-27B-IT".
    LOGSCOPE_LLM_MAX_TOKENS   Optional max completion tokens (default 500).
    LOGSCOPE_LLM_TIMEOUT      Optional request timeout in seconds
                              (default 30).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Union

from logscope.commands.summary import ErrorFrequency, compute_summary

ENDPOINT_ENV_VAR = "LOGSCOPE_LLM_ENDPOINT"
API_KEY_ENV_VAR = "LOGSCOPE_LLM_API_KEY"
MODEL_ENV_VAR = "LOGSCOPE_LLM_MODEL"
MAX_TOKENS_ENV_VAR = "LOGSCOPE_LLM_MAX_TOKENS"
TIMEOUT_ENV_VAR = "LOGSCOPE_LLM_TIMEOUT"

DEFAULT_ENDPOINT = "https://api.sea-lion.ai/v1/chat/completions"
DEFAULT_MODEL = "aisingapore/Qwen-SEA-LION-v4.5-27B-IT"
# SEA-LION's default model is a reasoning model: it spends completion
# tokens on a hidden "thinking" pass before writing the final answer, so a
# small budget (e.g. 500) can be consumed entirely by reasoning, leaving an
# empty final answer. 2000 leaves enough room for both on a short prompt.
DEFAULT_MAX_TOKENS = 2000
DEFAULT_TIMEOUT_SECONDS = 60.0

NO_ERRORS_EXPLANATION = "No ERROR entries were found, so there is nothing to explain."

HttpPost = Callable[[str, dict, Optional[str], float], dict]


class ExplainError(Exception):
    """Raised when the explain command cannot complete: missing endpoint
    configuration, a network/HTTP failure, or an unrecognised LLM response.
    """


@dataclass
class ExplainResult:
    top_errors: List[ErrorFrequency] = field(default_factory=list)
    malformed_lines: int = 0
    explanation: str = ""
    endpoint: Optional[str] = None
    model: Optional[str] = None


def build_prompt(top_errors: List[ErrorFrequency]) -> str:
    """Build a short, deterministic prompt describing the top errors."""
    lines = [
        "You are helping an operations engineer triage a production "
        "incident. Below are the most frequent ERROR messages from an "
        "application log, most frequent first. For each one, suggest a "
        "likely root cause in one or two sentences, then give a short "
        "overall summary.",
        "",
    ]
    for rank, error in enumerate(top_errors, start=1):
        lines.append(f"{rank}. ({error.count}x) {error.message}")
    return "\n".join(lines)


def _default_http_post(
    endpoint: str, payload: dict, api_key: Optional[str], timeout: float
) -> dict:
    """Default transport: POST JSON over HTTP(S) using only the standard
    library, so the stretch goal needs no extra dependency.
    """
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise ExplainError(
            f"LLM endpoint returned HTTP {exc.code}: {exc.reason}"
            + (f" - {detail}" if detail else "")
        ) from exc
    except urllib.error.URLError as exc:
        raise ExplainError(f"Could not reach LLM endpoint '{endpoint}': {exc.reason}") from exc
    except TimeoutError as exc:
        raise ExplainError(f"LLM endpoint '{endpoint}' timed out after {timeout}s") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ExplainError("LLM endpoint returned a response that was not valid JSON") from exc


def _extract_explanation(response: dict) -> str:
    """Accept an OpenAI-style chat-completion response (used by SEA-LION
    and most providers) or a simpler ``{"explanation": str}`` shape.

    Some models (including SEA-LION's default) are "reasoning" models that
    return their hidden thinking in a separate ``reasoning_content`` field
    and only put the final answer in ``content``. If ``max_completion_tokens``
    was too small to fit both, ``content`` can come back empty/null; in
    that case we fall back to ``reasoning_content`` rather than erroring
    out, since it still contains a usable (if less polished) explanation.
    """
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            reasoning = message.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning.strip():
                return reasoning.strip()

    explanation = response.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        return explanation.strip()

    raise ExplainError(
        "LLM endpoint response did not contain a recognisable "
        "chat-completion 'choices' field (or an 'explanation' field)."
    )


def run_explain(
    path: Union[str, Path],
    *,
    http_post: Optional[HttpPost] = None,
) -> ExplainResult:
    """Compute the top ERROR messages for ``path`` and ask the configured
    LLM endpoint for a probable root-cause summary.

    If there are no ERROR entries, the LLM endpoint is never contacted and
    none of the LLM environment variables need to be set.
    """
    summary = compute_summary(path)
    result = ExplainResult(
        top_errors=summary.top_errors,
        malformed_lines=summary.malformed_lines,
    )

    if not summary.top_errors:
        result.explanation = NO_ERRORS_EXPLANATION
        return result

    endpoint = os.environ.get(ENDPOINT_ENV_VAR) or DEFAULT_ENDPOINT
    result.endpoint = endpoint

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        raise ExplainError(
            f"The {API_KEY_ENV_VAR} environment variable is not set. "
            "Set it to your LLM provider's API key (e.g. a SEA-LION API "
            "key from https://sea-lion.ai)."
        )

    model = os.environ.get(MODEL_ENV_VAR) or DEFAULT_MODEL
    result.model = model

    max_tokens = DEFAULT_MAX_TOKENS
    raw_max_tokens = os.environ.get(MAX_TOKENS_ENV_VAR)
    if raw_max_tokens:
        try:
            max_tokens = int(raw_max_tokens)
        except ValueError as exc:
            raise ExplainError(
                f"Invalid {MAX_TOKENS_ENV_VAR} value '{raw_max_tokens}': must be an integer."
            ) from exc

    timeout = DEFAULT_TIMEOUT_SECONDS
    raw_timeout = os.environ.get(TIMEOUT_ENV_VAR)
    if raw_timeout:
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ExplainError(
                f"Invalid {TIMEOUT_ENV_VAR} value '{raw_timeout}': must be a number."
            ) from exc

    post = http_post or _default_http_post
    payload = {
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [{"role": "user", "content": build_prompt(summary.top_errors)}],
    }
    response = post(endpoint, payload, api_key, timeout)
    result.explanation = _extract_explanation(response)
    return result
