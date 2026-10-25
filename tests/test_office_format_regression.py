from __future__ import annotations

from dataclasses import replace

from report.data_classes import (
    EXTRA_TIME_NOTE,
    DailyReport,
    ReportChunk,
    ReportEntry,
)
from utils.format import (
    format_office_status,
    format_overtime_breakdown_only,
    parse_ticket_and_title,
)
from validator import FactualValidator, StrictFormatValidator


def make_entry(
    id_: str,
    kind: str,
    created_at: str,
    text: str = "",
    sha: str | None = None,
    review_state: str | None = None,
) -> ReportEntry:
    extra = False
    return ReportEntry(
        id=id_,
        kind=kind,
        text=text,
        created_at=created_at,
        extra_time=extra,
        note=EXTRA_TIME_NOTE if extra else None,
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
    any_extra = any(e.extra_time for e in entries)
    return ReportChunk(
        repository=repo,
        kind=kind,
        key=key,
        title=title,
        description=description,
        url=f"https://github.com/{repo}/pull/{key}" if repo else "",
        categories=categories,
        entries=tuple(entries),
        extra_time=any_extra,
        note=EXTRA_TIME_NOTE if any_extra else None,
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
        author="Volcann",
        chunks=tuple(chunks),
        created_at_index=index,
        summaries=summaries or {},
    )


def test_1_day_specific_status_header_formatting():
    for d_str, expected in [
        ("2026-10-16", "STATUS (16-OCT-2026)"),
        ("2026-09-11", "STATUS (11-SEP-2026)"),
        ("2026-08-24", "STATUS (24-AUG-2026)"),
    ]:
        rep = make_report(d_str, [])
        text = format_office_status(rep)
        assert text.startswith(expected)
        v = StrictFormatValidator.validate(text)
        assert v.is_valid
        assert v.compliance_percent == 100.0


def test_2_pr_review_entries():
    entry = make_entry(
        "e1",
        "review",
        "2026-10-16T15:00:00+05:00",
        text="Found N+1 query in serializer and requested batching",
        review_state="CHANGES_REQUESTED",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "448",
        "HTM-341: Performance issues & enh",
        [entry],
        categories=("reviewed_prs",),
    )
    rep = make_report("2026-10-16", [chunk])
    text = format_office_status(rep)

    assert "Reviewed PRs:" in text
    assert "-> HTM-341: Performance issues & enh -> PR#448" in text
    assert "-> Review feedback: Found N+1 query in serializer and requested batching" in text
    assert "-> Outcome: Requested changes." in text
    assert "Backend PR:" not in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid
    assert v_fact.fact_support_percent == 100.0


def test_reviewed_marker_uses_authored_findings_and_keeps_the_impact():
    entries = [
        make_entry("summary", "review", "2026-10-02T15:00:00+05:00", text="-> Reviewed changes."),
        make_entry(
            "migration",
            "review_comment",
            "2026-10-02T14:00:00+05:00",
            text=(
                "Can we create separate clones for older versions?\n\n"
                "Otherwise, overlapping parameters will violate unique constraints "
                "and lose past evaluations."
            ),
        ),
        make_entry(
            "lock",
            "review_comment",
            "2026-10-02T14:15:00+05:00",
            text="Adding parameters bypasses the lock on evaluated sets.",
        ),
    ]
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "410",
        "HTM-298: Replace KPISet versions with clones",
        entries,
        categories=("reviewed_prs",),
    )
    report = make_report("2026-10-02", [chunk])

    status = format_office_status(report)

    assert "-> HTM-298: Replace KPISet versions with clones -> PR#410" in status
    assert "Documented 2 review findings" not in status
    assert "separate clones for older versions? Otherwise, overlapping parameters" in status
    assert "lose past evaluations." in status
    assert "Adding parameters bypasses the lock on evaluated sets." in status
    assert "-> Reviewed changes." not in status
    assert FactualValidator.validate(status, report).is_valid


def test_marker_only_self_review_does_not_invent_findings():
    entry = make_entry(
        "self_review",
        "review",
        "2026-10-23T18:34:19+05:00",
        text="-> Reviewed my own PR.",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "469",
        "HMT-361: Add organization hold management",
        [entry],
        categories=("reviewed_prs",),
    )
    report = make_report("2026-10-23", [chunk])

    status = format_office_status(report)

    assert "-> Review recorded." in status
    assert "Review feedback:" not in status
    assert "admin edits" not in status
    assert FactualValidator.validate(status, report).is_valid


