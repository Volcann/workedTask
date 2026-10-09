"""Tests for StatusReportFormatter ensuring exact alignment with expected report formats."""

from __future__ import annotations

from shared.demo_data import (
    get_demo_report_1,
    get_demo_report_2,
    get_demo_report_3,
)
from presentation.formatter import StatusReportFormatter
from models.models import (
    BranchActivity,
    CommitInfo,
    DailyReport,
    ProjectActivity,
    ReviewInfo,
)


def test_format_demo_1_exact() -> None:
    report = get_demo_report_1()
    formatter = StatusReportFormatter()
    out = formatter.format_report(report)

    assert "STATUS (11-SEP-2026)" in out
    assert "HR-Tool" in out
    assert "Backend PR:" in out
    assert "HMT-258 | Add search and natural sorting to device mappings" in out
    assert "-> PR#348 -> Added search and natural sorting" in out
    assert "-> Tested the command." in out
    assert "HTM-228: feat - adopt AXI guidelines" in out
    assert "Frontend PR:" in out
    assert "HMT-258: BE | Employee Unmapping & Attendance Handling Issues" in out
    assert "-> PR#275 -> Refactored mapped/unmapped" in out


def test_format_demo_2_exact() -> None:
    report = get_demo_report_2()
    formatter = StatusReportFormatter()
    out = formatter.format_report(report)

    assert "STATUS (16-SEP-2026)" in out
    assert "HR-Tool" in out
    assert "Reviewed PRs:" in out
    assert "-> MB-228: Payroll run -> PR#359" in out
    assert "MB-228: Payroll run" in out
    assert "-> PR#359 -> Contributed authored commit(s) to this PR." in out
    assert "-> Machine Logs API: Added missing employee profile pictures" in out
    assert "HTM-211 | Reorganizes shift services" in out
    assert "-> Edge Case Identified:" in out
    assert "HTM-282 | Enhance Leave Request Validation" in out
    assert "-> Please debug the device issue." in out


def test_format_demo_3_exact() -> None:
    report = get_demo_report_3()
    formatter = StatusReportFormatter()
    out = formatter.format_report(report)

    assert "STATUS (22-SEP-2026)" in out
    assert "HR-Tool" in out
    assert "HMT-291 | Backend issues" in out
    assert "-> PR#382 -> Resolved comments." in out
    assert "-> Tested the platform. Deleted users are accessing endpoints fixed inside #385." in out
    assert (
        "HMT-273 | Filter soft-deleted employees and replace string literals with enum choices"
        in out
    )
    assert "HMT-273 | Reusable Approval Configuration API & Workflow Engine" in out
    assert "-> Created the end-to-end design of configuration mockups" in out


def test_format_branch_activity() -> None:
    act = ProjectActivity(
        project_name="HR-Tool",
        category="Backend",
        owner="MoneyTalks-vantaggio",
        repo="backend",
        branch_commits=[
            BranchActivity(
                branch_name="feature/HMT-299-db-cache",
                commits=[
                    CommitInfo(
                        sha="abc1234",
                        message="feat: configure Redis session caching for high-load endpoints",
                    ),
                    CommitInfo(
                        sha="def5678",
                        message="test: add unit tests for Redis cache invalidation",
                    ),
                ],
            )
        ],
    )
    report = DailyReport(
        target_date=get_demo_report_1().target_date,
        date_display="11-SEP-2026",
        projects=[act],
    )
    formatter = StatusReportFormatter()
    out = formatter.format_report(report)

    assert "Inside branch feature/HMT-299-db-cache:" in out
    assert "-> feat: configure Redis session caching for high-load endpoints" in out
    assert "-> test: add unit tests for Redis cache invalidation" in out


def test_format_reviewed_prs_with_comments() -> None:
    act = ProjectActivity(
        project_name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        reviewed_prs=[
            ReviewInfo(
                pr_number=387,
                pr_title="HTM-219 | Simplify approval amount modification",
                reviewer="Volcann",
                state="APPROVED",
                comments=["I have fully tested from FE no breaking changes."],
            )
        ],
    )
    report = DailyReport(
        target_date=get_demo_report_1().target_date,
        date_display="23-SEP-2026",
        projects=[act],
    )
    formatter = StatusReportFormatter()
    out = formatter.format_report(report)

    assert "Reviewed PRs:" in out
    assert "-> HTM-219 | Simplify approval amount modification -> PR#387" in out
    assert "-> I have fully tested from FE no breaking changes." in out
