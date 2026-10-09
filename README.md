# GitHub Daily Status Reporter (CLI)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tested with: pytest](https://img.shields.io/badge/tested%20with-pytest-blue.svg)](https://docs.pytest.org/)
[![Tooling: uv](https://img.shields.io/badge/tooling-uv-purple.svg)](https://github.com/astral-sh/uv)

An enterprise-grade Python CLI tool that automates compiling daily engineering status updates directly from GitHub. It queries commits, pull requests, reviews, foreign contributions, and branch activities for any target date, groups them by project and domain (`Backend PR`, `Frontend PR`, `Reviewed PRs`), formats them into clean executive bullet points, and exports the final report directly to a separate `.txt` file.

---

## 🌟 Key Features

1. **Date-Driven Activity Retrieval**:
   - Accepts flexible date formats: `11-SEP-2026`, `2026-09-11`, `today`, `yesterday`, etc.
   - Automatically queries GitHub for all commits authored, PRs created, and PRs reviewed on that day.
2. **Comprehensive Contribution Mapping**:
   - **Own PRs**: Full PR details, titles, tickets, and associated commit summaries.
   - **Foreign PR Contributions**: Detects commits authored by the configured contributor in another teammate's PR and formats them as:
     `-> PR#<num> -> Contributed authored commit(s) to this PR.`
   - **Conservative Attribution**: Mixed-author PRs are summarized only from commits attributed to the configured contributor. If no authored commit evidence is available, the report records the PR activity without claiming its implementation.
   - **Branch Commits**: Identifies standalone commits pushed to a branch not yet tied to a PR:
     `Inside branch <branch_name>: -> <commit message>`
   - **Reviewed PRs**: Tracks PRs reviewed and approved/commented on during that day.
3. **Multi-Project & Frontend/Backend Domain Separation**:
   - Categorizes updates by project (e.g. `HR-Tool`) and domain (`Backend PR:`, `Frontend PR:`).
4. **Dynamic Configuration (`projects.json`)**:
   - Configure unlimited repositories with custom project names, categories, and author handles.
   - CLI commands to dynamically list, add, and remove repositories.
5. **Dual Report Delivery**:
   - Prints formatted status report directly to the terminal stdout.
   - Automatically saves the report separately to a `.txt` file (e.g., `reports/status_report_11_SEP_2026.txt` or custom `--output`).
6. **AI-Enhanced & Deterministic Modes**:
   - Supports Gemini (`google-genai`) for executive summarization when `GEMINI_API_KEY` is present.
   - Robust deterministic rule-based engine as fallback for offline or zero-API environments.

---

## 🚀 Quickstart & Installation

### Using `uv` (Recommended)

```bash
# Clone the repository
git clone https://github.com/Volcann/workedTask.git
cd workedTask

# Create virtual environment and install with uv
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Using standard `pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 📋 Configuration (`projects.json`)

The CLI dynamically reads repository mappings from `projects.json`.

```json
[
  {
    "name": "HR-Tool",
    "category": "Backend",
    "owner": "MoneyTalks-vantaggio",
    "repo": "backend",
    "author": "Volcann"
  },
  {
    "name": "HR-Tool",
    "category": "Frontend",
    "owner": "MoneyTalks-vantaggio",
    "repo": "frontend",
    "author": "Volcann"
  }
]
```

### Managing Projects via CLI

```bash
# List all active projects
status-reporter projects list

# Add or update a project
status-reporter projects add --name "HR-Tool" --owner "MoneyTalks-vantaggio" --repo "backend" --category "Backend" --author "Volcann"

# Remove a project
status-reporter projects remove --owner "MoneyTalks-vantaggio" --repo "backend"
```

---

## 💻 CLI Usage

### Generate Daily Report for a Date

```bash
# Query status for a specific date
status-reporter --date 11-SEP-2026

# Query today or yesterday
status-reporter --date today
status-reporter --date yesterday

# Filter by project or category
status-reporter --date 11-SEP-2026 --project "HR-Tool"
status-reporter --date 11-SEP-2026 --category "Backend"

# Specify a custom report output file
status-reporter --date 11-SEP-2026 --output custom_status.txt

# Run with default Gemini 3.5 Flash Lite
status-reporter --date 11-SEP-2026

# Run offline without AI API calls
status-reporter --date 11-SEP-2026 --no-ai

# Clean unused reports (keeps active/latest report)
status-reporter clean-reports

# Clean all reports
status-reporter clean-reports --all
```

### ⚡ Quick Execution with `make`

```bash
# Run for a specific day (defaults to gemini-2.5-flash-lite)
make status DATE=11-SEP-2026

# Alias
make run DATE=16-SEP-2026

# Override model if desired
make status DATE=11-SEP-2026 MODEL=gemini-2.5-flash-lite

# Run for today or yesterday
make today
make yesterday

# Filter by project or category
make status DATE=11-SEP-2026 PROJECT=HR-Tool
make status DATE=11-SEP-2026 CATEGORY=Backend

# Run offline without AI API calls
make status DATE=11-SEP-2026 NO_AI=1

# Clean unused reports (keeps active report currently in use)
make clean-reports

# Clean all generated reports
make clean-reports ALL=1

# Keep a specific report and delete all others
make clean-reports KEEP=24-SEP-2026

# Run canonical prompt demos
make demo1
make demo2
make demo3
```

---

## 📄 Output Report Format Examples

### Example 1 (Frontend & Backend PRs)
```text
STATUS (11-SEP-2026)
HR-Tool

Backend PR:
HMT-258 | Add search and natural sorting to device mappings
-> PR#348 -> Added search and natural sorting to device-user listings and unmapped-punch APIs with deterministic ordering, updated OpenAPI docs, and full test coverage.

HMT-258 | Updated permission checks for org super-admins and admins
-> PR#349 -> Restricted org super-admin permissions to evaluate strictly against ADMIN_PERMISSION_CODENAMES and added test coverage confirming org admins lack punch approval access.
-> Tested the command.

HTM-228: feat - adopt AXI guidelines and gh-axi for token-efficient GitHub operations
-> PR#350 -> Optimized AI agent workflows by integrating the gh-axi standard into AGENTS.md, replacing bulky JSON outputs with token-efficient formatting. Reduced token overhead by 32–55% across GitHub operations, eliminating context flooding and significantly lowering the risk of LLM hallucinations. Benchmarked and shared comparative performance reports in this PR summary, which can be revalidated later. The results demonstrate the efficiency gains of gh-axi over legacy JSON outputs.

Frontend PR:
HMT-258: BE | Employee Unmapping & Attendance Handling Issues
-> PR#275 -> Refactored mapped/unmapped device user tables with debounced search, improved loading states, and refreshed UI styling.
```

### Example 2 (Reviewed PRs & Foreign Contributions)
```text
STATUS (16-SEP-2026)
HR-Tool
Reviewed PRs:
-> MB-228: Payroll run -> PR#359

MB-228: Payroll run
-> PR#359 -> Contributed authored commit(s) to this PR.
-> Machine Logs API: Added missing employee profile pictures to the /api/v1/devices/machine-logs/ response payload.
-> Timesheet Attendance (HTM-228): Excluded soft-deleted users by removing include_soft_deleted; regression tests and Ruff passed (Committed: fd3cfbc).
-> Tardiness vs. Absence Logic: Filtered absent users out of tardiness calculations inside compute_organization_tardiness_records() while keeping absent_count stats accurate; 30 tests and Ruff passed (Pending commit/push).
-> Increases total test coverage to over 92% by adding comprehensive test suites across permissions, reporting, and accounts, while successfully implementing and validating core payroll processing, compensation APIs, and benefit enrollments.

HTM-211 | Reorganizes shift services
-> PR#375 -> Restructures shift and attendance services into isolated domain packages for gap filling, persistence, and punch requests, resolving circular dependencies while preserving existing API behavior.

-> Edge Case Identified: While refactoring and testing, found that a database constraint blocks duplicate punch requests ("already punched"). Need product/business logic confirmation on whether users should be allowed to submit a punch request for that same time.

HTM-282 | Enhance Leave Request Validation
-> #376 -> Refactors leave duration logic to accurately calculate effective end times for partial and full-day leaves, adding tests to validate maximum consecutive day policy enforcement and unauthorized request handling.

-> Please debug the device issue. I shared the details of the successfully connected device with Moin.
```

---

## 🧪 Testing & Code Quality

Run tests using `pytest`:

```bash
pytest
```

Run linter and code formatter checks using `ruff`:

```bash
ruff check .
ruff format --check .
```

Run pre-commit hooks:

```bash
pre-commit run --all-files
```

---

## 📁 Repository Structure

```
workedTask/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI workflow
├── .pre-commit-config.yaml    # Pre-commit configuration (ruff, trailing-whitespace, etc.)
├── pyproject.toml             # Modern PEP 517/621 build and tool definitions
├── projects.json              # Dynamic project configurations
├── README.md                  # Comprehensive documentation
├── reports/                   # Saved daily status report .txt files
├── src/
│   └── status_reporter/
│       ├── __init__.py        # Package root and version
│       ├── __main__.py        # python -m status_reporter entrypoint
│       ├── ai_enhancer.py     # Gemini AI summarization engine
│       ├── cli.py             # Rich CLI argument parser and execution handler
│       ├── collector.py       # Activity scanner for PRs, commits, reviews, branches
│       ├── config.py          # projects.json loader, dynamic manager, and env loader
│       ├── demo_data.py       # Canonical reference datasets for prompt examples
│       ├── formatter.py       # Canonically styled report renderer
│       ├── models.py          # Strongly typed domain dataclasses
│       └── utils.py           # Date parsers, ticket regex, and string cleaners
└── tests/
    ├── conftest.py            # Shared fixtures
    ├── test_cli.py            # CLI commands, options, and file output tests
    ├── test_collector.py      # Aggregation, foreign contribution, and branch tests
    ├── test_config.py         # Dynamic projects.json configuration tests
    ├── test_date_utils.py     # Multi-format date parsing and text cleaning tests
    ├── test_formatter.py      # Formatting fidelity tests for Examples 1, 2, and 3
```
