"""Tests for GitHubClient with mocked CLI and REST endpoints."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from status_reporter.github_client import GitHubClient


def test_get_user_commits_ignores_merge_commits() -> None:
    client = GitHubClient(token="mock_token", prefer_cli=False)

    fake_commits = [
        {
            "sha": "111111111111",
            "commit": {
                "message": "feat: implement permission check for admin endpoints",
                "author": {"name": "Volcann", "date": "2026-09-11T14:00:00Z"},
            },
            "author": {"login": "Volcann"},
            "html_url": "https://github.com/org/repo/commit/1111111",
        },
        {
            "sha": "222222222222",
            "commit": {
                "message": "Merge pull request #340 from dev/fix",
                "author": {"name": "Volcann", "date": "2026-09-11T15:00:00Z"},
            },
            "author": {"login": "Volcann"},
            "html_url": "https://github.com/org/repo/commit/2222222",
        },
    ]

    with patch.object(client, "_rest_get", return_value=fake_commits):
        commits = client.get_user_commits_for_date("org", "repo", "Volcann", date(2026, 9, 11))

    assert len(commits) == 1
    assert commits[0].sha == "111111111111"
    assert commits[0].headline == "feat: implement permission check for admin endpoints"


def test_get_user_prs_for_date() -> None:
    client = GitHubClient(token="mock_token", prefer_cli=False)

    fake_search = {
        "items": [
            {
                "number": 348,
                "title": "HMT-258 | Add search and natural sorting to device mappings",
                "body": "Added search and natural sorting to device-user listings.",
                "user": {"login": "Volcann"},
                "state": "OPEN",
                "html_url": "https://github.com/org/repo/pull/348",
                "created_at": "2026-09-11T10:00:00Z",
                "head": {"ref": "feature/HMT-258"},
            }
        ]
    }

    with patch.object(client, "_rest_get", return_value=fake_search):
        prs = client.get_user_prs_for_date("org", "repo", "Volcann", date(2026, 9, 11))

    assert len(prs) == 1
    assert prs[0].number == 348
    assert prs[0].title.startswith("HMT-258")
    assert prs[0].is_own is True


def test_get_pr_details() -> None:
    client = GitHubClient(token="mock_token", prefer_cli=False)

    fake_pr_data = {
        "number": 359,
        "title": "MB-228: Payroll run",
        "body": "Summary of payroll run changes.",
        "user": {"login": "OtherDev"},
        "state": "OPEN",
        "html_url": "https://github.com/org/repo/pull/359",
        "created_at": "2026-09-15T10:00:00Z",
        "head": {"ref": "feat/payroll"},
    }

    fake_commits = [
        {
            "sha": "fd3cfbc1234",
            "commit": {"message": "Timesheet Attendance (HTM-228): Excluded soft-deleted users"},
            "author": {"login": "Volcann"},
        }
    ]

    def mock_get(endpoint: str, *args, **kwargs):
        if endpoint.endswith("/commits"):
            return fake_commits
        return fake_pr_data

    with patch.object(client, "_rest_get", side_effect=mock_get):
        pr = client.get_pr_details("org", "repo", 359)

    assert pr is not None
    assert pr.number == 359
    assert pr.author_login == "OtherDev"
    assert len(pr.commits) == 1
    assert pr.commits[0].author_login == "Volcann"


def test_get_user_reviewed_prs_for_date() -> None:
    client = GitHubClient(token="mock_token", prefer_cli=False)

    fake_search = {
        "items": [
            {
                "number": 359,
                "title": "MB-228: Payroll run",
                "html_url": "https://github.com/org/repo/pull/359",
            }
        ]
    }

    fake_reviews = [
        {
            "user": {"login": "Volcann"},
            "state": "APPROVED",
            "submitted_at": "2026-09-16T12:30:00Z",
        },
        {
            "user": {"login": "SomeoneElse"},
            "state": "COMMENTED",
            "submitted_at": "2026-09-16T09:00:00Z",
        },
    ]

    def mock_get(endpoint: str, *args, **kwargs):
        if "reviews" in endpoint:
            return fake_reviews
        return fake_search

    with patch.object(client, "_rest_get", side_effect=mock_get):
        reviews = client.get_user_reviewed_prs_for_date("org", "repo", "Volcann", date(2026, 9, 16))

    assert len(reviews) == 1
    assert reviews[0].pr_number == 359
    assert reviews[0].state == "APPROVED"


def test_get_pr_user_comments() -> None:
    client = GitHubClient(token="mock_token", prefer_cli=False)

    fake_comments = [
        {
            "id": 1,
            "user": {"login": "Volcann"},
            "created_at": "2026-09-23T15:00:00Z",
            "body": "I have fully tested from FE no breaking changes.",
        },
        {
            "id": 2,
            "user": {"login": "OtherDev"},
            "created_at": "2026-09-23T16:00:00Z",
            "body": "LGTM from backend side.",
        },
    ]

    with patch.object(client, "_rest_get", return_value=fake_comments):
        comments = client.get_pr_user_comments("org", "repo", 387, "Volcann", date(2026, 9, 23))

    assert len(comments) == 1
    assert comments[0] == "I have fully tested from FE no breaking changes."
