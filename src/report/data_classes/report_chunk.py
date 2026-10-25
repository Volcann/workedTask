from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .report_entry import ReportEntry


@dataclass(frozen=True)
class ReportChunk:
    repository: str | None
    kind: str
    key: str
    title: str
    description: str
    url: str
    categories: tuple[str, ...]
    entries: tuple[ReportEntry, ...]
    extra_time: bool
    note: str | None
    merged_at: str | None = None
    merged_by: str | None = None
    merge_commit_sha: str | None = None
    merge_status_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def chunk_id(chunk: ReportChunk) -> str:
    return f"{chunk.repository or 'non-github'}:{chunk.kind}:{chunk.key}"
