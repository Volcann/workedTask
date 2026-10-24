from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ClaimEvidence:
    claim: str
    type: str
    date: str
    ticket_id: str | None
    pr_number: int | None
    commit_sha: str | None
    evidence_id: str | None
    verified: bool
    source: str
    extra_time: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "type": self.type,
            "date": self.date,
            "ticket_id": self.ticket_id,
            "pr_number": self.pr_number,
            "commit_sha": self.commit_sha,
            "evidence_id": self.evidence_id,
            "verified": self.verified,
            "source": self.source,
            "extra_time": self.extra_time,
            "notes": self.notes,
        }