def test_ai_review_feedback_replaces_long_comments_and_keeps_pr_link():
    entry = ReportEntry(
        id="finding",
        kind="review_comment",
        text="Could we check attendance already linked to this holiday? Otherwise a saved row stays marked as a holiday.",
        created_at="2026-10-13T12:49:00+05:00",
        extra_time=False,
        note=None,
        url="https://github.com/acme/backend/pull/445#discussion_r1",
        actor_login="alice",
    )
    chunk = make_chunk("acme/backend", "pr", "445", "Holiday attendance", [entry], ("reviewed_prs",))
    report = make_report(
        "2026-10-13",
        [chunk],
        summaries={
            "review:acme/backend:pr:445": "Flagged stale holiday attendance when an employee leaves a department.",
            "review_verified:acme/backend:pr:445": "Flagged stale holiday attendance when an employee leaves a department.",
        },
    )

    status = format_office_status(report)

    assert "Documented 1 review finding" not in status
    assert "-> Review feedback: Flagged stale holiday attendance" in status
    assert "-> PR link: https://github.com/acme/backend/pull/445" in status
    assert "#discussion_r1" not in status
    assert "Could we check attendance" not in status
    assert FactualValidator.validate(status, report).is_valid


def test_reviewed_prs_show_feedback_and_outcome_without_event_log():
    first = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "451",
        "HTM-341: Preserve performance cycle definitions and fix supervisor assignment race",
        [
            replace(
                make_entry(
                    "finding",
                    "review_comment",
                    "2026-10-19T13:49:00+05:00",
                    text="Saving a published template removes its published version; block edits for open cycles.",
                ),
                url="https://github.com/example/pull/451#discussion_r1",
            ),
            make_entry("requested", "review", "2026-10-19T13:50:00+05:00", review_state="CHANGES_REQUESTED"),
            make_entry("approved", "review", "2026-10-19T14:52:00+05:00", review_state="APPROVED"),
        ],
        ("reviewed_prs",),
    )
    second = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "456",
        "HMT-345: Filter salary components by required status",
        [
            make_entry(
                "suggestion",
                "review_comment",
                "2026-10-19T13:15:00+05:00",
                text="Good practice to move param filters in separate filters.py.",
            ),
            make_entry("requested2", "review", "2026-10-19T13:16:00+05:00", review_state="CHANGES_REQUESTED"),
            make_entry("approved2", "review", "2026-10-19T13:18:00+05:00", review_state="APPROVED"),
        ],
        ("reviewed_prs",),
    )
    summary = "Saving a published template removes its published version; block edits for open cycles."
    report = make_report(
        "2026-10-19",
        [first, second],
        summaries={
            "review:folium-hr-management-tool/hr-tool-backend:pr:451": summary,
            "review_verified:folium-hr-management-tool/hr-tool-backend:pr:451": summary,
            "review:folium-hr-management-tool/hr-tool-backend:pr:456": "NO_FINDING",
        },
    )

    status = format_office_status(report)

    assert status.count("-> Outcome: Requested changes, then approved.") == 2
    assert "-> Review feedback: Saving a published template removes its published version" in status
    assert "-> Review feedback: Good practice to move param filters in separate filters.py." in status
    assert status.count("-> PR link:") == 2
    assert "-> Review by" not in status
    assert "-> PR comment by" not in status
    assert "#discussion_r1" not in status
    assert "Merge status: unavailable" not in status
    assert StrictFormatValidator.validate(status).is_valid
    assert FactualValidator.validate(status, report).is_valid


def test_reviewed_pr_includes_conversation_finding_alongside_implementation():
    review = make_entry("review", "review", "2026-10-20T13:00:00+05:00")
    comment = make_entry(
        "comment",
        "issue_comment",
        "2026-10-20T13:01:00+05:00",
        text="If no approval configuration exists, check whether HR approval is required.",
    )
    commit = make_entry(
        "commit", "commit", "2026-10-20T13:02:00+05:00", text="Implement approvals", sha="abc1234"
    )
    chunk = make_chunk(
        "acme/backend",
        "pr",
        "460",
        "Fix approval display",
        [review, comment, commit],
        ("prs", "reviewed_prs"),
    )
    report = make_report("2026-10-20", [chunk])

    status = format_office_status(report)

    assert "Reviewed PRs:" in status
    assert "If no approval configuration exists" in status
    assert "Backend PR:" in status
    assert FactualValidator.validate(status, report).is_valid


