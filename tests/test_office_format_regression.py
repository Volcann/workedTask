from __future__ import annotations

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
    assert "-> Found N+1 query in serializer and requested batching" in text
    assert "Backend PR:" not in text

    v_fmt = StrictFormatValidator.validate(text)
    assert v_fmt.is_valid
    v_fact = FactualValidator.validate(text, rep)
    assert v_fact.is_valid
    assert v_fact.fact_support_percent == 100.0


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


def test_10_fact_preservation_after_ai_rewriting():
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
    assert v_fact.is_valid
    assert v_fact.fact_support_percent == 100.0


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
    entry = make_entry("i1", "issue", "2026-10-19T14:00:00+05:00", text="Discussed database latency")
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
    assert "-> Found performance issue in employee evaluation serializer." in text
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
        if line.startswith("-> ") and not line.startswith("-> PR#") and not line.startswith("-> Committed:")
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
