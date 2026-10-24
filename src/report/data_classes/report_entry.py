from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportEntry:
    id: str
    kind: str
    text: str
    created_at: str
    extra_time: bool
    note: str | None
    sha: str | None = None
    url: str = ""
    branches: tuple[str, ...] = ()
    review_state: str | None = None