def test_ai_no_finding_does_not_count_an_explanatory_comment_as_an_issue():
    entry = make_entry(
        "note",
        "review_comment",
        "2026-10-20T13:00:00+05:00",
        text="UTC is intentional in this change; organization timezones are separate work.",
    )
    chunk = make_chunk("acme/backend", "pr", "458", "Show UTC label", [entry], ("reviewed_prs",))
    report = make_report("2026-10-20", [chunk], summaries={"review:acme/backend:pr:458": "NO_FINDING"})

    status = format_office_status(report)

    assert "Documented 1 review finding" not in status
    assert "Review impact:" not in status
    assert "UTC is intentional" in status


def test_unverified_ai_review_impact_needs_independent_review():
    entry = make_entry(
        "finding",
        "review_comment",
        "2026-10-20T13:00:00+05:00",
        text="The frontend does not display the API message.",
    )
    chunk = make_chunk("acme/backend", "pr", "459", "Show request message", [entry], ("reviewed_prs",))
    report = make_report(
        "2026-10-20",
        [chunk],
        summaries={"review:acme/backend:pr:459": "Employees cannot see the API message."},
    )

    result = FactualValidator.validate(format_office_status(report), report)

    assert not result.is_valid
    assert any("requires independent review" in violation for violation in result.violations)


def test_ai_review_impact_appears_in_overtime_when_review_was_after_shift():
    entry = make_entry(
        "finding",
        "review_comment",
        "2026-10-14T21:00:00+05:00",
        text="Multiple HRs appear as pending for one request.",
    )
    chunk = make_chunk("acme/backend", "pr", "449", "Pending approvers", [entry], ("reviewed_prs",))
    report = make_report(
        "2026-10-14",
        [chunk],
        summaries={
            "review:acme/backend:pr:449": "Flagged duplicate pending HR approvers.",
            "review_verified:acme/backend:pr:449": "Flagged duplicate pending HR approvers.",
        },
    )

    status = format_office_status(report)

    assert "Reviewed PRs:" not in status
    assert "Overtime:" in status
    assert "-> Review feedback: Flagged duplicate pending HR approvers." in status
    assert "-> PR#449 -> Review feedback recorded." in status
    assert "Review feedback: Flagged duplicate pending HR approvers." in format_overtime_breakdown_only(
        report
    )
    assert FactualValidator.validate(status, report).is_valid


