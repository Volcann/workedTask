from __future__ import annotations

import pytest
from constants import PROHIBITED_WORDS
from report.data_classes import EXTRA_TIME_NOTE
from validator.strict_format_validator import StrictFormatValidator


def test_validator_empty_and_whitespace_only():
    for text in ["", "   ", "\n\n\t  \n"]:
        res = StrictFormatValidator.validate(text)
        assert not res.is_valid
        assert res.compliance_percent == 0.0
        assert res.total_rules == 8
        assert res.passed_rules == 0
        assert res.failed_rules == ["Empty status report"]


def test_validator_single_line_valid():
    res = StrictFormatValidator.validate("STATUS (24-OCT-2026)")
    assert res.is_valid is True
    assert res.compliance_percent == 100.0
    assert res.total_rules == 1
    assert res.passed_rules == 1
    assert res.failed_rules == []
    assert res.details == {"rule_status_header": True}


def test_validator_single_line_invalid():
    res = StrictFormatValidator.validate("STATUS (2026-10-24)")
    assert res.is_valid is False
    assert res.compliance_percent == 0.0
    assert res.total_rules == 1
    assert res.passed_rules == 0
    assert res.failed_rules == ["Invalid STATUS header"]
    assert res.details == {"rule_status_header": False}


def test_validator_invalid_status_header_multiline():
    text = """STATUS (24-oct-2026)
HR-Tool
Reviewed PRs:
-> HMT-1: Fix login -> PR#10
"""
    res = StrictFormatValidator.validate(text)
    assert not res.is_valid
    assert "rule_status_header" in res.failed_rules


@pytest.mark.parametrize(
    "bad_project_line",
    [
        "-> Project Arrow",
        "# Project Markdown",
        "Reviewed PRs:",
        "Backend PR:",
    ],
)
def test_validator_invalid_project_header(bad_project_line):
    text = f"""STATUS (24-OCT-2026)
{bad_project_line}
Reviewed PRs:
-> HMT-1: Fix login -> PR#10
"""
    res = StrictFormatValidator.validate(text)
    assert not res.is_valid
    assert "rule_project_header" in res.failed_rules


def test_validator_invalid_category_heading():
    text = """STATUS (24-OCT-2026)
HR-Tool
Unsupported Category:
-> Some bullet
"""
    res = StrictFormatValidator.validate(text)
    assert not res.is_valid
    assert "rule_category_headings" in res.failed_rules


def test_validator_invalid_arrow_bullet():
    text = """STATUS (24-OCT-2026)
HR-Tool
Reviewed PRs:
Invalid line without arrow
Another invalid line without arrow
"""
    res = StrictFormatValidator.validate(text)
    assert not res.is_valid
    assert "rule_arrow_bullets" in res.failed_rules


def test_validator_valid_pipe_and_subheading_bullets():
    text = """STATUS (24-OCT-2026)
HR-Tool
Backend PR:
HMT-101 | Implement feature
-> PR#101 -> Core feature implementation
Foster Ferret
Backend PR:
FF-202 | Adopt workflow
-> PR#202 -> Workflow adoption
"""
    res = StrictFormatValidator.validate(text)
    assert res.is_valid
    assert res.details["rule_arrow_bullets"] is True


def test_validator_overtime_sentence_missing():
    text = """STATUS (24-OCT-2026)
HR-Tool
Overtime:
-> HMT-101: Urgent bugfix
-> PR#101 -> Fixed race condition
"""
    res = StrictFormatValidator.validate(text)
    assert not res.is_valid
    assert "rule_overtime_sentence" in res.failed_rules


def test_validator_overtime_sentence_present():
    text = f"""STATUS (24-OCT-2026)
HR-Tool
Overtime:
-> HMT-101: Urgent bugfix
-> PR#101 -> Fixed race condition
{EXTRA_TIME_NOTE}
"""
    res = StrictFormatValidator.validate(text)
    assert res.is_valid
    assert res.details["rule_overtime_sentence"] is True


@pytest.mark.parametrize(
    "markdown_artifact",
    [
        "## Subheading",
        "| Header | Col |",
        "|---|---|",
    ],
)
def test_validator_rejects_markdown_artifacts(markdown_artifact):
    text = f"""STATUS (24-OCT-2026)
HR-Tool
Reviewed PRs:
{markdown_artifact}
-> HMT-1: Fix login -> PR#10
"""
    res = StrictFormatValidator.validate(text)
    assert not res.is_valid
    assert "rule_no_markdown_artifacts" in res.failed_rules


@pytest.mark.parametrize("buzzword", PROHIBITED_WORDS)
def test_validator_rejects_corporate_buzzwords(buzzword):
    text = f"""STATUS (24-OCT-2026)
HR-Tool
Backend PR:
HMT-101 | Work item
-> PR#101 -> We {buzzword} to achieve high efficiency.
"""
    res = StrictFormatValidator.validate(text)
    assert not res.is_valid
    assert "rule_no_corporate_buzzwords" in res.failed_rules


def test_validator_rejects_pr_without_hash():
    text = """STATUS (24-OCT-2026)
HR-Tool
Reviewed PRs:
-> HMT-1: Fix login -> PR 10
"""
    res = StrictFormatValidator.validate(text)
    assert not res.is_valid
    assert "rule_identifier_format" in res.failed_rules


def test_validator_accepts_pr_with_hash():
    text = """STATUS (24-OCT-2026)
HR-Tool
Reviewed PRs:
-> HMT-1: Fix login -> PR#10
"""
    res = StrictFormatValidator.validate(text)
    assert res.is_valid
    assert res.details["rule_identifier_format"] is True
