from __future__ import annotations

from validator import (
    ALLOWED_HEADINGS,
    PROHIBITED_WORDS,
    ClaimEvidence,
    FactualValidationResult,
    FactualValidator,
    FormatValidationResult,
    StrictFormatValidator,
)
from validator.data_classes import (
    ClaimEvidence as ClaimEvidenceDC,
)
from validator.data_classes import (
    FactualValidationResult as FactualValidationResultDC,
)
from validator.data_classes import (
    FormatValidationResult as FormatValidationResultDC,
)
from validator.data_classes.claim_evidence import ClaimEvidence as DirectClaimEvidence
from validator.data_classes.factual_validation_result import (
    FactualValidationResult as DirectFactualValidationResult,
)
from validator.data_classes.format_validation_result import (
    FormatValidationResult as DirectFormatValidationResult,
)
from validator.factual_validator import FactualValidator as DirectFactualValidator
from validator.strict_format_validator import StrictFormatValidator as DirectStrictFormatValidator


def test_classes_identity():
    assert ClaimEvidence is DirectClaimEvidence is ClaimEvidenceDC
    assert FormatValidationResult is DirectFormatValidationResult is FormatValidationResultDC
    assert FactualValidationResult is DirectFactualValidationResult is FactualValidationResultDC
    assert StrictFormatValidator is DirectStrictFormatValidator
    assert FactualValidator is DirectFactualValidator
    assert "Reviewed PRs:" in ALLOWED_HEADINGS
    assert "game-changing" in PROHIBITED_WORDS


def test_format_validation_result_instantiation():
    res = FormatValidationResult(
        is_valid=True,
        compliance_percent=100.0,
        total_rules=8,
        passed_rules=8,
    )
    assert res.is_valid is True
    assert res.compliance_percent == 100.0
    assert res.total_rules == 8
    assert res.passed_rules == 8
    assert res.failed_rules == []
    assert res.details == {}


def test_claim_evidence_instantiation_and_to_dict():
    evidence = ClaimEvidence(
        claim="Tested feature",
        type="commit",
        date="2026-10-25",
        ticket_id="TICK-123",
        pr_number=42,
        commit_sha="abcdef1",
        evidence_id="acme/repo:pr:42",
        verified=True,
        source="https://github.com/acme/repo/pull/42",
        extra_time=False,
        notes="All good",
    )
    assert evidence.to_dict() == {
        "claim": "Tested feature",
        "type": "commit",
        "date": "2026-10-25",
        "ticket_id": "TICK-123",
        "pr_number": 42,
        "commit_sha": "abcdef1",
        "evidence_id": "acme/repo:pr:42",
        "verified": True,
        "source": "https://github.com/acme/repo/pull/42",
        "extra_time": False,
        "notes": "All good",
    }


def test_factual_validation_result_instantiation():
    res = FactualValidationResult(
        is_valid=True,
        fact_support_percent=100.0,
        total_claims=1,
        supported_claims=1,
        contradicted_claims=0,
        unsupported_claims=0,
        overtime_attribution_percent=100.0,
    )
    assert res.is_valid is True
    assert res.claims == []
    assert res.violations == []


def test_strict_format_validator_empty():
    res = StrictFormatValidator.validate("")
    assert not res.is_valid
    assert res.compliance_percent == 0.0
    assert "Empty status report" in res.failed_rules