def test_3_backend_and_frontend_grouping():
    e_be = make_entry(
        "be1", "commit", "2026-09-11T14:00:00+05:00", text="HMT-258 | Add search", sha="a1b2c3d"
    )
    chunk_be = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "348",
        "HMT-258 | Add search and natural sorting to device mappings",
        [e_be],
        categories=("prs",),
    )
    e_fe = make_entry(
        "fe1", "commit", "2026-09-11T16:00:00+05:00", text="HMT-258 | Refactor tables", sha="d4e5f6a"
    )
    chunk_fe = make_chunk(
        "folium-hr-management-tool/hr-tool-frontend",
        "pr",
        "275",
        "HMT-258: BE | Employee Unmapping & Attendance Handling Issues",
        [e_fe],
        categories=("prs", "frontend"),
    )
    rep = make_report("2026-09-11", [chunk_be, chunk_fe])
    text = format_office_status(rep)

    assert "Backend PR:" in text
    assert "HMT-258 | Add search and natural sorting to device mappings" in text
    assert "Frontend PR:" in text
    assert "HMT-258 | Employee Unmapping & Attendance Handling Issues" in text
    assert text.index("Backend PR:") < text.index("Frontend PR:")

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_4_multiple_prs_associated_with_one_ticket():
    e1 = make_entry(
        "e1", "commit", "2026-09-11T12:00:00+05:00", text="HMT-258 | First feature", sha="1111111"
    )
    chunk1 = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "348",
        "HMT-258 | Add search and natural sorting to device mappings",
        [e1],
    )
    e2 = make_entry(
        "e2", "commit", "2026-09-11T13:00:00+05:00", text="HMT-258 | Second feature", sha="2222222"
    )
    chunk2 = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "349",
        "HMT-258 | Updated permission checks for org super-admins",
        [e2],
    )
    rep = make_report("2026-09-11", [chunk1, chunk2])
    text = format_office_status(rep)

    assert "PR#348" in text
    assert "PR#349" in text
    assert "Add search and natural sorting to device mappings" in text
    assert "Updated permission checks for org super-admins" in text
    assert text.count("HMT-258 |") == 2

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_5_multiple_commits_under_one_pr():
    e1 = make_entry(
        "c1",
        "commit",
        "2026-10-16T12:00:00+05:00",
        text="HTM-341: Expose period status for employee performance results",
        sha="a8c7d92",
    )
    e2 = make_entry(
        "c2",
        "commit",
        "2026-10-16T13:00:00+05:00",
        text="HTM-341: Add 59 performance evaluation API tests",
        sha="b9d8e03",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "454",
        "HTM-341: Expose period status for employee performance results",
        [e1, e2],
    )
    rep = make_report("2026-10-16", [chunk])
    text = format_office_status(rep)

    assert "HTM-341 | Expose period status for employee performance results" in text
    assert "-> PR#454 -> Expose period status for employee performance results" in text
    assert "-> Add 59 performance evaluation API tests." in text
    assert "-> Committed: a8c7d92, b9d8e03" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_6_non_github_tasks_and_team_discussions():
    entry = make_entry(
        "m1",
        "extra_task",
        "2026-10-16T14:30:00+05:00",
        text="Discussed device sync architecture with mobile engineering team",
    )
    chunk = make_chunk(
        None,
        "extra_task",
        "manual-sync",
        "Architecture sync",
        [entry],
        categories=("extra_tasks",),
        description="Discussed device sync architecture with mobile engineering team",
    )
    rep = make_report("2026-10-16", [chunk])
    text = format_office_status(rep)

    assert "Out of scope:" in text
    assert "-> Discussed device sync architecture with mobile engineering team" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_7_out_of_scope_work():
    e_work = make_entry("w1", "commit", "2026-10-16T12:00:00+05:00", text="HTM-341: Core work", sha="1234567")
    chunk_work = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "454", "HTM-341: Core work", [e_work]
    )
    e_out = make_entry(
        "o1", "extra_task", "2026-10-16T15:00:00+05:00", text="Investigated AWS S3 storage quota"
    )
    chunk_out = make_chunk(
        None,
        "extra_task",
        "s3-quota",
        "Storage investigation",
        [e_out],
        categories=("extra_tasks",),
        description="Investigated AWS S3 storage quota",
    )
    rep = make_report("2026-10-16", [chunk_work, chunk_out])
    text = format_office_status(rep)

    assert "Backend PR:" in text
    assert "Out of scope:" in text
    assert "-> Investigated AWS S3 storage quota" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_8_overnight_and_overtime_activity():
    e_reg = make_entry("c_reg", "commit", "2026-10-16T14:00:00+05:00", text="HTM-341: Day fix", sha="aaa1111")
    e_ot = make_entry(
        "c_ot", "commit", "2026-10-16T21:30:00+05:00", text="HTM-341: Urgent late fix", sha="bbb2222"
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "454", "HTM-341: Performance issues", [e_reg, e_ot]
    )
    rep = make_report("2026-10-16", [chunk])
    text = format_office_status(rep)

    assert "Backend PR:" in text
    assert "-> Committed: aaa1111" in text
    assert "Overtime:" in text
    assert "-> PR#454 -> Urgent late fix" in text
    assert "-> Committed: bbb2222" in text
    assert EXTRA_TIME_NOTE in text

    ot_only = format_overtime_breakdown_only(rep)
    assert "PR#454" in ot_only
    assert "-> Committed: bbb2222" in ot_only
    assert EXTRA_TIME_NOTE in ot_only
    assert "Day fix" not in ot_only

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid
    assert v_fact.overtime_attribution_percent == 100.0


def test_9_natural_technical_writing():
    text = """STATUS (16-OCT-2026)
HR-Tool
Reviewed PRs:
-> HTM-341: Performance issues & enh -> PR#448

Backend PR:
HTM-341 | Expose period status for employee performance results
-> PR#454 -> Added `period_status` to the evaluation serializer and updated the workflow documentation.
-> Verified 59 performance evaluation API tests passed.
-> Committed: a8c7d92
"""
    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    assert v_fmt.compliance_percent == 100.0

    fluff_text = text.replace(
        "Added `period_status`", "Successfully leveraged innovative solutions and enhanced system robustness"
    )
    v_fluff = StrictFormatValidator.validate(fluff_text)
    assert not v_fluff.is_valid
    assert "rule_no_corporate_buzzwords" in v_fluff.failed_rules


