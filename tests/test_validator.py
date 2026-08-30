"""Tests for status_reporter.validator (Validation Pipeline)."""

from __future__ import annotations

from datetime import date

from status_reporter.models import (
    CommitInfo,
    DailyReport,
    ProjectActivity,
    PullRequestInfo,
)
from status_reporter.validator import StatusValidator


def test_validator_removes_hallucinated_endpoint_claims() -> None:
    """Validator strips fictitious endpoints and delivery testing claims without API files."""
    pr = PullRequestInfo(
        number=393,
        title="HMT-215: BE | Implement In App Notifications",
        author_login="Volcann",
        commits=[
            CommitInfo(
                sha="50b3cbc160a349365ea907ca0e5479469096d9b8",
                message="HMT-215: BE | Implement In App Notifications\n\nAdded Device and Notification models",
                author_name="Volcann",
                files=[
                    "hr_tool/notifications/models/device.py",
                    "hr_tool/notifications/models/notification.py",
                    "hr_tool/notifications/admin.py",
                    "hr_tool/notifications/choices.py",
                    "hr_tool/notifications/tests/test_models.py",
                ],
            ),
            CommitInfo(
                sha="42842acc7e367f07882a45d1419bdfafe331bb88",
                message="HMT-215: Update conflict error messages for resource deletion",
                author_name="Volcann",
                files=[
                    "hr_tool/core/views/base.py",
                    "hr_tool/core/tests/test_soft_delete.py",
                ],
            ),
        ],
        author_commits=[
            CommitInfo(
                sha="50b3cbc160a349365ea907ca0e5479469096d9b8",
                message="HMT-215: BE | Implement In App Notifications",
                author_name="Volcann",
                files=[
                    "hr_tool/notifications/models/device.py",
                    "hr_tool/notifications/models/notification.py",
                    "hr_tool/notifications/tests/test_models.py",
                ],
            ),
            CommitInfo(
                sha="42842acc7e367f07882a45d1419bdfafe331bb88",
                message="HMT-215: Update conflict error messages for resource deletion",
                author_name="Volcann",
                files=["hr_tool/core/views/base.py"],
            ),
        ],
        bullets=[
            "PR#393 -> Implemented the backend for in-app notifications.",
            "Added notification creation endpoints, updated user/notification models, and refined conflict error handling.",
            "Tested notification delivery via the new /api/v1/notifications POST endpoint.",
        ],
        category="Backend",
        project_name="HR-Tool",
    )

    activity = ProjectActivity(
        project_name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        own_prs=[pr],
    )
    report = DailyReport(
        target_date=date(2026, 9, 24),
        date_display="24-SEP-2026",
        projects=[activity],
    )

    validator = StatusValidator(verbose=False)
    result = validator.validate_report(report)

    assert result.has_removals
    assert len(result.removed_items) == 2

    # Check reason explanations
    endpoint_item = next(
        item for item in result.removed_items if "/api/v1/notifications" in item.bullet
    )
    assert "fictitious endpoint" in endpoint_item.reason.lower()

    creation_item = next(
        item for item in result.removed_items if "creation endpoints" in item.bullet
    )
    assert "api view, url" in creation_item.reason.lower()

    # The hallucinated bullets should be removed from pr.bullets
    assert not any("/api/v1/notifications" in b for b in pr.bullets)
    assert not any("creation endpoints" in b for b in pr.bullets)


def test_validator_removes_invalid_commit_hash() -> None:
    """Validator removes bullet citing a commit hash that does not exist in author commits."""
    pr = PullRequestInfo(
        number=388,
        title="HMT-273 | Add early checkout grace period support",
        author_login="Volcann",
        commits=[
            CommitInfo(
                sha="e48e7c2f00000000000000000000000000000000",
                message="refactor: remove organization timezone param",
                author_name="Volcann",
            )
        ],
        author_commits=[
            CommitInfo(
                sha="e48e7c2f00000000000000000000000000000000",
                message="refactor: remove organization timezone param",
                author_name="Volcann",
            )
        ],
        bullets=[
            "PR#388 -> Added early checkout grace period support.",
            "Refactored check-in/out functions to remove organization timezone param (Commit: e48e7c2).",
            "Updated docs and tests to clarify UTC evaluation (Commit: badc0de).",
        ],
        category="Backend",
        project_name="HR-Tool",
    )

    activity = ProjectActivity(
        project_name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        own_prs=[pr],
    )
    report = DailyReport(
        target_date=date(2026, 9, 24),
        date_display="24-SEP-2026",
        projects=[activity],
    )

    validator = StatusValidator(verbose=False)
    result = validator.validate_report(report)

    assert result.has_removals
    assert len(result.removed_items) == 1
    assert "badc0de" in result.removed_items[0].reason
    assert not any("badc0de" in b for b in pr.bullets)
    # Valid commit hash e48e7c2 remains
    assert any("e48e7c2" in b for b in pr.bullets)


def test_validator_fallback_when_all_bullets_filtered() -> None:
    """When all bullets fail validation, validator synthesizes grounded fallback from commit headlines."""
    pr = PullRequestInfo(
        number=393,
        title="HMT-215: BE | Implement In App Notifications",
        author_login="Volcann",
        commits=[
            CommitInfo(
                sha="50b3cbc160a349365ea907ca0e5479469096d9b8",
                message="HMT-215: BE | Implement In App Notifications",
                author_name="Volcann",
            )
        ],
        author_commits=[
            CommitInfo(
                sha="50b3cbc160a349365ea907ca0e5479469096d9b8",
                message="HMT-215: BE | Implement In App Notifications",
                author_name="Volcann",
            )
        ],
        bullets=[
            "Tested notification delivery via the new /api/v1/notifications POST endpoint.",
        ],
        category="Backend",
        project_name="HR-Tool",
    )

    activity = ProjectActivity(
        project_name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        own_prs=[pr],
    )
    report = DailyReport(
        target_date=date(2026, 9, 24),
        date_display="24-SEP-2026",
        projects=[activity],
    )

    validator = StatusValidator(verbose=False)
    validator.validate_report(report)

    # Fallback created from real commit headline
    assert len(pr.bullets) == 1
    assert "PR#393 -> HMT-215: BE | Implement In App Notifications" in pr.bullets[0]


def test_validator_format_summary() -> None:
    """Format summary returns clean audit explanation."""
    report = DailyReport(
        target_date=date(2026, 9, 24),
        date_display="24-SEP-2026",
    )
    validator = StatusValidator(verbose=False)
    result = validator.validate_report(report)

    # Empty summary
    assert "All claims verified" in result.format_summary()

    # With removed items
    from status_reporter.models import RemovedItem

    result.removed_items.append(
        RemovedItem(
            target="PR#393",
            project="HR-Tool / Backend",
            bullet="Tested /api/v1/notifications",
            reason="Endpoint does not exist",
        )
    )
    summary = result.format_summary()
    assert "Excluded 1 misleading or low-validation claim(s):" in summary
    assert "PR#393" in summary
    assert "Endpoint does not exist" in summary
