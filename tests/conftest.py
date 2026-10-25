"""Offline fixtures: synthetic data only; no credentials or external requests."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, time

import pytest
from ghtoolkit import GitHubClient
from ghtoolkit.activity import collect_repository_activity
from report.data_classes import ReportSchedule


def commit(sha, stamp, author="alice", message=None):
    return {
        "sha": sha,
        "author": {"login": author} if author else None,
        "html_url": f"https://github.com/acme/widget/commit/{sha}",
        "commit": {
            "message": message or f"Implement {sha[0]}",
            "author": {"name": author or "Alias Name", "email": "alias@example.test", "date": stamp},
            "committer": {"date": stamp},
        },
    }


def subject(number, title, author="alice", created="2026-10-20T05:00:00Z", pull=True):
    result = {
        "number": number,
        "title": title,
        "body": f"Description for {title}",
        "user": {"login": author},
        "created_at": created,
        "updated_at": "2026-10-24T23:00:00Z",
        "html_url": f"https://github.com/acme/widget/{'pull' if pull else 'issues'}/{number}",
    }
    if pull:
        result["pull_request"] = {"url": f"https://api.github.com/repos/acme/widget/pulls/{number}"}
    return result


class FakeGateway:
    def __init__(self):
        self.calls = []
        self.entered = 0
        self.exited = 0
        self.s1, self.s2, self.s3 = "a" * 40, "b" * 40, "c" * 40
        first = commit(self.s1, "2026-10-24T06:00:00Z")
        standalone = commit(self.s2, "2026-10-24T14:00:00Z")
        fork = commit(self.s3, "2026-10-24T12:00:00Z")
        self.pulls = [
            subject(36, "Implement login"),
            subject(37, "Fix edge case", "bob"),
            subject(38, "New proposal", created="2026-10-24T09:00:00Z"),
            subject(41, "Old PR with today's review", "bob", "2020-01-01T00:00:00Z"),
        ]
        self.pulls[-1]["updated_at"] = "2020-01-01T00:00:00Z"
        self.issues = [
            subject(39, "Investigate incident", "bob", pull=False),
            subject(40, "Track cleanup", created="2026-10-24T08:00:00Z", pull=False),
        ]
        self.branch_commits = {
            "main": [
                first,
                commit("d" * 40, "2026-10-24T07:00:00Z", "bob"),
                commit("e" * 40, "2026-10-24T01:00:00Z"),
                commit("f" * 40, "2026-10-25T01:00:00Z"),
            ],
            "feature": [first, standalone],
        }
        self.pr_commits = {36: [first], 37: [fork], 38: [], 41: []}
        self.issue_comments = [
            {
                "id": 1,
                "body": "Discussed login validation",
                "user": {"login": "alice"},
                "created_at": "2026-10-24T07:00:00Z",
                "issue_url": "https://api.github.com/repos/acme/widget/issues/36",
            },
            {
                "id": 2,
                "body": "Finished incident follow-up at 2 a.m.",
                "user": {"login": "alice"},
                "created_at": "2026-10-24T21:00:00Z",
                "issue_url": "https://api.github.com/repos/acme/widget/issues/39",
            },
            {
                "id": 3,
                "body": "Old comment edited today",
                "user": {"login": "alice"},
                "created_at": "2026-10-23T07:00:00Z",
                "updated_at": "2026-10-24T07:00:00Z",
                "issue_url": "https://api.github.com/repos/acme/widget/issues/39",
            },
            {
                "id": 4,
                "body": "Not this author's work",
                "user": {"login": "bob"},
                "created_at": "2026-10-24T07:00:00Z",
                "issue_url": "https://api.github.com/repos/acme/widget/issues/39",
            },
        ]
        self.inline_comments = [
            {
                "id": 1,
                "body": "Handle the missing value",
                "user": {"login": "alice"},
                "created_at": "2026-10-24T15:01:00Z",
                "commit_id": self.s3,
                "pull_request_url": "https://api.github.com/repos/acme/widget/pulls/37",
            }
        ]
        self.reviews = {
            36: [],
            37: [
                {
                    "id": 1,
                    "body": "",
                    "state": "APPROVED",
                    "submitted_at": "2026-10-24T15:00:00Z",
                    "user": {"login": "alice"},
                },
                {
                    "id": 2,
                    "body": "Draft",
                    "state": "PENDING",
                    "submitted_at": None,
                    "user": {"login": "alice"},
                },
            ],
            38: [],
            41: [
                {
                    "id": 3,
                    "body": "Reviewed old PR",
                    "state": "COMMENTED",
                    "submitted_at": "2026-10-24T05:00:00Z",
                    "user": {"login": "alice"},
                }
            ],
        }
        self.commit_comments = [
            {
                "id": 1,
                "body": "Investigated old commit",
                "user": {"login": "alice"},
                "created_at": "2026-10-24T20:00:00Z",
                "commit_id": "0" * 40,
            }
        ]
        self.associations = {}
        self.details = {"0" * 40: commit("0" * 40, "2020-01-01T00:00:00Z", "bob")}

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, *args):
        self.exited += 1

    def list(self, resource, action, **kwargs):
        self.calls.append((f"list:{resource}.{action}", deepcopy(kwargs)))
        route = (resource, action)
        if route == ("repos", "list_branches"):
            result = [{"name": name} for name in self.branch_commits]
        elif route == ("repos", "list_commits"):
            result = self.branch_commits[kwargs["sha"]]
        elif route == ("pulls", "list"):
            result = self.pulls
        elif route == ("issues", "list_for_repo"):
            result = self.issues + self.pulls
        elif route == ("issues", "list_comments_for_repo"):
            result = self.issue_comments
        elif route == ("pulls", "list_review_comments_for_repo"):
            result = self.inline_comments
        elif route == ("pulls", "list_reviews"):
            result = self.reviews[kwargs["pull_number"]]
        elif route == ("repos", "list_commit_comments_for_repo"):
            result = self.commit_comments
        elif route == ("repos", "list_pull_requests_associated_with_commit"):
            result = self.associations.get(kwargs["commit_sha"], [])
        else:
            raise AssertionError(f"Unexpected list route {route}")
        return iter(deepcopy(result))

    def call(self, resource, action, **kwargs):
        self.calls.append((f"call:{resource}.{action}", deepcopy(kwargs)))
        if (resource, action) == ("pulls", "get"):
            return deepcopy(next(p for p in self.pulls if p["number"] == kwargs["pull_number"]))
        if (resource, action) == ("issues", "get"):
            return deepcopy(
                next(p for p in self.issues + self.pulls if p["number"] == kwargs["issue_number"])
            )
        if (resource, action) == ("repos", "get_commit"):
            return deepcopy(self.details[kwargs["ref"]])
        return {"id": 100, **kwargs}

    def text(self, resource, action, **kwargs):
        self.calls.append((f"text:{resource}.{action}", deepcopy(kwargs)))
        return "diff --git a/a.py b/a.py\n+new\n"

    def graphql(self, query, variables):
        self.calls.append(("graphql", deepcopy(variables)))
        nodes = []
        for item in self.pr_commits[variables["number"]]:
            meta = item["commit"]
            nodes.append(
                {
                    "commit": {
                        "oid": item["sha"],
                        "message": meta["message"],
                        "url": item["html_url"],
                        "committedDate": meta["committer"]["date"],
                        "authoredDate": meta["author"]["date"],
                        "author": {
                            "name": meta["author"]["name"],
                            "email": meta["author"]["email"],
                            "user": item["author"],
                        },
                    }
                }
            )
        return {
            "repository": {
                "pullRequest": {
                    "commits": {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}
                }
            }
        }


@pytest.fixture
def fake_gateway():
    return FakeGateway()


@pytest.fixture
def schedule():
    return ReportSchedule(date(2026, 10, 24), "Asia/Karachi", time(9), time(18), time(6))


@pytest.fixture
def fake_client(fake_gateway):
    return GitHubClient("acme/widget", gateway=fake_gateway)


@pytest.fixture
def activity(fake_client, schedule):
    return collect_repository_activity(fake_client, "alice", schedule.window)