def test_10_ai_rewriting_requires_independent_review():
    e = make_entry("c1", "commit", "2026-10-16T12:00:00+05:00", text="HTM-341: Base commit", sha="a8c7d92")
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "454", "HTM-341: Expose period status", [e]
    )
    ai_summary = "Added `period_status` to the evaluation serializer and updated workflow documentation."
    rep = make_report(
        "2026-10-16", [chunk], summaries={f"{chunk.repository}:{chunk.kind}:{chunk.key}": ai_summary}
    )
    text = format_office_status(rep)

    assert "HTM-341 | Expose period status" in text
    assert "PR#454" in text
    assert "a8c7d92" in text
    assert "Added `period_status`" in text

    v_fact = FactualValidator.validate(text, rep)
    assert not v_fact.is_valid
    assert v_fact.fact_support_percent < 100.0
    assert any("AI summary" in violation for violation in v_fact.violations)


def test_12_empty_and_partially_documented_reporting_days():
    rep_empty = make_report("2026-10-11", [])
    text_empty = format_office_status(rep_empty)
    assert text_empty == "STATUS (11-OCT-2026)\n"
    v_empty = StrictFormatValidator.validate(text_empty)
    assert v_empty.is_valid
    assert v_empty.compliance_percent == 100.0

    e_rev = make_entry("r1", "review", "2026-10-11T13:00:00+05:00", text="LGTM", review_state="APPROVED")
    chunk_rev = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "400",
        "HTM-300: Quick fix",
        [e_rev],
        categories=("reviewed_prs",),
    )
    rep_partial = make_report("2026-10-11", [chunk_rev])
    text_partial = format_office_status(rep_partial)

    assert "STATUS (11-OCT-2026)" in text_partial
    assert "Reviewed PRs:" in text_partial
    assert "Backend PR:" not in text_partial
    assert "Frontend PR:" not in text_partial
    assert "Overtime:" not in text_partial

    v_part = StrictFormatValidator.validate(text_partial)
    assert v_part.is_valid
    v_fact = FactualValidator.validate(text_partial, rep_partial)
    assert v_fact.is_valid


def test_13_issue_chunk_routed_to_out_of_scope():
    entry = make_entry("i1", "issue_comment", "2026-10-19T14:00:00+05:00", text="Discussed database latency")
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "issue",
        "455",
        "Critical: Django Silk is active on production environment (Severe latency overhead)",
        [entry],
        categories=("issues",),
        description="Critical: Django Silk is active on production environment (Severe latency overhead)",
    )
    rep = make_report("2026-10-19", [chunk])
    text = format_office_status(rep)

    assert "Out of scope:" in text
    assert "Reviewed PRs:" not in text
    assert "Backend PR:" not in text
    assert "PR#455" not in text
    assert "Django Silk" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid
    assert v_fact.contradicted_claims == 0


def test_14_pr_number_normalization_in_commit_text():
    e1 = make_entry(
        "c1", "commit", "2026-10-09T14:00:00+05:00", text="HTM-327 | Core payroll fix", sha="1111111"
    )
    e2 = make_entry(
        "c2",
        "commit",
        "2026-10-09T15:00:00+05:00",
        text="Move PR 433 test coverage onto base branch",
        sha="2222222",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "419",
        "HTM-327 | Core payroll fix",
        [e1, e2],
    )
    rep = make_report("2026-10-09", [chunk])
    text = format_office_status(rep)

    assert "Move PR#433 test coverage onto base branch." in text
    assert "Move PR 433" not in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    assert v_fmt.details["rule_identifier_format"] is True


