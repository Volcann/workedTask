from __future__ import annotations

from dataclasses import dataclass, field

from .claim_evidence import ClaimEvidence


@dataclass
class FactualValidationResult:
    is_valid: bool
    fact_support_percent: float
    total_claims: int
    supported_claims: int
    contradicted_claims: int
    unsupported_claims: int
    overtime_attribution_percent: float
    claims: list[ClaimEvidence] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    @property
    def source_consistency_percent(self) -> float:
        """Preferred name for the legacy fact_support_percent field."""
        return self.fact_support_percent
