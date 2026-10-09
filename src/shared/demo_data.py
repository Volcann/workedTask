from __future__ import annotations

from datetime import date

from models.models import (
    DailyReport,
    ProjectActivity,
    PullRequestInfo,
    ReviewInfo,
)


def get_demo_report_1() -> DailyReport:
    target_date = date(2026, 9, 11)

    backend_act = ProjectActivity(
        project_name="HR-Tool",
        category="Backend",
        owner="MoneyTalks-vantaggio",
        repo="backend",
        own_prs=[
            PullRequestInfo(
                number=348,
                title="HMT-258 | Add search and natural sorting to device mappings",
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "PR#348 -> Added search and natural sorting to device-user listings and unmapped-punch APIs with deterministic ordering, updated OpenAPI docs, and full test coverage."
                ],
            ),
            PullRequestInfo(
                number=349,
                title="HMT-258 | Updated permission checks for org super-admins and admins",
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "PR#349 -> Restricted org super-admin permissions to evaluate strictly against ADMIN_PERMISSION_CODENAMES and added test coverage confirming org admins lack punch approval access.",
                    "Tested the command.",
                ],
            ),
            PullRequestInfo(
                number=350,
                title="HTM-228: feat - adopt AXI guidelines and gh-axi for token-efficient GitHub operations",
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "PR#350 -> Optimized AI agent workflows by integrating the gh-axi standard into AGENTS.md, replacing bulky JSON outputs with token-efficient formatting. Reduced token overhead by 32–55% across GitHub operations, eliminating context flooding and significantly lowering the risk of LLM hallucinations. Benchmarked and shared comparative performance reports in this PR summary, which can be revalidated later. The results demonstrate the efficiency gains of gh-axi over legacy JSON outputs."
                ],
            ),
        ],
    )

    frontend_act = ProjectActivity(
        project_name="HR-Tool",
        category="Frontend",
        owner="MoneyTalks-vantaggio",
        repo="frontend",
        own_prs=[
            PullRequestInfo(
                number=275,
                title="HMT-258: BE | Employee Unmapping & Attendance Handling Issues",
                category="Frontend",
                project_name="HR-Tool",
                bullets=[
                    "PR#275 -> Refactored mapped/unmapped device user tables with debounced search, improved loading states, and refreshed UI styling."
                ],
            )
        ],
    )

    return DailyReport(
        target_date=target_date,
        date_display="11-SEP-2026",
        projects=[backend_act, frontend_act],
    )


def get_demo_report_2() -> DailyReport:
    target_date = date(2026, 9, 16)

    act = ProjectActivity(
        project_name="HR-Tool",
        category="Backend",
        owner="MoneyTalks-vantaggio",
        repo="backend",
        reviewed_prs=[
            ReviewInfo(
                pr_number=359,
                pr_title="MB-228: Payroll run",
                reviewer="Volcann",
                state="APPROVED",
                project_name="HR-Tool",
            )
        ],
        foreign_contributions=[
            PullRequestInfo(
                number=359,
                title="MB-228: Payroll run",
                is_own=False,
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "PR#359 -> Contributed authored commit(s) to this PR.",
                    "Machine Logs API: Added missing employee profile pictures to the /api/v1/devices/machine-logs/ response payload.",
                    "Timesheet Attendance (HTM-228): Excluded soft-deleted users by removing include_soft_deleted; regression tests and Ruff passed (Committed: fd3cfbc).",
                    "Tardiness vs. Absence Logic: Filtered absent users out of tardiness calculations inside compute_organization_tardiness_records() while keeping absent_count stats accurate; 30 tests and Ruff passed (Pending commit/push).",
                    "Increases total test coverage to over 92% by adding comprehensive test suites across permissions, reporting, and accounts, while successfully implementing and validating core payroll processing, compensation APIs, and benefit enrollments.",
                ],
            )
        ],
        own_prs=[
            PullRequestInfo(
                number=375,
                title="HTM-211 | Reorganizes shift services",
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "PR#375 -> Restructures shift and attendance services into isolated domain packages for gap filling, persistence, and punch requests, resolving circular dependencies while preserving existing API behavior.",
                    "",
                    'Edge Case Identified: While refactoring and testing, found that a database constraint blocks duplicate punch requests ("already punched"). Need product/business logic confirmation on whether users should be allowed to submit a punch request for that same time.',
                ],
            ),
            PullRequestInfo(
                number=376,
                title="HTM-282 | Enhance Leave Request Validation",
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "#376 -> Refactors leave duration logic to accurately calculate effective end times for partial and full-day leaves, adding tests to validate maximum consecutive day policy enforcement and unauthorized request handling.",
                    "",
                    "Please debug the device issue. I shared the details of the successfully connected device with Moin.",
                ],
            ),
        ],
    )

    return DailyReport(
        target_date=target_date,
        date_display="16-SEP-2026",
        projects=[act],
    )


def get_demo_report_3() -> DailyReport:
    target_date = date(2026, 9, 22)

    act = ProjectActivity(
        project_name="HR-Tool",
        category="Backend",
        owner="MoneyTalks-vantaggio",
        repo="backend",
        own_prs=[
            PullRequestInfo(
                number=382,
                title="HMT-291 | Backend issues",
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "PR#382 -> Resolved comments.",
                    "Bank fields now trigger field-access lookup in employee.py.",
                    "Submitted bank fields are enforced through enforce_writable_fields() in [onboard.py (line 144).",
                    "The five-field regression test now passes.",
                    "Removed docs/development/execution-state/benefit-claim-employee-scope.md.",
                    "Preserved unrelated changes.",
                    "",
                    "Tested the platform. Deleted users are accessing endpoints fixed inside #385.",
                ],
            ),
            PullRequestInfo(
                number=385,
                title="HMT-273 | Filter soft-deleted employees and replace string literals with enum choices",
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "#385 -> Enforces soft-delete filtering across all employee and manager-facing querysets to securely exclude deleted users, and refactors the codebase to replace hard-coded string literals with centralized Django TextChoices enums."
                ],
            ),
            PullRequestInfo(
                number=384,
                title="HMT-273 | Reusable Approval Configuration API & Workflow Engine",
                category="Backend",
                project_name="HR-Tool",
                bullets=[
                    "#384 -> Implements REST endpoints and an atomic service pipeline for reusable approval workflows, validating strict business rules for tenant-wide scoping, contiguous step sequences, and cross-step approver exclusivity, while refactoring test client fixtures.",
                    "",
                    "Created the end-to-end design of configuration mockups, finalizing the user flow and securing team alignment through strategic validation.",
                ],
            ),
        ],
    )

    return DailyReport(
        target_date=target_date,
        date_display="22-SEP-2026",
        projects=[act],
    )