def test_15_task_title_without_ticket_id():
    e1 = make_entry("c1", "commit", "2026-10-19T16:00:00+05:00", text="Stage 2nd Release", sha="3333333")
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-frontend",
        "pr",
        "451",
        "Stage 2nd Release",
        [e1],
        categories=("prs", "frontend"),
    )
    rep = make_report("2026-10-19", [chunk])
    text = format_office_status(rep)

    assert "Frontend PR:" in text
    assert "Stage 2nd Release" in text
    assert "-> PR#451 -> Stage 2nd Release" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    assert v_fmt.details["rule_arrow_bullets"] is True
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_16_merge_commits_filtered_from_implementation_and_overtime():
    e_merge = make_entry(
        "m1",
        "commit",
        "2026-09-01T14:00:00+05:00",
        text="Merge branch 'dev' of https://github.com/folium-hr-management-tool/hr-tool-backend into MM-HMT-211",
        sha="1111111",
    )
    e_real = make_entry(
        "c1",
        "commit",
        "2026-09-01T15:00:00+05:00",
        text="feat: enhance punch request validation to prevent duplicate times",
        sha="2222222",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "297",
        "HMT-211 | Handle Punch Request Edge Cases and Strengthen Validation",
        [e_merge, e_real],
    )
    rep = make_report("2026-09-01", [chunk])
    text = format_office_status(rep)

    assert "Merge branch" not in text
    assert "Merge pull request" not in text
    assert "Enhance punch request validation to prevent duplicate times" in text
    assert "-> Committed: 1111111, 2222222" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_17_conventional_commit_prefix_stripped_and_cleaned():
    e1 = make_entry(
        "c1",
        "commit",
        "2026-09-01T13:00:00+05:00",
        text="feat(leave): add punch request policy constants for leave management",
        sha="3333333",
    )
    e2 = make_entry(
        "c2",
        "commit",
        "2026-09-01T14:00:00+05:00",
        text="fix: update employee reference in punch creation to use OrgMemberProfile",
        sha="4444444",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "297",
        "HMT-211 | Punch request improvements",
        [e1, e2],
    )
    rep = make_report("2026-09-01", [chunk])
    text = format_office_status(rep)

    assert "feat:" not in text
    assert "fix:" not in text
    assert "feat(leave):" not in text
    assert "-> PR#297 -> Add punch request policy constants for leave management" in text
    assert "-> Update employee reference in punch creation to use OrgMemberProfile." in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_18_distinguish_review_from_implementation_on_same_pr():
    e_rev = make_entry(
        "r1",
        "review",
        "2026-10-16T13:00:00+05:00",
        text="Found performance issue in employee evaluation serializer",
        review_state="CHANGES_REQUESTED",
    )
    e_fix = make_entry(
        "c1",
        "commit",
        "2026-10-16T15:00:00+05:00",
        text="HTM-341: Fix serialization performance by batching queries",
        sha="5555555",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "454",
        "HTM-341: Expose period status for employee performance results",
        [e_rev, e_fix],
        categories=("prs", "reviewed_prs"),
    )
    rep = make_report("2026-10-16", [chunk])
    text = format_office_status(rep)

    assert "Reviewed PRs:" in text
    assert "-> HTM-341: Expose period status for employee performance results -> PR#454" in text
    assert "-> Review feedback: Found performance issue in employee evaluation serializer." in text
    assert "Backend PR:" in text
    assert "HTM-341 | Expose period status for employee performance results" in text
    assert "-> PR#454 -> Fix serialization performance by batching queries" in text
    assert "-> Committed: 5555555" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid
    assert v_fact.fact_support_percent == 100.0


def test_19_ticket_with_developer_prefix():
    for raw, exp_ticket, exp_title in [
        ("MM-HMT-351: Date time issues on listing", "HMT-351", "Date time issues on listing"),
        ("TS-HMT-352: Attendance fix", "HMT-352", "Attendance fix"),
        ("MB/HTM-341: Performance closure", "HTM-341", "Performance closure"),
        ("[MM-HMT-361] Organization hold models", "HMT-361", "Organization hold models"),
    ]:
        ticket, title = parse_ticket_and_title(raw)
        assert ticket == exp_ticket
        assert title == exp_title


