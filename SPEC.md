# LogScope - Project Specification

## 1. Project Overview

LogScope is a Python command line interface also known as CLI tool for analysing application log files after a incident.

This project is to help the operations teams understand application behaviour without needing to open a dashboard or manually search through large log files.

## 2. Technology Requirements

- Programming language for this project: Python
- Interface: Command line interface (CLI).
- Testing framework: pytest.
- Version control: Github.
- Input: Plain-text application log files.
- Output: Human-readable text, JSON or markdown reports.

## 3. Log File Format 

The parser must identify the following information from each valid log line:

- Timestamp
- Log level: INFO, WARN or ERROR
- Message

The expected log format is:

`YYYY-MM-DD HH:MM:SS LEVEL Message text`

The parser must validate timestamps and log levels. Malformed or unsupported lines must be counted and skipped without crashing the application.

Before finalising the parser, inspect the supplied sample log file and adjust the parsing rules if its actual format differs from this example.

## 4. Functional Requirements

### 4.1 Summary Command

Command:

`python -m logscope summary app.log`

The command must:

- Count the number of INFO, WARN and ERROR entries.
- Identify the five most frequent distinct ERROR messages and their occurrence counts.
- Report the first and last valid timestamps encountered in the file.
- Report the total number of malformed lines skipped.
- Handle files containing no valid log entries without crashing.

If fewer than five distinct error messages exist, report only those available. If there are no errors, report that no errors were found.

For equal error frequencies, use alphabetical message order as the tie-breaker.

### 4.2 Timeline Command

Command:

`python -m logscope timeline app.log --bucket 15m`

The command must:

- Count ERROR entries within time buckets of the requested duration.
- Support bucket durations expressed as a positive integer followed by `m` (minutes) or `h` (hours).
- Align bucket boundaries to the clock. For example, a 15-minute bucket starts at 09:00, 09:15, 09:30 or 09:45.
- Display the results as a text-based bar chart.
- Label each bucket with its start timestamp and show its error count.
- Report the number of malformed lines skipped.
- Handle empty input and files with no errors.

Each `#` in the chart represents one error. The chart must not use an excessive amount of terminal space for unusually large counts; if necessary, scale the bars and document the scaling.

### 4.3 Grep Command

Command:

`python -m logscope grep app.log --level ERROR --since "2026-10-01 09:00"`

The command must:

- Filter log entries by the requested level.
- Support INFO, WARN and ERROR as level filters.
- Support an optional `--since` timestamp.
- Include entries whose timestamps are equal to or later than the specified timestamp.
- Print matching log lines in their original order.
- Report the number of malformed lines skipped.
- Handle cases where no entries match.

The `--level` and `--since` filters must be independently optional. If neither is provided, all valid log lines must be eligible for output.

## 5. Output Formats

Every command must support:

`--format json`

and

`--format md`

The default format is JSON if the user does not specify a format.

### JSON

- Write valid JSON to standard output.
- Use a consistent, documented structure for each command.
- Include relevant results and the malformed-line count.
- Do not mix diagnostic messages or progress messages into the JSON output.

### Markdown

- Generate a readable Markdown report file.
- Use predictable filenames in the current working directory:
  - `logscope-summary-report.md`
  - `logscope-timeline-report.md`
  - `logscope-grep-report.md`
- Include the command type, results and malformed-line count.
- Report file-writing errors clearly without crashing or silently losing the report.

The exact JSON field names and report layouts should be documented and tested.

## 6. Error Handling

The application must:

- Count and skip malformed log lines.
- Continue processing when individual lines are invalid.
- Display clear error messages for missing files, unreadable files, invalid command arguments and unsupported output formats.
- Return a non-zero exit status when the command cannot complete because of an invalid argument or file-level error.
- Handle empty files and files with no valid entries gracefully.

Malformed input lines are data-quality issues and must not, by themselves, terminate processing.

## 7. Performance and Memory Requirements

The tool must process a log file of approximately 100 MB in under 60 seconds on the available test environment.

Requirements:

- Read the input incrementally, one line at a time.
- Never load the entire input file into memory.
- Keep memory usage stable as file size increases, apart from bounded result data and the storage needed for individual output matches.
- Do not store every parsed log entry in a list.
- Track summary statistics, error frequencies and timeline buckets incrementally.
- For grep, stream matching lines to the selected output rather than retaining all input lines in memory.
- Document any unavoidable memory limitations associated with Markdown report generation or large grep results.

## 8. Unit Testing

Use pytest to test the parser and all three commands.

Tests must cover:

- Valid INFO, WARN and ERROR entries.
- Malformed lines and invalid timestamps.
- Empty files and files with no valid entries.
- Correct summary counts and top-five error ranking.
- Timeline bucket boundaries and error counts.
- Grep level filtering and inclusive `--since` filtering.
- JSON validity and expected fields.
- Markdown report creation and content.
- Missing files and invalid arguments.
- Correct malformed-line reporting.
- Large-file processing without loading the entire input into memory.

Use temporary files and small deterministic test fixtures wherever possible.

## 9. Synthetic Log Generator and Benchmark

Create a script at `scripts/gen_log` that generates a synthetic log file of approximately 100 MB.

The generator must:

- Produce realistic timestamps, levels and messages.
- Support reproducible output when given the same random seed.
- Support a configurable output path and target size.
- Include a configurable proportion of malformed lines for robustness testing.
- Write incrementally instead of constructing the entire generated file in memory.

Measure and record:

- File size.
- Processing runtime.
- Peak memory usage, using an appropriate measurement method available in the environment.
- Whether the 60-second acceptance target is met.

Document the test environment and benchmark command.

## 10. Project Structure

Use a clear, maintainable structure similar to:

- `SPEC.md` — project specification.
- `Projects.md` — instructions for axet code.
- `pyproject.toml` — project configuration and test dependencies.
- `logscope/` — application package and CLI entry point.
- `tests/` — unit tests.
- `scripts/gen_log` — synthetic log generator.
- `sample.log` — supplied sample input, if available.
- `README.md` — setup, usage and testing instructions.

The implementation plan may refine this structure before coding begins.

## 11. Acceptance Criteria

The project is complete when:

1. All three commands work correctly on the supplied `sample.log`.
2. Unit tests for the parser and each command pass.
3. JSON output is valid, and Markdown reports are written to files.
4. Malformed lines are counted and skipped without crashing the tool.
5. A 100 MB synthetic log is processed in under 60 seconds in the available test environment.
6. Memory usage remains stable and the entire input is not loaded into memory.

## 12. Stretch Goal: Explain Errors with an LLM

`python -m logscope explain app.log`

The command will send the most frequent error messages to an LLM endpoint configured through an environment variable.
