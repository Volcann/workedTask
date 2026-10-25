# workedTask / status-reporter

A report consumer of ghToolkit, **not a GitHub API client**.

The source contains no GitHub API client or shell-based GitHub data collection.
All GitHub collection, association and cleaning is reused from
`GitHubHub.collect_daily_activity`. An architecture test enforces this boundary.
For live reports, credentials come from `GITHUB_TOKEN` or `GH_TOKEN` when set;
otherwise the program runs `gh auth token` through a subprocess to use an existing
GitHub CLI login. If needed, run `gh auth login` once beforehand. Snapshot reports
and injected activity sources do not require GitHub credentials.

The five log categories are PRs, reviewed PRs/comments, standalone branch commits,
issues, and daily extra tasks outside GitHub. Reports are grouped repository-wise
and then PR/issue-wise. Non-GitHub tasks are supplied through a local JSON file.

For each reported PR, the office output links to its repository-specific GitHub
page and shows the merge status from the PR detail endpoint. A submitted review
prints its exact GitHub state (`APPROVED`, `CHANGES_REQUESTED`, or `COMMENTED`),
reviewer, time, and review link when available. PR comments are labeled as
comments and do not imply approval. A merge is attributed to the account in
GitHub's `merged_by` field; a merge commit author is not used as proof of who
merged. Merges by the report author appear as dated PR activity even without a
commit or comment that day. When GitHub merge metadata is unavailable, the
report says so instead of treating the PR as unmerged. Merge status reflects
GitHub when the report was generated; the merge timestamp remains explicit.
An `APPROVED` review records the submitted review state and time; it does not
by itself prove that the reviewer approved later commits pushed to the PR.

Set your actual shift start/end; they have no guessed defaults. Configure a timezone
and reporting-day cutoff. For example, a 06:00 cutoff associates 02:00 on the next
calendar day with the preceding work date, while retaining its full actual date
and offset in the report. After-shift work has the exact marker:

```text
(The task is done in extra time)
```

The regular shift includes its start and excludes its end; activity before the
start or at/after the timezone-aware end is marked as extra time. A
22:00–06:00 overnight shift does not mark 02:00 as overtime. Cutoffs and shifts are
validated; nonexistent DST clock times are rejected, and ambiguous times use the
first occurrence. Date-only and timezone-free manual timestamps are rejected.

Run `worked-task --help` or `python -m src --help` for the CLI. The
positional date accepts YYYY-MM-DD. Configuration JSON may be passed with
`--config` or `WORKED_TASK_CONFIG`; explicit CLI settings override the file. Paths
in configuration are relative to the working directory, not the configuration
file's directory. Output replacement is atomic per file.

The programmatic entry point is:

```python
from utils import format_office_status, generate_report

report = generate_report(
    {
        "repositories": ["owner/repo"],
        "author": "your-login",
        "timezone": "Asia/Karachi",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "day_start": "06:00",
    },
    "2026-10-24",
)
print(format_office_status(report))
```

No AI provider is selected automatically. `--chunks-output` exports exactly one
cleaned PR per JSONL record; `--ai` opts in to the Gemini adapter. API key and model
must be supplied. A custom object implementing `summarize(ReportChunk) -> str` may
be injected into `ReportService.generate` instead. The application always keeps
raw evidence and renders overtime markers itself.

Original workedTask source was absent from the upload and could not be retrieved.
This package implements the attached workflow; it does not claim to preserve
unknown old configuration formats, CLI aliases, or internal imports. The root
Celery adapter now imports this package's explicit programmatic entry point.

## Office Status Reporting

The package includes modules implementing strict office status reporting and factual validation:

- **`status_reporter.office_format`**: Formats daily reports into the exact office format (`STATUS (DD-MMM-YYYY)` -> Project -> Conditional Sections -> `->` bullets).
- **`validator`**: Implements `StrictFormatValidator` (structure, headers, bullets) and `FactualValidator` (evidence linking, PR numbers, commit SHAs, review segregation, overtime isolation).

`FactualValidator` checks whether a status is reproducible from its supplied
`DailyReport` activity snapshot and links each line to a repository-specific
source chunk. Use `result.source_consistency_percent` for the percentage;
the legacy `fact_support_percent` field remains for compatibility. This percentage is
**source consistency**, not a guarantee that a
commit message, PR title, review comment, or AI summary accurately describes
the code or a production deployment. A separate live GitHub and code review is
needed before making an external factual-accuracy claim. Historical generated
reports must be regenerated after formatter or validator changes.

### Shift Baseline (Lahore, Pakistan)
- **Timezone:** `Asia/Karachi`
- **Shift:** 11:00 AM – 8:00 PM PKT (`11:00 <= t < 20:00`)
- **Overtime:** `t < 11:00 OR t >= 20:00 PKT` with mandatory note `(The task is done in extra time)`
- **Duration Policy:** Git event timestamps demonstrate occurrence, not duration. Durations are kept unmanufactured and require confirmed timesheet entry.

