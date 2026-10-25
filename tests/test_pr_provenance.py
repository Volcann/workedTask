from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from ghtoolkit import GitHubRequestError, SnapshotSource, write_snapshot
from ghtoolkit.activity import collect_repository_activity
from report.service import ReportService
from utils.format import format_office_status
from validator import FactualValidator, StrictFormatValidator


def _report(fake_client, schedule):
    activity = collect_repository_activity(fake_client, "alice", schedule.window)
    source = SimpleNamespace(collect_daily_activity=Mock(return_value=(activity,)))
    return ReportService(source).generate(["acme/widget"], "alice", schedule)


def test_approval_with_body_and_merge_by_same_user_are_separate_facts(fake_client, fake_gateway, schedule):
    pr = next(item for item in fake_gateway.pulls if item["number"] == 37)
    pr.update(
        merged_at="2026-10-24T12:30:00Z",
        merged_by={"login": "alice"},
        merge_commit_sha="f" * 40,
    )
    fake_gateway.reviews[37][0]["body"] = "Please add a regression check"
    report = _report(fake_client, schedule)
    chunk = next(c for c in report.chunks if c.kind == "pr" and c.key == "37")
    text = format_office_status(report)

    assert chunk.merge_status_verified
    assert chunk.merged_by == "alice"
    assert any(e.kind == "pr_merged" for e in chunk.entries)
    assert "Review by @alice: APPROVED at 2026-10-24T20:00+05:00" in text
    assert "Merged by @alice at 2026-10-24T17:30+05:00" in text
    assert "merge SHA " + "f" * 40 in text
    assert "Please add a regression check" in text
    assert "PR link: https://github.com/acme/widget/pull/37" in text
    assert StrictFormatValidator.validate(text).is_valid
    validation = FactualValidator.validate(text, report)
    assert validation.is_valid
    assert all(
        not claim.extra_time
        for claim in validation.claims
        if claim.claim.startswith("-> Merged by @alice at 2026-10-24T17:30")
    )


def test_merge_without_other_activity_still_appears(fake_client, fake_gateway, schedule):
    pr = next(item for item in fake_gateway.pulls if item["number"] == 41)
    pr.update(
        merged_at="2026-10-24T12:00:00Z",
        merged_by={"login": "alice"},
        merge_commit_sha="9" * 40,
    )
    fake_gateway.reviews[41] = []
    report = _report(fake_client, schedule)
    chunk = next(c for c in report.chunks if c.kind == "pr" and c.key == "41")
    text = format_office_status(report)

    assert [e.kind for e in chunk.entries] == ["pr_merged"]
    assert "Merged PRs:" in text
    assert "Merged by @alice at 2026-10-24T17:00+05:00" in text
    assert FactualValidator.validate(text, report).is_valid


def test_merge_by_other_user_is_not_attributed_to_report_author(fake_client, fake_gateway, schedule):
    pr = next(item for item in fake_gateway.pulls if item["number"] == 37)
    pr.update(merged_at="2026-10-24T12:30:00Z", merged_by={"login": "bob"})
    report = _report(fake_client, schedule)
    chunk = next(c for c in report.chunks if c.kind == "pr" and c.key == "37")
    text = format_office_status(report)

    assert not any(e.kind == "pr_merged" for e in chunk.entries)
    assert "Merged by @bob at 2026-10-24T17:30+05:00" in text
    assert "Merged by @alice" not in text


def test_comment_and_review_are_labeled_differently_and_unverified_merge_is_unknown(
    fake_client, fake_gateway, schedule
):
    report = _report(fake_client, schedule)
    text = format_office_status(report)

    assert "Review by @alice: APPROVED" in text
    assert "PR comment by @alice" in text
    assert "Merge status: unavailable from GitHub." in text
    assert "Verified and approved PR" not in text


