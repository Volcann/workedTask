from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ghtoolkit.models import CommitInfo, PullRequestInfo, ReviewInfo


@dataclass
class BranchActivity:
    branch_name: str
    commits: list[CommitInfo] = field(default_factory=list)
    project_name: str = "HR-Tool"
    category: str = "Backend"


@dataclass
class ProjectActivity:
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
    target: str
    project: str
    bullet: str
    reason: str
    confidence: float = 0.0


@dataclass
class DailyReport:
    target_date: date
    date_display: str
    projects: list[ProjectActivity] = field(default_factory=list)
    rendered_text: str = ""
    removed_items: list[RemovedItem] = field(default_factory=list)
