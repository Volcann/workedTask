from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .report_chunk import ReportChunk


@dataclass(frozen=True)
class DailyReport:
    work_date: str
    timezone: str
    window: dict[str, str]
    shift: dict[str, str]
    author: str
    chunks: tuple[ReportChunk, ...]
    created_at_index: dict[str, str]
    summaries: dict[str, str]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def counts(self) -> dict[str, int]:
        names = ("prs", "reviewed_prs", "branch_commits", "issues", "extra_tasks")
        return {name: sum(name in chunk.categories for chunk in self.chunks) for name in names}