def test_verified_open_pr_is_explicitly_not_merged(fake_client, fake_gateway, schedule):
    pr = next(item for item in fake_gateway.pulls if item["number"] == 37)
    pr.update(merged_at=None, merged_by=None, merge_commit_sha=None)
    report = _report(fake_client, schedule)
    text = format_office_status(report)

    assert "Merge status: not merged at report generation." in text
    assert "Merged by @alice" not in text


def test_review_uses_exact_github_actor_when_alias_matches(fake_client, fake_gateway, schedule):
    fake_client.register_author_alias("alice", ["reviewer-alias"])
    fake_gateway.reviews[37][0]["user"]["login"] = "reviewer-alias"
    report = _report(fake_client, schedule)
    chunk = next(c for c in report.chunks if c.kind == "pr" and c.key == "37")
    review = next(e for e in chunk.entries if e.kind == "review")

    assert review.actor_login == "reviewer-alias"
    assert "Review by @reviewer-alias: APPROVED" in format_office_status(report)


def test_merge_alias_survives_snapshot_replay(fake_client, fake_gateway, schedule, tmp_path):
    fake_client.register_author_alias("alice", ["merge-alias"])
    pr = next(item for item in fake_gateway.pulls if item["number"] == 41)
    pr.update(merged_at="2026-10-24T12:00:00Z", merged_by={"login": "merge-alias"})
    fake_gateway.reviews[41] = []
    activity = collect_repository_activity(fake_client, "alice", schedule.window)
    path = tmp_path / "activity.json"
    write_snapshot(path, "alice", schedule.window, (activity,))
    replayed = SnapshotSource(path).collect_daily_activity(["acme/widget"], "alice", schedule.window)

    merger_event = next(e for e in replayed[0].timeline if e.kind == "pr_merged")
    assert merger_event.author == "alice"
    assert merger_event.actor_login == "merge-alias"


def test_validator_rejects_changed_merger_identity(fake_client, fake_gateway, schedule):
    pr = next(item for item in fake_gateway.pulls if item["number"] == 37)
    pr.update(merged_at="2026-10-24T12:30:00Z", merged_by={"login": "bob"})
    report = _report(fake_client, schedule)
    correct = format_office_status(report)
    forged = correct.replace("Merged by @bob", "Merged by @alice")

    assert not FactualValidator.validate(forged, report).is_valid


def test_pr_list_supplies_unmerged_status_when_detail_lookup_fails(fake_client, fake_gateway, schedule):
    pr = next(item for item in fake_gateway.pulls if item["number"] == 37)
    pr.update(merged_at=None, merged_by=None)
    original = fake_client.get_pull_request

    def get_detail(number):
        if number == 37:
            raise GitHubRequestError("pulls.get", 404)
        return original(number)

    fake_client.get_pull_request = get_detail
    report = _report(fake_client, schedule)
    chunk = next(c for c in report.chunks if c.kind == "pr" and c.key == "37")

    assert chunk.merge_status_verified
    assert "Merge status: not merged at report generation." in format_office_status(report)


def test_merge_only_commit_is_not_presented_as_implementation(fake_client, fake_gateway, schedule):
    pr = next(item for item in fake_gateway.pulls if item["number"] == 41)
    sha = "7" * 40
    pr.update(merged_at="2026-10-24T12:00:00Z", merged_by={"login": "alice"})
    fake_gateway.reviews[41] = []
    merge = deepcopy(fake_gateway.branch_commits["main"][0])
    merge["sha"] = sha
    merge["commit"]["message"] = "Merge pull request #41 from team/feature"
    merge["commit"]["committer"]["date"] = "2026-10-24T12:00:00Z"
    merge["commit"]["author"]["date"] = "2026-10-24T12:00:00Z"
    fake_gateway.branch_commits["main"].append(merge)
    fake_gateway.associations[sha] = [pr]

    report = _report(fake_client, schedule)
    text = format_office_status(report)
    assert f"-> Merge commit: {sha}" in text
    backend = text.split("Backend PR:", 1)[1].split("Frontend PR:", 1)[0]
    assert "PR#41" not in backend
    assert FactualValidator.validate(text, report).is_valid
