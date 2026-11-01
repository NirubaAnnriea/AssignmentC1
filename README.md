# LogScope

A Python command line tool for analysing application log files after an
incident: summarise them, chart ERROR entries over time, or grep them by
level and timestamp.

## 1. Requirements

- Python 3.11+ (tested with Python 3.12).
- `pytest` and `psutil` for running tests and the benchmark (`pip install -e .[dev]`).

## 2. Installation

From the project root:

```bash
python -m pip install -e .[dev]
```

No installation is strictly required to run the tool - `python -m logscope ...`
works from the project root as long as `pytest`/`psutil` are available for
testing/benchmarking.

### Generating a sample log

`sample.log` is **not** committed to this repository (it's a ~100 MB
generated file, excluded via `.gitignore`). To create your own copy to run
the commands below against, use the included generator:

```bash
python scripts/gen_log --output sample.log --size-mb 100 --seed 42 --malformed-ratio 0.02 --progress
```

This is fully reproducible - the same `--seed` always produces the exact
same file - and writes incrementally, so generating it never loads the
whole file into memory. Use a smaller `--size-mb` (e.g. `1`) for a quicker
file to experiment with; see section 9 for the full generator options.

## 3. Usage

### Summary

```bash
python -m logscope summary sample.log
python -m logscope summary sample.log --format md
```

Counts INFO/WARN/ERROR entries, ranks the top 5 most frequent ERROR
messages (ties broken alphabetically), and reports the first/last valid
timestamp and the number of malformed lines skipped.

### Timeline

```bash
python -m logscope timeline sample.log --bucket 15m
python -m logscope timeline sample.log --bucket 2h --format md
```

Counts ERROR entries into clock-aligned time buckets (e.g. a 15-minute
bucket always starts at :00/:15/:30/:45, never at an offset derived from
the first log line) and renders a `#`-based text bar chart.

### Grep

```bash
python -m logscope grep sample.log --level ERROR --since "2026-10-01 09:00"
python -m logscope grep sample.log --format md
```

Filters entries by level and/or a `--since` timestamp (inclusive), printing
matches in their original file order. Both filters are optional and
independent; omitting both returns every valid line.

### Quick reference

```bash
python -m logscope summary sample.log
python -m logscope timeline sample.log --bucket 15m
python -m logscope grep sample.log --level ERROR --since "2026-10-01 09:00"
```

- `summary` — counts of INFO/WARN/ERROR entries, the top 5 most frequent
  distinct ERROR messages, and the first/last valid timestamp in the file.
- `timeline --bucket 15m` — ERROR count per clock-aligned 15-minute bucket,
  rendered as a `#` text bar chart.
- `grep --level ERROR --since "2026-10-01 09:00"` — prints every ERROR line
  timestamped on or after `2026-10-01 09:00`, in original file order.

All three (plus `explain`, below) accept `--format json` (default, printed
to stdout) or `--format md` (written to a report file) and report the
malformed-line count.

### Explain (stretch goal)

```bash
set LOGSCOPE_LLM_API_KEY=your-sea-lion-api-key
python -m logscope explain sample.log
python -m logscope explain sample.log --format md
```

To quickly test this command yourself (PowerShell):

```powershell
$env:LOGSCOPE_LLM_API_KEY = "PASTE_API_KEY_HERE"
python -m logscope explain sample.log --format md
```

No API key is committed to this repository (see section 6/"Design decisions"
and the `.gitignore` entry for `.env`) - **contact me at niruba.kich@global.ntt for a
working test key** if you need one to try this command yourself.

