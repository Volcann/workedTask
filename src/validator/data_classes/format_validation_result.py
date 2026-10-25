from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FormatValidationResult:
    is_valid: bool
    compliance_percent: float
    total_rules: int
    passed_rules: int
    failed_rules: list[str] = field(default_factory=list)
    details: dict[str, bool] = field(default_factory=dict)