def test_20_multiple_projects_on_same_day():
    e_hr = make_entry(
        "c1", "commit", "2026-10-16T12:00:00+05:00", text="HTM-341: Core HR work", sha="6666666"
    )
    chunk_hr = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "454", "HTM-341: Core HR work", [e_hr]
    )

    e_ff = make_entry(
        "c2", "commit", "2026-10-16T14:00:00+05:00", text="FF-10: Adopt ferret workflow", sha="7777777"
    )
    chunk_ff = make_chunk("folium/foster-ferret", "pr", "10", "FF-10: Adopt ferret workflow", [e_ff])

    rep = make_report("2026-10-16", [chunk_hr, chunk_ff])
    text = format_office_status(rep)

    assert "HR-Tool" in text
    assert "Foster Ferret" in text
    assert text.index("HR-Tool") < text.index("Foster Ferret")

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    assert v_fmt.compliance_percent == 100.0
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_21_deduplication_and_cap_on_secondary_commits():
    entries = [
        make_entry(f"c{i}", "commit", f"2026-09-01T1{i}:00:00+05:00", text=msg, sha=f"aaa{i:04d}")
        for i, msg in enumerate(
            [
                "feat: add punch request constants",
                "feat: add punch request constants",
                "fix: punch request validation",
                "test: add 10 unit tests for punch request",
                "docs: update API documentation",
                "chore: bump dependencies",
                "refactor: clean serializers",
            ],
            start=1,
        )
    ]
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "297", "HMT-211 | Punch request constants", entries
    )
    rep = make_report("2026-09-01", [chunk])
    text = format_office_status(rep)

    bullet_lines = [
        line
        for line in text.splitlines()
        if line.startswith("-> ")
        and not line.startswith(("-> PR#", "-> Committed:", "-> PR link:", "-> Merge status:"))
    ]
    assert len(bullet_lines) <= 3
    assert len(bullet_lines) == len(set(bullet_lines))
    assert "aaa0001" in text
    assert "aaa0007" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_22_multi_repo_same_pr_number_factual_validation():
    e_review = make_entry("r1", "review_comment", "2026-10-13T14:00:00+05:00", text="Check attendance link.")
    chunk_be = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "445", "HTM-327: Holiday attendance", [e_review]
    )
    e_commit = make_entry("c1", "commit", "2026-10-13T15:00:00+05:00", text="Address feedback", sha="2bd3532")
    chunk_fe = make_chunk(
        "folium-hr-management-tool/hr-tool-frontend",
        "pr",
        "445",
        "HMT-341: Show performance scores",
        [e_commit],
    )

    rep = make_report("2026-10-13", [chunk_be, chunk_fe])
    text = format_office_status(rep)

    assert "Reviewed PRs:" in text
    assert "Frontend PR:" in text
    assert "-> Committed: 2bd3532" in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid
    assert v_fact.fact_support_percent == 100.0
    assert len(v_fact.violations) == 0
    frontend_claim = next(c for c in v_fact.claims if c.claim.startswith("-> PR#445"))
    assert frontend_claim.evidence_id == "folium-hr-management-tool/hr-tool-frontend:pr:445"


def test_fabricated_claim_on_real_pr_is_rejected():
    entry = make_entry("c1", "commit", "2026-10-20T14:00:00+05:00", text="Fix punch policy", sha="abc1234")
    chunk = make_chunk("folium-hr-management-tool/hr-tool-backend", "pr", "458", "Fix punch policy", [entry])
    report = make_report("2026-10-20", [chunk])
    text = format_office_status(report).replace(
        "Backend PR:\n", "Backend PR:\n-> PR#458 -> Built a quantum payroll engine.\n", 1
    )

    result = FactualValidator.validate(text, report)

    assert not result.is_valid
    assert result.fact_support_percent < 100.0
    assert not next(c for c in result.claims if "quantum payroll" in c.claim).verified


def test_comment_only_pr_is_not_implementation():
    entry = make_entry("comment", "issue_comment", "2026-10-12T14:00:00+05:00", text="Keep this PR open.")
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "434", "Scope salary reads", [entry]
    )
    report = make_report("2026-10-12", [chunk])
    text = format_office_status(report)

    assert "Backend PR:" not in text
    assert "Out of scope:" in text
    assert FactualValidator.validate(text, report).is_valid


def test_overtime_issue_keeps_the_recorded_comment():
    entry = make_entry(
        "comment",
        "issue_comment",
        "2026-10-17T21:12:13+05:00",
        text="-> Fixed, updated .env and restart the server.",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "issue",
        "455",
        "Django Silk profiling",
        [entry],
        categories=("issues",),
    )
    report = make_report("2026-10-17", [chunk])
    text = format_office_status(report)

    assert "-> Issue #455: Django Silk profiling" in text
    assert "-> Commented: Fixed, updated .env and restart the server." in text
    assert FactualValidator.validate(text, report).is_valid


def test_configured_shift_drives_report_and_validator_overtime():
    entry = make_entry(
        "evening", "commit", "2026-10-20T19:00:00+05:00", text="Fix punch policy", sha="abc1234"
    )
    chunk = make_chunk("folium-hr-management-tool/hr-tool-backend", "pr", "458", "Fix punch policy", [entry])
    report = make_report("2026-10-20", [chunk])
    report = replace(report, shift={"start": "2026-10-20T09:00:00+05:00", "end": "2026-10-20T18:00:00+05:00"})

    text = format_office_status(report)

    assert "Overtime:" in text
    assert "Backend PR:" not in text
    assert "abc1234" in format_overtime_breakdown_only(report)
    assert FactualValidator.validate(text, report).is_valid


