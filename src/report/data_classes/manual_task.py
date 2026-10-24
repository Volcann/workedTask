from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ghtoolkit import parse_timestamp


@dataclass(frozen=True)
class ManualTask:
    id: str
    title: str
    completed_at: datetime
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.title.strip():
            raise ValueError("Manual tasks require a nonempty id and title.")
        object.__setattr__(self, "completed_at", parse_timestamp(self.completed_at))
