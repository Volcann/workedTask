<p align="center">
  <img src="icon.png" alt="workedTask logo" width="128" height="128" />
</p>

# workedTask

**Turn GitHub activity into a structured daily work report-with explicit shift rules, traceable evidence, and optional AI summaries.**

`workedTask` collects activity through `ghToolkit`, separates regular work from overtime, and renders an office-format status report. It also provides validators for report structure and consistency with the collected evidence.

[Problem](#problem) · [Solution](#solution) · [Impact](#impact) · [Quick Start](#quick-start) · [Configuration](#configuration) · [CLI Reference](#cli-reference) · [Validation](#validation) · [Backend PR Review Guide](docs/backend-pr-review.md)

## Problem

A daily status report should explain what you worked on, what you reviewed, and when the activity happened. Building that report manually means searching across repositories, reconciling commits and comments, checking merge attribution, and applying the same reporting format every day.

Three details make this harder than copying a list of commits:

- **Activity is scattered.** Implementation, reviews, issues, and non-GitHub work need to appear in one report without misattributing another person's work.
- **A workday is not always a calendar day.** Late-night activity may belong to the previous reporting day, and overtime must follow an explicit local shift.
- **A summary is not proof.** A PR title, review comment, or AI-generated sentence does not establish that a change was correct, deployed, or responsible for a measurable improvement.

The goal is a repeatable reporting process that preserves those distinctions.

## Solution

The primary `worked-task` CLI uses `ghToolkit` as its GitHub collection layer. `ReportService` turns the returned activity into report chunks, applies the configured shift, adds manual tasks, and optionally requests AI summaries. The formatter produces the final text.

```text
GitHub activity through ghToolkit ─┐
                                  ├─> ReportService
Saved ghToolkit snapshot ──────────┘       ├─ Reporting-day and shift rules
                                          ├─ Repository / PR activity chunks
Manual tasks ─────────────────────────────>├─ Non-GitHub work
                                          └─ Optional Gemini summaries
                                                    |
                                                    v
                                              DailyReport
                                               /       \
                                      Office text     PR JSONL
                                           |
                                           v
                                 Explicit validation through
                                 the Python API, when requested
```

The activity model supports authored PR work, reviewed PRs and comments, standalone branch commits, issues, and manual tasks. Categories can overlap; adding their counts does not necessarily give a unique task count.

The office formatter uses conditional sections such as `Reviewed PRs:`, `Merged PRs:`, `Backend PR:`, `Frontend PR:`, `Out of scope:`, and `Overtime:`. It renders the required overtime marker itself:

```text
(The task is done in extra time)
```

**Scope:** this is a report generator, not a scheduler, time tracker, or automated backend performance auditor. The CLI does not run the validators automatically. A separate legacy JSON extractor remains in the repository; it is not the primary report-generation path.

Implementation: [`ReportService`](src/report/service/report_service.py), [`DailyReport`](src/report/data_classes/daily_report.py), [`formatter`](src/utils/format.py), and [`CLI`](src/cli/commands.py).

## Impact

### What the tool is intended to improve

| Outcome | Supporting behavior | How to measure the outcome |
| --- | --- | --- |
| Less manual report preparation | One reporting workflow combines collected activity and manual tasks | Compare active preparation and correction time for comparable reports |
| More consistent shift reporting | Explicit timezone, reporting-day cutoff, and overtime rules | Count classification errors against a human-reviewed reference set |
| Better traceability | Activity identifiers, timestamps, links, and source-consistency checks | Measure supported claims and independently audit attribution |
| Clearer review reporting | Review findings remain distinct from approvals and implementation work | Check whether each reported finding has an attributable review and supporting evidence |

These are intended benefits, not published benchmark results. This repository does not establish a measured time saving, latency reduction, production defect reduction, or infrastructure-cost saving.

For report preparation, calculate:

```text
Minutes saved per report = baseline active minutes − assisted active minutes
Monthly hours saved      = minutes saved per report × reports per month / 60
```

Include configuration, evidence checking, and corrections in the assisted workflow. Report machine runtime separately from active human time. Use actual report counts and comparable samples; label extrapolations as estimates.

### How to report backend PR impact

Use **Problem → Solution → Impact → Evidence**. Describe what the review established before claiming what the fix achieved.

> **Problem:** The order-list serializer performs related-object lookups for each order.
>
> **Solution:** Fetch the required relationships before serialization and add query-count regression tests.
>
> **Impact:** Not yet measured. Verify query counts at multiple page sizes, then compare latency under the same workload. Do not infer a latency percentage from query-count reduction.
>
> **Evidence:** Record the base and head commit IDs, dataset, test command, query trace, and benchmark output.

A finding progresses through **identified**, **reproduced**, **fixed**, **verified**, and **deployed**. These are different claims. Identifying a risk is meaningful review work, but it is not evidence that a production incident was prevented.

The [Backend PR Review Guide](docs/backend-pr-review.md) provides worked calculations, N+1 examples, deterministic concurrency tests, stale-object checks, and a reusable review template. Its Django/PostgreSQL examples are illustrative; they are not components of `workedTask`.

## Quick Start

### Prerequisites

Use Python 3.11 or newer and a compatible `ghtoolkit` installation (`>=0.2.0,<0.3.0`). Live reports also need GitHub access through `GITHUB_TOKEN`, `GH_TOKEN`, or an existing GitHub CLI login.

The supplied repository does **not** include the `ghToolkit` source. The installation below assumes you have obtained the compatible companion checkout and placed it next to this repository:

```text
workspace/
├── ghToolkit/
└── workedTask/
```

### 1. Install

Run from the `workedTask` repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ../ghToolkit -e .
```

These are POSIX-shell commands. On Windows, use the corresponding virtual-environment activation command. When `ghtoolkit` is already available from your configured package source, the sibling editable installation is unnecessary.

### 2. Authenticate

Use an existing GitHub CLI session:

```bash
gh auth login
```

Alternatively, export a token with access to the configured repositories:

```bash
export GITHUB_TOKEN="your-github-token"
```

The authentication helper checks `GITHUB_TOKEN`, then `GH_TOKEN`, then invokes `gh auth token`. Snapshot-based reports do not require GitHub credentials. See [`status_reporter_auth`](src/status_reporter_auth/__init__.py).

### 3. Configure

Create `worked-task.json`:

```json
{
  "repositories": ["owner/repo-one", "owner/repo-two"],
  "author": "your-github-login",
  "timezone": "Asia/Karachi",
  "shift_start": "11:00",
  "shift_end": "20:00",
  "day_start": "06:00",
  "ai": false
}
```

Replace the repository names, author, and shift with your own values. The CLI does **not** discover `worked-task.json` automatically: pass `--config` or export `WORKED_TASK_CONFIG`.

### 4. Generate a report

```bash
# Current reporting day, using the configured timezone and cutoff.
worked-task --config worked-task.json

# A specific reporting day.
worked-task 2026-10-24 --config worked-task.json

# Save the report and export PR evidence as JSONL.
worked-task 2026-10-24 --config worked-task.json \
  --output reports/2026-10-24.txt \
  --chunks-output reports/2026-10-24-prs.jsonl
```

To avoid repeating the configuration flag:

```bash
export WORKED_TASK_CONFIG="$PWD/worked-task.json"
worked-task
```

**Use `worked-task` for office reports.** In the current Makefile, `make today`, `make yesterday`, and `make extract` run the legacy JSON extractor instead.

## Configuration

Configuration is loaded from the file specified by `--config`, or from `WORKED_TASK_CONFIG` when the flag is absent. Supplied CLI values override their corresponding JSON values. Relative paths resolve from the current working directory, not from the configuration file's directory.

```json
{
  "repositories": ["owner/repo"],
  "author": "your-login",
  "author_aliases": ["alternate-login"],
  "timezone": "Asia/Karachi",
  "shift_start": "11:00",
  "shift_end": "20:00",
  "day_start": "06:00",
  "workers": 2,
  "manual_tasks": "tasks.json",
  "ai": false,
  "ai_failure": "raise"
}
```

`repositories`, `author`, `shift_start`, and `shift_end` must be supplied. The reporting defaults are `timezone: "UTC"`, `day_start: "00:00"`, and `workers: 1`; actual shift hours have no inferred defaults. Leave out `manual_tasks` when no task file is needed.

See [`configuration loading`](config/config.py) and [`application configuration`](src/utils/application.py).

### Reporting day and overtime

The reporting window includes its start and excludes its end. With `day_start: "06:00"`, the report for October 24 covers October 24 at 06:00 through, but not including, October 25 at 06:00 in the configured timezone.

The regular shift also includes its start and excludes its end:

```text
Example: Asia/Karachi, shift 11:00–20:00

10:59  → overtime
11:00  → regular shift
19:59  → regular shift
20:00  → overtime
```

An overnight shift such as 22:00–06:00 is supported when the reporting-day cutoff allows the entire shift to fit inside the reporting window. For example, a 06:00 cutoff includes the following day's 02:00 activity in that shift.

Shift start and end must differ. Nonexistent daylight-saving boundary times are rejected; ambiguous boundary times use their first occurrence. See [`ReportSchedule`](src/report/data_classes/report_schedule.py).

### Manual tasks

Use a JSON array with a unique `id`, a nonempty `title`, and an offset-aware `completed_at`. `description` is optional.

```json
[
  {
    "id": "planning-2026-10-24",
    "title": "Sprint planning meeting",
    "completed_at": "2026-10-24T14:30:00+05:00",
    "description": "Discussed priorities and assigned follow-up work."
  }
]
```

```bash
worked-task 2026-10-24 --config worked-task.json --manual-tasks tasks.json
```

Duplicate IDs are rejected. Tasks outside the reporting window are excluded. Date-only and timezone-free completion timestamps are not accepted. A manual task records supplied information; it is not independent verification that the work occurred.

See [`manual-task parsing`](config/config.py), [`ManualTask`](src/report/data_classes/manual_task.py), and [`ReportService`](src/report/service/report_service.py).

## CLI Reference

```text
worked-task [date] [options]
status-report [date] [options]    # equivalent installed entry point
```

From an installed editable checkout, `python -m src` is also available when run from the repository root.

| Argument or option | Behavior |
| --- | --- |
| `date` | Optional `YYYY-MM-DD`; defaults to the configured reporting day. The primary CLI does not accept the literals `today` or `yesterday`. |
| `--config PATH` | JSON configuration file; otherwise uses `WORKED_TASK_CONFIG`. |
| `--repo owner/repo` | Repository override; repeat to supply multiple repositories. |
| `--author LOGIN` | Report author override. |
| `--alias LOGIN` | Additional author alias; repeat as needed. |
| `--timezone TZ` | IANA timezone, such as `Asia/Karachi`. |
| `--shift-start HH:MM` | Local shift start. |
| `--shift-end HH:MM` | Local shift end. |
| `--day-start HH:MM` | Local reporting-day cutoff. |
| `--workers N` | Repository-collection parallelism; CLI help advertises 1–8. Collection behavior is delegated to `ghToolkit`. This does not parallelize AI summaries. |
| `--manual-tasks PATH` | Manual-task JSON file. |
| `--snapshot PATH` | Collect activity from a compatible saved `ghToolkit` snapshot instead of live GitHub. |
| `--ai` | Enable Gemini summaries. This may send private repository content to the provider. |
| `--model NAME` | Preferred Gemini model; overrides the configured model. |
| `--ai-failure MODE` | `raise` by default, or `keep-raw` for failures during summarization. |
| `--format office` | Only `office` is supported. |
| `--output PATH` | Replace the destination report file through a temporary file; otherwise print to stdout. |
| `--chunks-output PATH` | Export one PR chunk per JSONL line; non-PR chunks are omitted. |

Each output file is replaced individually. The report and JSONL export are **not** a single transaction, and simultaneous runs targeting the same path can overwrite one another. Use distinct output paths for independent runs.

Source: [`CLI parser and output handling`](src/cli/commands.py).

## Programmatic API

### Generate and format a report

```python
from config import load_configuration
from utils import format_office_status, generate_report

config = load_configuration("worked-task.json")
report = generate_report(config, "2026-10-24")
text = format_office_status(report)
print(text, end="")
```

### Inject a custom summarizer

A summarizer implements `summarize(chunk) -> str`. The chunk title is available as `chunk.title`.

```python
from report.data_classes import ReportChunk
from utils import generate_report


class TitleSummarizer:
    def summarize(self, chunk: ReportChunk) -> str:
        # A minimal interface example, not an independently verified summary.
        return chunk.title


report = generate_report(config, "2026-10-24", summarizer=TitleSummarizer())
```

An injected summarizer does not require `ai: true`. The caller owns the lifecycle of an injected client or summarizer. See [`generate_report`](src/utils/application.py).

### Replay a saved snapshot

```python
report = generate_report(
    {**config, "snapshot": "activity-snapshot.json", "ai": False},
    "2026-10-24",
)
```

Use a snapshot produced by a compatible `ghToolkit` version for the requested author and reporting window. Snapshot replay bypasses live GitHub collection; enabling AI can still cause network requests. Replay demonstrates consistency with saved data, not that the data is current.

## AI Summaries

AI is disabled unless enabled through configuration or `--ai`. The bundled implementation uses Gemini; other behavior can be supplied through an injected summarizer.

Install the optional dependency and export credentials explicitly:

```bash
python -m pip install -e '.[ai]'
export GEMINI_API_KEY="your-api-key"
export GEMINI_MODEL="your-available-gemini-model"

worked-task 2026-10-24 --config worked-task.json --ai
```

Replace the model placeholder with an identifier available to your account. `GOOGLE_API_KEY` is also recognized. A checked-in model registry is not evidence of current availability or free access, so this README does not promise either.

The summarizer may try alternative models after certain failures, even when a preferred model was supplied. Treat `--model` as a preference, not an exclusive model restriction.

**Privacy:** PR titles, descriptions, messages, and comments may be included in provider requests. Review the data and your organization's policies before enabling AI or sharing exported chunks.

`--ai-failure keep-raw` retains the original activity if a summarization call fails and adds a warning to `DailyReport.warnings`. The current CLI does not display that warnings collection. Initialization or configuration failures can still stop the run.

Do not rely on copying `.env.example` alone: automatic `.env` loading depends on the optional `python-dotenv` module, which is not declared in this package's dependencies. Explicit environment variables avoid that dependency.

Implementation: [`GeminiSummarizer`](src/ai/summarizer.py), [`environment/model helpers`](src/utils/models.py), and [`summary orchestration`](src/report/service/report_service.py).

## Validation

Validation is an explicit Python API step. A successful CLI exit means report generation completed; it does not mean these checks passed.

```python
from validator import FactualValidator, StrictFormatValidator

format_result = StrictFormatValidator.validate(text)
factual_result = FactualValidator.validate(text, report)

print("Format valid:", format_result.is_valid)
print("Format failures:", format_result.failed_rules)
print("Source consistency (%):", factual_result.source_consistency_percent)
print("Factual violations:", factual_result.violations)

if not format_result.is_valid or not factual_result.is_valid:
    raise ValueError("Review validation failures before publishing the report.")
```

`StrictFormatValidator` checks the status header, supported section labels, bullet conventions, overtime marker, and other formatting rules.

`FactualValidator` checks the text against the activity-backed rendering and associates claims with source chunks. Its `source_consistency_percent` measures supported claims among evaluated claims, **not** the percentage of all physical lines and **not** independently verified real-world truth. `fact_support_percent` remains a legacy alias for that value.

AI-generated PR summaries are marked as requiring independent review. AI review-feedback claims also have an explicit verification check; merely reproducing the generated wording does not establish that a finding is correct. There is no documented CLI approval workflow for clearing these checks.

A source-consistent report can still repeat an incorrect commit message or an unverified review claim. Review the code, evidence, and measurements before publishing claims about correctness, performance, or impact.

Implementation: [`format validator`](src/validator/strict_format_validator.py), [`factual validator`](src/validator/factual_validator.py), and [`validation result types`](src/validator/data_classes/).

## Architecture

```text
workedTask/
├── config/                 # Configuration loading and schedule construction
├── src/
│   ├── cli/                # worked-task and status-report entry points
│   ├── report/             # ReportService and report data classes
│   ├── ai/                 # Summarizer protocol and Gemini implementation
│   ├── validator/          # Structural and source-consistency validators
│   ├── utils/              # Application orchestration, formatting, prompts
│   ├── status_reporter_auth/ # Token resolution; GitHub CLI auth fallback
│   ├── extractors/         # Legacy JSON extraction path
│   └── constants.py        # Report constants and model preference registry
├── docs/
│   └── backend-pr-review.md
├── tests/
├── Makefile
└── pyproject.toml          # Distribution: status-reporter, version 0.2.0
```

The primary reporting path delegates collection to `GitHubHub.collect_daily_activity`. The legacy extractor also uses `ghToolkit`, but accesses client internals and runner-based operations. Do not interpret the architecture test as proving that every package path is free of shell-backed collection: it scans a selected set of directories.

### Attribution and freshness

Merge attribution uses `merged_by` metadata, not a merge commit's author. Unknown merge metadata must remain unknown. Merge status describes the data available at collection or snapshot time, not necessarily the state at the end of the historical workday.

Submitted review states and event metadata remain in the activity data. The office report may summarize review outcomes rather than print every event's exact state, reviewer, timestamp, and URL. A comment is not approval, and an approval does not establish that later commits were reviewed.

See [`report chunks`](src/report/data_classes/report_chunk.py), [`review rendering`](src/utils/format.py), and [`architecture tests`](tests/test_cli_architecture.py).

## Development

Install the development dependencies into the active environment:

```bash
python -m pip install -e '.[dev]'

# Exclude the explicitly live/local-repository extraction tests.
python -m pytest --ignore=tests/extractors/test_live_extraction.py

python -m ruff check .
python -m ruff format --check .
```

Some architecture tests also require the sibling `ghToolkit` source checkout, not just an installed wheel. The full default test suite includes tests that depend on live/local repository setup; do not treat `make test` as an unconditional offline command.

`make lint`, `make format`, and `make clean` provide development shortcuts. Legacy extraction, demo, and project-management Make targets are not a substitute for the current CLI reference.

## Current Limitations

The office formatter includes project-specific naming rules, defaulting to `HR-Tool` and recognizing `Foster Ferret`; it is not a generic configurable project-template engine. Changing project naming may also require validator changes.

The package does not schedule daily execution, benchmark backend PRs, calculate production impact, or prove source claims true. Those responsibilities require separate automation, evidence, and review.

For the review method, use the [Backend PR Review Guide](docs/backend-pr-review.md). For the documentation corrections and verification limits in this revision, see [Review Notes](docs/review-notes.md).
