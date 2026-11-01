# Instructions for aXet Code - LogScope

## 1. Your Role

You are assisting with building LogScope, a Python command-line tool for analysing application log files.

Use `SPEC.md` as the main reference for what the application must do.

Your priorities are:
- Write clean, readable Python code.
- Make sure the application works correctly.
- Test each feature before moving on.
- Keep the code simple and easy to maintain.
- Make sure large log files can be processed efficiently.

Explain technical concepts and important decisions in simple terms because the developer is still learning software engineering.

## 2. Plan Before Coding

Do not start writing code immediately.

First:

1. Read `SPEC.md` and this instruction file.
2. Check whether a `sample.log` file has been provided.
3. Identify anything unclear or missing from the requirements.
4. Create a step-by-step implementation plan.
5. Explain which files need to be created and what each file will do.
6. Explain how you will test the application and check its performance.

Present the implementation plan and wait for my approval before writing any application code.

If something in the specification is unclear, explain the issue and suggest a solution.

## 3. Coding Guidelines

When writing the application:

- Use Python 3.11 or later.
- Use pytest for unit testing.
- Prefer Python's built-in libraries where possible.
- Use clear variable and function names.
- Add type hints where appropriate.
- Keep functions small and focused.
- Separate the parser, commands and output formatting into appropriate modules.
- Avoid unnecessary complexity and duplicated code.
- Handle errors properly and provide understandable error messages.
- Follow standard Python coding conventions.
- Never hardcode API keys or passwords.

## 4. Implementation Steps

Once the implementation plan is approved, build the application in the following order.

### Step 1: Project Setup and Log Parser

- Create the basic project structure.
- Inspect the provided sample log to understand its format.
- Build the parser to read and understand individual log lines.
- Identify valid and malformed log entries.
- Write tests for the parser.
- Run the tests and fix any issues.

### Step 2: Summary Command

- Count INFO, WARN and ERROR entries.
- Find the five most frequent error messages.
- Identify the first and last timestamps.
- Count malformed lines.
- Write tests for the summary command.
- Run the tests and fix any issues.

### Step 3: Timeline Command

- Group errors into time intervals.
- Support the requested time bucket options.
- Display errors as a text-based bar chart.
- Write tests for the timeline command.
- Run the tests and fix any issues.

### Step 4: Grep Command

- Allow users to filter logs by level.
- Allow users to filter logs by timestamp.
- Preserve the original order of matching entries.
- Write tests for the grep command.
- Run the tests and fix any issues.

### Step 5: Output Formats

- Add JSON output support.
- Add Markdown report generation.
- Make sure each command supports both formats.
- Check that Markdown reports are saved correctly.
- Write tests for both output formats.
- Run the tests and fix any issues.

### Step 6: Large Log File Testing

- Create a script to generate a synthetic log file of approximately 100 MB.
- Make sure the generator writes data incrementally.
- Run LogScope against the generated file.
- Measure processing time and memory usage.
- Check whether the application meets the 60-second requirement.
- Improve performance if necessary.

### Step 7: Final Testing

- Run all unit tests.
- Test all three commands using the supplied sample log.
- Check JSON and Markdown outputs.
- Test malformed lines and missing files.
- Check that large files can be processed efficiently.
- Update the README with instructions on how to use the application.

The optional LLM-based `explain` feature should only be considered after all required features are completed.

## 5. Testing Requirements

Testing is an important part of this project.

- Write unit tests for each feature.
- Run tests after completing each implementation step.
- Fix errors before moving on to the next feature.
- Test normal situations as well as unusual cases.
- Use small sample files for testing where possible.
- Do not claim that tests have passed unless they have actually been executed.

If a test fails:
1. Explain what went wrong.
2. Identify the likely cause.
3. Fix the issue.
4. Run the test again.

## 6. Memory and Performance

The application must be able to process large log files without using excessive memory.

Follow these rules:

- Read the file one line at a time.
- Do not load the entire log file into memory.
- Avoid using `readlines()` or storing every log entry in a list.
- Keep only the information needed for calculations.
- Stream matching results instead of storing all matching lines.
- Measure memory usage during the 100 MB test.

The goal is to process a 100 MB log file in under 60 seconds while keeping memory usage stable.

## 7. Communication

Throughout the project:

- Explain what you are going to implement before starting each step.
- Explain important code and technical decisions in simple terms.
- Complete one feature at a time.
- Run tests after each feature.
- Show which files were created or modified.
- Summarise the test results.
- Explain any problems or limitations.

Do not implement multiple major features at once.

Wait for the developer's approval before moving from the initial implementation plan to coding.

## 8. Completion Requirements

The project is considered complete when:

1. The summary, timeline and grep commands work.
2. All unit tests pass.
3. JSON and Markdown output work correctly.
4. Malformed lines are counted and skipped without crashing.
5. A 100 MB log file is processed in under 60 seconds.
6. Memory usage remains stable.
7. The application works correctly with the supplied sample log.

At the end, provide a summary explaining:
- What features were implemented.
- What tests were performed.
- Whether all tests passed.
- How long the 100 MB file took to process.
- How much memory was used.
- Any remaining issues.

Clearly identify anything that has not been tested or verified.