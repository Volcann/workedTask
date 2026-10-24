from __future__ import annotations

from report.data_classes import (
    DailyReport,
    ReportChunk,
    ReportEntry,
)
from utils.format import format_office_status
from validator.factual_validator import FactualValidator


def make_entry(
    id_: str,
    kind: str,
    created_at: str,
    text: str = "",
    sha: str | None = None,
    review_state: str | None = None,
) -> ReportEntry:
    return ReportEntry(
        id=id_,
        kind=kind,
        text=text,
        created_at=created_at,
        extra_time=False,
        note=None,
        sha=sha,
        review_state=review_state,
    )


def make_chunk(
    repo: str | None,
    kind: str,
    key: str,
    title: str,
    entries: list[ReportEntry],
    categories: tuple[str, ...] = ("prs",),
    description: str = "",
) -> ReportChunk:
    return ReportChunk(
        repository=repo,
        kind=kind,
        key=key,
        title=title,
        description=description,
        url=f"https://github.com/{repo}/pull/{key}" if repo else "",
        categories=categories,
        entries=tuple(entries),
        extra_time=False,
        note=None,
    )


def make_report(
    work_date: str,
    chunks: list[ReportChunk],
    summaries: dict[str, str] | None = None,
) -> DailyReport:
    index = {e.id: e.created_at for c in chunks for e in c.entries}
    return DailyReport(
        work_date=work_date,
        timezone="Asia/Karachi",
        window={"start": f"{work_date}T06:00:00+05:00", "end": "next"},
        shift={"start": f"{work_date}T11:00:00+05:00", "end": f"{work_date}T20:00:00+05:00"},
        author="alice",
        chunks=tuple(chunks),
        created_at_index=index,
        summaries=summaries or {},
    )


def test_factual_validator_empty_report():
    report = make_report("2026-10-24", [])
    text = format_office_status(report)
    res = FactualValidator.validate(text, report)
    assert res.is_valid is True
    assert res.fact_support_percent == 100.0
    assert res.source_consistency_percent == 100.0
    assert res.overtime_attribution_percent == 100.0
    assert res.total_claims == 0
    assert res.supported_claims == 0
    assert res.violations == []


def test_factual_validator_unmatched_line_and_no_source_chunk():
    entry = make_entry("c1", "commit", "2026-10-24T12:00:00+05:00", text="Real commit", sha="a1b2c3d")
    chunk = make_chunk("org/hr-tool-backend", "pr", "10", "Real PR", [entry])
    report = make_report("2026-10-24", [chunk])
    canonical = format_office_status(report)

    # Inject an alien line
    tampered = canonical + "-> Fabricated claim without source\n"
    res = FactualValidator.validate(tampered, report)

    assert not res.is_valid
    assert any("differs from the activity-backed" in v for v in res.violations)
    assert any("Line is not in the activity-backed" in v for v in res.violations)
    assert any("No unique source chunk" in v for v in res.violations)


def test_factual_validator_pr_number_mismatch():
    entry = make_entry("c1", "commit", "2026-10-24T12:00:00+05:00", text="Real commit", sha="a1b2c3d")
    chunk = make_chunk("org/hr-tool-backend", "pr", "10", "Real PR", [entry])
    report = make_report("2026-10-24", [chunk])
    canonical = format_office_status(report)

    # Change PR#10 to PR#999
    tampered = canonical.replace("PR#10", "PR#999")
    res = FactualValidator.validate(tampered, report)

    assert not res.is_valid
    assert any("does not match its source chunk" in v for v in res.violations)


def test_factual_validator_review_claim_missing_review_event():
    # Chunk has only commit events, but rendered under Reviewed PRs
    entry = make_entry("c1", "commit", "2026-10-24T12:00:00+05:00", text="Commit text", sha="1111111")
    chunk = make_chunk(
        "org/hr-tool-backend", "pr", "20", "Reviewed item", [entry], categories=("reviewed_prs",)
    )
    report = make_report("2026-10-24", [chunk])

    # Manually craft reviewed status
    text = """STATUS (24-OCT-2026)
HR-Tool
Reviewed PRs:
-> Reviewed item -> PR#20
"""
    res = FactualValidator.validate(text, report)
    assert not res.is_valid
    assert any("has no review event" in v for v in res.violations)


def test_factual_validator_implementation_claim_missing_implementation_event():
    # Chunk has only review comment event, placed under Backend PR
    entry = make_entry("r1", "review_comment", "2026-10-24T12:00:00+05:00", text="Review text")
    chunk = make_chunk("org/hr-tool-backend", "pr", "30", "Feature item", [entry])
    report = make_report("2026-10-24", [chunk])

    text = """STATUS (24-OCT-2026)
HR-Tool
Backend PR:
Feature item
-> PR#30 -> Feature item
"""
    res = FactualValidator.validate(text, report)
    assert not res.is_valid
    assert any("has no implementation event" in v for v in res.violations)


def test_factual_validator_commit_sha_not_unique_or_missing():
    entry = make_entry("c1", "commit", "2026-10-24T12:00:00+05:00", text="Feature item", sha="abcdef1")
    chunk = make_chunk("org/hr-tool-backend", "pr", "40", "Feature item", [entry])
    report = make_report("2026-10-24", [chunk])
    canonical = format_office_status(report)

    # Change commit sha to unknown sha9999
    tampered = canonical.replace("abcdef1", "sha9999")
    res = FactualValidator.validate(tampered, report)

    assert not res.is_valid
    assert any("is not unique in its source chunk" in v for v in res.violations)


def test_factual_validator_overtime_commit_during_regular_shift():
    # A commit at 14:00 (regular shift) placed under Overtime
    entry = make_entry("c1", "commit", "2026-10-24T14:00:00+05:00", text="Regular commit", sha="1234567")
    chunk = make_chunk("org/hr-tool-backend", "pr", "50", "Overtime attempt", [entry])
    report = make_report("2026-10-24", [chunk])

    text = """STATUS (24-OCT-2026)
HR-Tool
Overtime:
-> Overtime attempt
-> PR#50 -> Regular commit
-> Committed: 1234567
(The task is done in extra time)
"""
    res = FactualValidator.validate(text, report)
    assert not res.is_valid
    assert any("occurred during the regular shift" in v for v in res.violations)
    assert any("No out-of-shift event supports" in v for v in res.violations)


def test_factual_validator_candidate_scoping_backend_and_frontend():
    # Both backend and frontend have PR#100 with same title
    e_be = make_entry("b1", "commit", "2026-10-24T14:00:00+05:00", text="Same title", sha="bbbb111")
    chunk_be = make_chunk("org/hr-tool-backend", "pr", "100", "Same title", [e_be])

    e_fe = make_entry("f1", "commit", "2026-10-24T15:00:00+05:00", text="Same title", sha="ffff222")
    chunk_fe = make_chunk("org/hr-tool-frontend", "pr", "100", "Same title", [e_fe], categories=("frontend",))

    report = make_report("2026-10-24", [chunk_be, chunk_fe])
    text = format_office_status(report)
    res = FactualValidator.validate(text, report)

    assert res.is_valid
    assert res.fact_support_percent == 100.0
    assert len(res.violations) == 0
