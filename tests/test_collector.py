from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from ghtoolkit.models import CommitInfo, ProjectConfig, PullRequestInfo, ReviewInfo

from collection.collector import ActivityCollector


def test_collector_own_prs(sample_date: date) -> None:
    client_mock = MagicMock()
    # Mock own PR
    own_pr = PullRequestInfo(
        number=348,
        title="HMT-258 | Add search and natural sorting to device mappings",
        body="Added search and natural sorting to device-user listings.",
        author_login="Volcann",
        commits=[
            CommitInfo(
                sha="abc348",
                message="Added search and natural sorting to device-user listings.",
                author_login="Volcann",
            )
        ],
    )
    client_mock.get_user_prs_for_date.return_value = [own_pr]
    client_mock.get_user_commits_for_date.return_value = []
    client_mock.get_user_reviewed_prs_for_date.return_value = []

    collector = ActivityCollector(github_client=client_mock, use_ai=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="MoneyTalks-vantaggio",
        repo="backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    assert len(report.projects) == 1
    act = report.projects[0]
    assert len(act.own_prs) == 1
    assert act.own_prs[0].number == 348
    assert "PR#348 -> Added search and natural sorting" in act.own_prs[0].bullets[0]


def test_collector_foreign_pr_contribution(sample_date: date) -> None:
    client_mock = MagicMock()
    client_mock.get_user_prs_for_date.return_value = []

    # Commit pushed by author
    author_commit = CommitInfo(
        sha="fd3cfbc123",
        message="Timesheet Attendance (HTM-228): Excluded soft-deleted users",
        author_login="Volcann",
    )
    client_mock.get_user_commits_for_date.return_value = [author_commit]

    # Commit belongs to PR #359 owned by someone else
    client_mock.get_commit_pull_requests.return_value = [{"number": 359}]
    foreign_pr = PullRequestInfo(
        number=359,
        title="MB-228: Payroll run",
        author_login="OtherDev",
    )
    client_mock.get_pr_details.return_value = foreign_pr
    client_mock.get_user_reviewed_prs_for_date.return_value = []

    collector = ActivityCollector(github_client=client_mock, use_ai=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="MoneyTalks-vantaggio",
        repo="backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    assert len(report.projects) == 1
    act = report.projects[0]
    assert len(act.foreign_contributions) == 1
    contr = act.foreign_contributions[0]
    assert contr.number == 359
    assert contr.bullets[0] == "PR#359 -> Contributed authored commit(s) to this PR."
    assert "Timesheet Attendance (HTM-228): Excluded soft-deleted users" in contr.bullets[1]


def test_collector_standalone_branch_commits(sample_date: date) -> None:
    client_mock = MagicMock()
    client_mock.get_user_prs_for_date.return_value = []

    standalone_commit = CommitInfo(
        sha="abc12345",
        message="refactor: cleanup unused middleware classes",
        author_login="Volcann",
        branch="feature/cleanup-middleware",
    )
    client_mock.get_user_commits_for_date.return_value = [standalone_commit]
    client_mock.get_commit_pull_requests.return_value = []
    client_mock.get_user_reviewed_prs_for_date.return_value = []

    collector = ActivityCollector(github_client=client_mock, use_ai=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="MoneyTalks-vantaggio",
        repo="backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    assert len(report.projects) == 1
    act = report.projects[0]
    assert len(act.branch_commits) == 1
    branch_act = act.branch_commits[0]
    assert branch_act.branch_name == "feature/cleanup-middleware"
    assert branch_act.commits[0].headline == "refactor: cleanup unused middleware classes"


def test_collector_reviewed_prs(sample_date: date) -> None:
    client_mock = MagicMock()
    client_mock.get_user_prs_for_date.return_value = []
    client_mock.get_user_commits_for_date.return_value = []

    review = ReviewInfo(
        pr_number=359,
        pr_title="MB-228: Payroll run",
        reviewer="Volcann",
        state="APPROVED",
    )
    client_mock.get_user_reviewed_prs_for_date.return_value = [review]

    collector = ActivityCollector(github_client=client_mock, use_ai=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="MoneyTalks-vantaggio",
        repo="backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    assert len(report.projects) == 1
    act = report.projects[0]
    assert len(act.reviewed_prs) == 1
    assert act.reviewed_prs[0].pr_number == 359


def test_collector_merged_pr_and_contributed_stays_on_both_sides(sample_date: date) -> None:
    client_mock = MagicMock()
    commit = CommitInfo(
        sha="a4d24608",
        message="feat: implement soft delete prevention",
        author_login="Volcann",
    )
    client_mock.get_user_commits_for_date.return_value = [commit]
    client_mock.get_commit_pull_requests.return_value = [{"number": 386}]

    pr = PullRequestInfo(
        number=386,
        title="HMT-273 | Soft delete fix inside config",
        author_login="Volcann",
    )
    client_mock.get_user_prs_for_date.return_value = [pr]
    client_mock.get_pr_details.return_value = pr

    review = ReviewInfo(
        pr_number=386,
        pr_title="HMT-273 | Soft delete fix inside config",
        reviewer="Volcann",
        state="APPROVED",
    )
    client_mock.get_user_reviewed_prs_for_date.return_value = [review]

    collector = ActivityCollector(github_client=client_mock, use_ai=False, verbose=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    act = report.projects[0]

    # Stays on both sides!
    assert len(act.reviewed_prs) == 1
    assert act.reviewed_prs[0].pr_number == 386

    assert len(act.own_prs) == 1
    assert act.own_prs[0].number == 386


def test_collector_reviewed_pr_comments_detected(sample_date: date) -> None:
    client_mock = MagicMock()
    client_mock.get_user_prs_for_date.return_value = []
    client_mock.get_user_commits_for_date.return_value = []

    review = ReviewInfo(
        pr_number=387,
        pr_title="HTM-219 | Simplify approval amount modification",
        reviewer="Volcann",
        state="APPROVED",
    )
    client_mock.get_user_reviewed_prs_for_date.return_value = [review]
    client_mock.get_pr_user_comments.return_value = [
        "I have fully tested from FE no breaking changes."
    ]

    collector = ActivityCollector(github_client=client_mock, use_ai=False, verbose=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    assert len(report.projects) == 1
    act = report.projects[0]
    assert len(act.reviewed_prs) == 1
    assert act.reviewed_prs[0].pr_number == 387
    assert act.reviewed_prs[0].comments == ["I have fully tested from FE no breaking changes."]


def test_collector_pr_comments_included_in_bullets(sample_date: date) -> None:
    client_mock = MagicMock()
    commit = CommitInfo(
        sha="db5db2d",
        message="HMT-273 | feat: update attendance metrics",
        author_login="Volcann",
    )
    client_mock.get_user_commits_for_date.return_value = [commit]
    client_mock.get_commit_pull_requests.return_value = [{"number": 388}]

    pr = PullRequestInfo(
        number=388,
        title="HMT-273 | Add early checkout grace period support",
        author_login="Volcann",
        is_own=True,
    )
    client_mock.get_user_prs_for_date.return_value = [pr]
    client_mock.get_pr_details.return_value = pr
    client_mock.get_user_reviewed_prs_for_date.return_value = []
    client_mock.get_pr_user_comments.return_value = ["Tested the command and boundary conditions."]

    collector = ActivityCollector(github_client=client_mock, use_ai=False, verbose=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    assert len(report.projects) == 1
    act = report.projects[0]
    assert len(act.own_prs) == 1
    own_pr = act.own_prs[0]
    assert own_pr.comments == ["Tested the command and boundary conditions."]
    assert any("Tested the command and boundary conditions." in b for b in own_pr.bullets)


def test_collector_does_not_attribute_teammate_commits_in_own_pr(sample_date: date) -> None:
    client_mock = MagicMock()
    own_commit = CommitInfo(
        sha="volcann1",
        message="feat: update checkout grace calculation",
        author_login="Volcann",
    )
    teammate_commit = CommitInfo(
        sha="moin1234",
        message="feat: add early checkout grace field to shift model",
        author_login="Moin",
    )
    pr = PullRequestInfo(
        number=388,
        title="HMT-273 | Add early checkout grace period support",
        body="Added the field and updated checkout calculations.",
        author_login="Volcann",
        commits=[teammate_commit, own_commit],
    )
    client_mock.get_user_prs_for_date.return_value = [pr]
    client_mock.get_user_commits_for_date.return_value = []
    client_mock.get_user_reviewed_prs_for_date.return_value = []

    collector = ActivityCollector(github_client=client_mock, use_ai=False, verbose=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    collected_pr = report.projects[0].own_prs[0]

    assert [commit.sha for commit in collected_pr.author_commits] == ["volcann1"]
    assert "update checkout grace calculation" in collected_pr.bullets[0]
    assert all("add early checkout grace field" not in bullet for bullet in collected_pr.bullets)


def test_collector_does_not_use_pr_body_without_authored_commits(sample_date: date) -> None:
    client_mock = MagicMock()
    pr = PullRequestInfo(
        number=396,
        title="HMT-273 | Add human-readable benefit claim IDs",
        body="Implemented claim IDs and claim filtering.",
        author_login="Volcann",
        commits=[
            CommitInfo(
                sha="moin1234",
                message="enh: claim filtering",
                author_login="Moin",
            )
        ],
    )
    client_mock.get_user_prs_for_date.return_value = [pr]
    client_mock.get_user_commits_for_date.return_value = []
    client_mock.get_user_reviewed_prs_for_date.return_value = []

    collector = ActivityCollector(github_client=client_mock, use_ai=False, verbose=False)
    project = ProjectConfig(
        name="HR-Tool",
        category="Backend",
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        author="Volcann",
    )

    report = collector.collect_for_date([project], sample_date)
    bullets = report.projects[0].own_prs[0].bullets

    assert bullets == ["PR#396 -> Opened this PR; no authored commit details were found."]
    assert all("claim filtering" not in bullet for bullet in bullets)