def test_overnight_shift_keeps_two_am_work_regular():
    entry = make_entry(
        "night", "commit", "2026-10-25T02:00:00+05:00", text="Fix overnight flow", sha="def5678"
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "459", "Fix overnight flow", [entry]
    )
    report = make_report("2026-10-24", [chunk])
    report = replace(report, shift={"start": "2026-10-24T22:00:00+05:00", "end": "2026-10-25T06:00:00+05:00"})

    text = format_office_status(report)

    assert "Backend PR:" in text
    assert "Overtime:" not in text
    assert not format_overtime_breakdown_only(report)
    assert FactualValidator.validate(text, report).is_valid


def test_23_overtime_review_and_ticket_prefixed_merge_commits():
    from utils.format import is_merge_commit

    assert is_merge_commit("HTM-215: Merge origin/stage")
    assert is_merge_commit("HMT-311: Merge branch 'stage' into dev")
    assert is_merge_commit("MM-HMT-215: Merge origin/stage into MM-HMT-215-Push-Notifcations")
    assert is_merge_commit("RESOLVED Merge CONFLICTS INSIDE branch 'stage' ...")
    assert not is_merge_commit("HTM-215: Restore push notification updates")

    e_ot_review = make_entry(
        "r_ot",
        "review_comment",
        "2026-08-25T21:00:00+05:00",
        text="```suggestion\n```\nDocumented endpoint path should include /status/.",
        sha="138f0cb72ced1b4fe61817502db9b5427e92a91e",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend", "pr", "276", "Reports Single Fetch Api", [e_ot_review]
    )
    rep = make_report("2026-08-25", [chunk])
    text = format_office_status(rep)

    assert "Overtime:" in text
    assert "Documented endpoint path should include /status/." in text
    assert "```suggestion" not in text
    assert "Committed:" not in text
    assert EXTRA_TIME_NOTE in text

    ot_breakdown = format_overtime_breakdown_only(rep)
    assert "PR#276" in ot_breakdown
    assert "Documented endpoint path should include /status/." in ot_breakdown
    assert "Committed:" not in ot_breakdown


def test_24_overtime_always_mentions_ticket_number():
    e_ot = make_entry(
        "c_ot",
        "commit",
        "2026-09-28T20:30:00+05:00",
        text="HTM-311: Consolidate overtime migrations",
        sha="b549df4",
    )
    chunk = make_chunk(
        "folium-hr-management-tool/hr-tool-backend",
        "pr",
        "400",
        "HTM-302: payroll issues",
        [e_ot],
    )
    rep = make_report("2026-09-28", [chunk])
    text = format_office_status(rep)

    assert "Overtime:" in text
    assert "-> HTM-302: Payroll issues" in text
    assert "-> PR#400 -> Consolidate overtime migrations" in text
    assert "-> Committed: b549df4" in text
    assert EXTRA_TIME_NOTE in text

    ot_breakdown = format_overtime_breakdown_only(rep)
    assert "-> HTM-302: Payroll issues" in ot_breakdown
    assert "-> PR#400 -> Consolidate overtime migrations" in ot_breakdown
    assert "-> Committed: b549df4" in ot_breakdown

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid


def test_25_overtime_marker_appears_once_at_section_end():
    e_ot1 = make_entry("ot1", "commit", "2026-10-08T20:30:00+05:00", text="HTM-327: Fix 1", sha="1111111")
    chunk1 = make_chunk("folium-hr-management-tool/hr-tool-backend", "pr", "419", "HTM-327: Task 1", [e_ot1])

    e_ot2 = make_entry("ot2", "commit", "2026-10-08T21:00:00+05:00", text="HMT-291: Fix 2", sha="2222222")
    chunk2 = make_chunk("folium-hr-management-tool/hr-tool-backend", "pr", "432", "HMT-291: Task 2", [e_ot2])

    rep = make_report("2026-10-08", [chunk1, chunk2])
    text = format_office_status(rep)

    assert "Overtime:" in text
    assert text.count(EXTRA_TIME_NOTE) == 1

    ot_breakdown = format_overtime_breakdown_only(rep)
    assert ot_breakdown.count(EXTRA_TIME_NOTE) == 1
    assert ot_breakdown.endswith(EXTRA_TIME_NOTE)
