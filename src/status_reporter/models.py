"""Data models for GitHub commits, pull requests, reviews, and status reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class ProjectConfig:
    """Configuration for a repository project to track."""

    owner: str
    repo: str
    name: str = "HR-Tool"
    category: str = "Backend"
    author: str = "Volcann"
    local_path: str = ""
    enabled: bool = True

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "owner": self.owner,
            "repo": self.repo,
            "author": self.author,
            "local_path": self.local_path,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectConfig:
        return cls(
            name=data.get("name") or data.get("project_name") or "HR-Tool",
            category=data.get("category")
            or ("Frontend" if "frontend" in (data.get("repo") or "").lower() else "Backend"),
            owner=data.get("owner", ""),
            repo=data.get("repo", ""),
            author=data.get("author", "Volcann"),
            local_path=data.get("local_path", ""),
            enabled=data.get("enabled", True),
        )


@dataclass
class CommitInfo:
    """Details of a single git commit."""

    sha: str
    message: str
    author_name: str = ""
    author_login: str = ""
    date: str = ""
    url: str = ""
    pr_number: int | None = None
    branch: str | None = None
    files: list[str] = field(default_factory=list)

    @property
    def short_sha(self) -> str:
        return self.sha[:7] if self.sha else ""

    @property
    def headline(self) -> str:
        if not self.message:
            return ""
        return self.message.strip().splitlines()[0]

    @property
    def body(self) -> str:
        if not self.message:
            return ""
        lines = self.message.strip().splitlines()
        return "\n".join(lines[1:]).strip() if len(lines) > 1 else ""


@dataclass
class PullRequestInfo:
    """Details of a GitHub pull request."""

    number: int
    title: str
    body: str = ""
    author_login: str = ""
    state: str = "OPEN"
    url: str = ""
    created_at: str = ""
    head_ref: str = ""
    is_own: bool = True
    commits: list[CommitInfo] = field(default_factory=list)
    author_commits: list[CommitInfo] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    category: str = "Backend"
    project_name: str = "HR-Tool"
    repo_name: str = ""
    files_changed: list[str] = field(default_factory=list)


@dataclass
class ReviewInfo:
    """Details of a pull request review."""

    pr_number: int
    pr_title: str
    reviewer: str
    state: str
    submitted_at: str = ""
    url: str = ""
    comments: list[str] = field(default_factory=list)
    review_bullets: list[str] = field(default_factory=list)
    project_name: str = "HR-Tool"
    category: str = "Backend"


@dataclass
class BranchActivity:
    """Commits pushed directly to a branch not yet merged into a PR."""

    branch_name: str
    commits: list[CommitInfo] = field(default_factory=list)
    project_name: str = "HR-Tool"
    category: str = "Backend"


@dataclass
class ProjectActivity:
    """Aggregated daily activities for a single repository or category."""

    project_name: str
    category: str
    owner: str
    repo: str
    own_prs: list[PullRequestInfo] = field(default_factory=list)
    foreign_contributions: list[PullRequestInfo] = field(default_factory=list)
    reviewed_prs: list[ReviewInfo] = field(default_factory=list)
    branch_commits: list[BranchActivity] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def has_activity(self) -> bool:
        return bool(
            self.own_prs
            or self.foreign_contributions
            or self.reviewed_prs
            or self.branch_commits
            or self.notes
        )


@dataclass
class RemovedItem:
    """Record of a bullet or claim removed by the validation pipeline."""

    target: str
    project: str
    bullet: str
    reason: str
    confidence: float = 0.0


@dataclass
class DailyReport:
    """Complete aggregated daily report across all projects and categories."""

    target_date: date
    date_display: str
    projects: list[ProjectActivity] = field(default_factory=list)
    rendered_text: str = ""
    removed_items: list[RemovedItem] = field(default_factory=list)