Sends the top 5 ERROR messages (never the raw log file) to an LLM endpoint
configured through environment variables, and prints/writes a probable
root-cause summary alongside the same top-error list used by `summary`.
By default this calls [SEA-LION](https://sea-lion.ai)'s chat-completions
API (`https://api.sea-lion.ai/v1/chat/completions`, model
`aisingapore/Qwen-SEA-LION-v4.5-27B-IT`), so only an API key is required
out of the box; any other OpenAI-compatible chat-completions endpoint can
be used instead by overriding `LOGSCOPE_LLM_ENDPOINT`/`LOGSCOPE_LLM_MODEL`.

Configuration (environment variables only - nothing is hardcoded):

| Variable | Required | Meaning |
|---|---|---|
| `LOGSCOPE_LLM_API_KEY` | Yes (if there are errors) | Sent as `Authorization: Bearer <key>`. |
| `LOGSCOPE_LLM_ENDPOINT` | No | Chat-completions URL. Defaults to SEA-LION's endpoint. |
| `LOGSCOPE_LLM_MODEL` | No | Model name. Defaults to `aisingapore/Qwen-SEA-LION-v4.5-27B-IT`. |
| `LOGSCOPE_LLM_MAX_TOKENS` | No | `max_completion_tokens` for the request (default `2000`). |
| `LOGSCOPE_LLM_TIMEOUT` | No | Request timeout in seconds (default `60`). |

Behaviour notes:

- If there are no ERROR entries, the endpoint is never contacted and no
  LLM environment variable needs to be set - the report just states that
  there is nothing to explain.
- If `LOGSCOPE_LLM_API_KEY` is missing while there are errors, the command
  fails with a clear message and a non-zero exit code (same error-handling
  pattern as the other commands).
- The request is sent in the standard OpenAI-compatible chat-completions
  shape (`{"model", "max_completion_tokens", "messages"}`), which SEA-LION
  and most LLM providers accept.
- **Reasoning-model token budget**: SEA-LION's default model emits a
  hidden "thinking" pass (`reasoning_content`) before its final answer
  (`content`); a too-small `max_completion_tokens` can be entirely consumed
  by reasoning, leaving `content` empty. 2000 was chosen as a default that
  leaves room for both on a short, 5-error prompt; if `content` still comes
  back empty, the tool falls back to `reasoning_content` rather than
  failing. Raise `LOGSCOPE_LLM_MAX_TOKENS` if explanations look cut off.
- Network/HTTP failures and unrecognised response shapes are caught and
  reported as a clean error, never a raw traceback.
- Uses only the Python standard library (`urllib.request`) - no extra
  dependency is required for this stretch goal.


## 4. Output formats

Every command supports `--format json` (default) and `--format md`.

- **JSON** is written to stdout only - no other text is mixed into it, so
  it is always safe to pipe into `jq`/scripts.
- **Markdown** is written to a predictable file in the current directory
  (`logscope-summary-report.md`, `logscope-timeline-report.md`,
  `logscope-grep-report.md`, `logscope-explain-report.md`); a short
  confirmation line is printed to stdout. Report write failures (e.g. an
  unwritable directory) are caught and reported clearly with a non-zero
  exit code - they never crash with a raw traceback or silently drop the
  report.

JSON field schemas are documented in the docstring at the top of
`logscope/output.py` and exercised by `tests/test_output.py`. In short:

- `summary`: `levels`, `top_errors`, `first_timestamp`, `last_timestamp`, `malformed_lines`.
- `timeline`: `bucket`, `scale`, `buckets` (`start`, `count`), `chart`, `malformed_lines`.
- `grep`: `level`, `since`, `matches` (`timestamp`, `level`, `message`, `line`), `match_count`, `malformed_lines`.
- `explain`: `top_errors`, `explanation`, `endpoint`, `model`, `malformed_lines`.

## 5. Log format and parsing rules

Expected line format: `YYYY-MM-DD HH:MM:SS LEVEL Message text`, where LEVEL
is `INFO`, `WARN` or `ERROR`. The timestamp must be a real calendar
date/time. Blank lines are ignored (not counted as malformed). Any other
line that doesn't match this shape - unknown level, invalid date/time,
missing message, no level field, garbage text - is counted as malformed
and skipped; parsing never stops or crashes because of it.

## 6. Design decisions worth noting

- **No `sample.log` was supplied** with the assignment, so the 100 MB file
  used both as the "supplied sample" and as the performance benchmark input
  is generated by `scripts/gen_log` (seed `42`). Unit tests use their own
  small, deterministic fixtures instead, per spec section 8.
- **Timeline chart vs. JSON**: the spec asks for both a "text-based bar
  chart" and strict JSON output with no mixed diagnostics. These are
  reconciled by embedding the rendered chart as a string value inside the
  JSON payload (`"chart": "..."`) alongside the structured `buckets` data,
  and as a fenced code block in the Markdown report.
- **Timeline buckets with zero errors are omitted.** Only buckets that
  contain at least one ERROR are stored/reported; this keeps memory bounded
  by the number of *distinct error buckets*, not by the length of the time
  range, and avoids printing potentially huge empty stretches for sparse
  logs spanning long periods.
- **Bar chart scaling**: bars are capped at 50 `#` characters
  (`logscope/commands/timeline.py::MAX_BAR_WIDTH`). If the busiest bucket
  exceeds that, all bars are scaled down by `ceil(max_count / 50)` and the
  scale factor is printed on the first line of the chart
  (`(each '#' represents N errors)`).
- **`--since` accepts both `"YYYY-MM-DD HH:MM"` and `"YYYY-MM-DD HH:MM:SS"`**,
  since the spec's own example (`"2026-10-01 09:00"`) omits seconds.

## 7. Performance and memory

Requirements (SPEC.md section 7): process ~100 MB in under 60 seconds,
without loading the whole file into memory, by reading one line at a time
and tracking only bounded statistics.

How this is achieved:

- `logscope/parser.py` streams the file with a plain `for line in handle`
  loop (no `readlines()`, no full-file buffering).
- `summary` keeps only 3 level counters, a dict of *distinct* ERROR
  messages (far smaller than the line count in practice) and two
  timestamps - never a list of all entries.
- `timeline` keeps only one counter per *distinct bucket that has at least
  one error* - bounded by the number of error buckets, not by file size.
- `grep` streams matches lazily (a generator); both the JSON writer and the
  Markdown writer in `logscope/output.py` write one match at a time instead
  of collecting them into a list first.

### Known memory limitation

Markdown grep reports with very large match counts still produce a large
file on disk (write-as-you-go, so the file content itself is big) even
though memory stays bounded - this is an unavoidable consequence of saving
every match to a persistent report file, not a buffering issue in the tool.

### Benchmark

Run with:

```bash
python scripts/gen_log --output sample.log --size-mb 100 --seed 42 --malformed-ratio 0.02 --progress
python scripts/benchmark.py sample.log
```

`scripts/gen_log` writes the file incrementally (one encoded line at a
time) and is fully reproducible for a given `--seed`. `scripts/benchmark.py`
times `summary` with `time.perf_counter()` and samples the process's RSS
memory with `psutil` from a background polling thread every 50 ms (chosen
because Windows has no `resource.getrusage` peak-RSS API) - the result is
an approximation of peak memory, not an exact figure.

**Test environment**: Windows, Python 3.12.10, `psutil` 7.2.2.

**Results** (100 MB file, 1,484,792 INFO / 423,802 WARN / 211,683 ERROR /
43,983 malformed lines):

| Command | Time | Notes |
|---|---|---|
| `summary` | 23.2 s | peak RSS (sampled) ≈ 30.8 MB |
| `timeline --bucket 1h` | 26.4 s | 1,202 non-empty buckets |
| `grep --level ERROR` | 28.8 s | 211,683 matches |

All three are well under the 60-second target, and memory stays in the
tens of megabytes regardless of the 100 MB input - consistent with the
"read incrementally, never load the whole file" requirement.

## 8. Testing

```bash
python -m pytest
```

93 tests across `tests/test_parser.py`, `tests/test_summary.py`,
`tests/test_timeline.py`, `tests/test_grep.py`, `tests/test_explain.py`,
`tests/test_output.py` and `tests/test_cli.py`, covering: valid/malformed
lines, empty files and files with no valid entries, summary counts and
top-5 ranking (including the alphabetical tie-breaker), timeline bucket
alignment and bar-chart scaling, grep level/`--since` filtering (inclusive
boundary) and ordering, the `explain` command (missing-endpoint error,
optional API key/timeout, OpenAI-style and documented response shapes,
no-errors short-circuit, malformed-line reporting - the real HTTP call is
faked via dependency injection so tests never touch the network), JSON
validity/schema, Markdown report creation, missing files/directories,
invalid arguments (`--bucket`, `--level`, `--since`, `--format`), and
malformed-line counts.

Large-file / streaming behaviour is exercised manually via
`scripts/benchmark.py` against the 100 MB `sample.log` rather than inside
`pytest` (a 100 MB fixture is impractical to ship/run on every test
invocation); the parser/command unit tests instead assert the streaming
API shape (generators, no materialised entry lists) on small fixtures.

## 9. Project structure

```
pyproject.toml              project metadata, pytest config
logscope/
  __init__.py
  __main__.py                python -m logscope entry point
  cli.py                      argument parsing, error handling, dispatch
  parser.py                   streaming log-line parser
  output.py                   JSON/Markdown formatting and report writers
  commands/
    summary.py
    timeline.py
    grep.py
    explain.py                 LLM root-cause summary (stretch goal)
tests/                        pytest suite (93 tests)
scripts/
  gen_log                     synthetic log generator (reproducible, incremental)
  benchmark.py                runtime + memory benchmark harness
sample.log                    100 MB synthetic log (generated, seed 42)
SPEC.md / PROJECT.md          original assignment spec and instructions
```

## 10. Stretch goal: `explain` (implemented)

SPEC.md section 12 describes an optional `explain` command that sends the
most frequent error messages to an LLM endpoint configured via an
environment variable. This is now implemented - see section 3 above for
usage and the `LOGSCOPE_LLM_ENDPOINT` / `LOGSCOPE_LLM_API_KEY` /
`LOGSCOPE_LLM_TIMEOUT` environment variables. No API key or endpoint URL is
hardcoded anywhere in the source; both are read from the environment at
run time, and only the bounded top-5 error list (never the raw log file)
is sent over the network.

## 11. Known limitations

- `--since` parses `YYYY-MM-DD HH:MM` or `YYYY-MM-DD HH:MM:SS` only (no
  timezone support, matching the log format itself which has none).
- Timeline buckets with zero errors are not shown (see section 6).
- Large Markdown grep reports produce a large file on disk (see section 7).
- `explain` requires an externally-hosted LLM endpoint that implements the
  documented request/response contract (section 3); this project does not
  ship or run that endpoint itself.
