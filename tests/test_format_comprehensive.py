from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import utils.format as fmt
import utils.formate as fmte
from report.data_classes import (
    EXTRA_TIME_NOTE,
    DailyReport,
    ReportChunk,
    ReportEntry,
)
from utils.render import render_pr_chunks


def test_formate_reexports_all_format_symbols():
    for name in fmt.__all__:
        assert hasattr(fmte, name)
        assert getattr(fmte, name) is getattr(fmt, name)


def test_clean_bullet_text():
    assert fmt.clean_bullet_text("  ->  PR 123  fixed   ") == "PR#123  fixed"
    assert fmt.clean_bullet_text("- PR 456 updated") == "PR#456 updated"
    assert fmt.clean_bullet_text("* regular bullet") == "regular bullet"
    assert fmt.clean_bullet_text("No bullet") == "No bullet"
    assert fmt.clean_bullet_text("") == ""


def test_first_line_of():
    assert fmt.first_line_of(None) == ""
    assert fmt.first_line_of("") == ""
    assert fmt.first_line_of("   \n\n  ") == ""
    assert fmt.first_line_of("-> First line\nSecond line") == "First line"
    assert fmt.first_line_of("- PR 101 resolved") == "PR#101 resolved"


def test_parse_ticket_and_title_variations():
    # Standard formats
    assert fmt.parse_ticket_and_title("HMT-123: Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("[HMT-123] Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("HMT-123 - Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("HMT-123 | Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("HMT-123 — Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("HMT-123 – Add feature") == ("HMT-123", "Add feature")

    # Developer prefixes
    assert fmt.parse_ticket_and_title("MM-HMT-123: Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("MM/HMT-123: Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("MM_HMT-123: Add feature") == ("HMT-123", "Add feature")

    # BE / FE marker
    assert fmt.parse_ticket_and_title("HMT-123: BE | Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("HMT-123: FE - Add feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("HMT-123: BE : Add feature") == ("HMT-123", "Add feature")

    # Branch style slugs
    assert fmt.parse_ticket_and_title("HMT-123-add-feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("HMT-123_add_feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("MM-HMT-123-add-feature") == ("HMT-123", "Add feature")
    assert fmt.parse_ticket_and_title("HMT-123--") == ("HMT-123", "HMT-123--")

    # Conventional commit prefixes stripped and capitalized
    assert fmt.parse_ticket_and_title("feat: add feature") == (None, "Add feature")
    assert fmt.parse_ticket_and_title("fix(core): fix bug") == (None, "Fix bug")
    assert fmt.parse_ticket_and_title("refactor!: rewrite") == (None, "Rewrite")
    assert fmt.parse_ticket_and_title("chore(deps)!: bump") == (None, "Bump")
    assert fmt.parse_ticket_and_title("docs: update readme") == (None, "Update readme")
    assert fmt.parse_ticket_and_title("test: add tests") == (None, "Add tests")
    assert fmt.parse_ticket_and_title("perf: optimize query") == (None, "Optimize query")
    assert fmt.parse_ticket_and_title("style: format code") == (None, "Format code")
    assert fmt.parse_ticket_and_title("ci: configure pipeline") == (None, "Configure pipeline")
    assert fmt.parse_ticket_and_title("build: upgrade setuptools") == (None, "Upgrade setuptools")

    # Edge cases
    assert fmt.parse_ticket_and_title("feat:") == (None, "feat:")
    assert fmt.parse_ticket_and_title("HMT-123: PR 42 reference") == ("HMT-123", "PR#42 reference")
    assert fmt.parse_ticket_and_title("Just a simple title") == (None, "Just a simple title")


def test_is_merge_commit_all_cases():
    assert not fmt.is_merge_commit(None)
    assert not fmt.is_merge_commit("")
    assert not fmt.is_merge_commit("   ")
    assert not fmt.is_merge_commit("feat: implement merge sort")
    assert not fmt.is_merge_commit("fix: handle merge conflict error messages")

    # Starts with keywords
    assert fmt.is_merge_commit("Merge branch 'main' into dev")
    assert fmt.is_merge_commit("Merge remote-tracking branch 'origin/main'")
    assert fmt.is_merge_commit("Merge pull request #123 from user/branch")
    assert fmt.is_merge_commit("Merge into stage")
    assert fmt.is_merge_commit("Merge origin/dev")
    assert fmt.is_merge_commit("Merge upstream/dev")
    assert fmt.is_merge_commit("Merge remote/feature")
    assert fmt.is_merge_commit("Resolve merge conflict")
    assert fmt.is_merge_commit("Resolved merge conflict in settings.py")
    assert fmt.is_merge_commit("Resolving merge conflict with backend")

    # Regex patterns
    assert fmt.is_merge_commit("merge dev into main")
    assert fmt.is_merge_commit("merge branch-a")

    # Substring patterns
    assert fmt.is_merge_commit("Commit: merge branch 'feat' into dev")
    assert fmt.is_merge_commit("Commit: merge remote-tracking branch 'origin/dev'")
    assert fmt.is_merge_commit("MM-HMT-12: merge conflicts inside branch dev")
    assert fmt.is_merge_commit("Fix merge conflict in schema.sql")


def test_clean_commit_message():
    assert fmt.clean_commit_message(None) == ""
    assert fmt.clean_commit_message("") == ""
    assert fmt.clean_commit_message("   ") == ""
    assert fmt.clean_commit_message("feat: add new feature") == "Add new feature"
    assert fmt.clean_commit_message("HMT-123: fix(auth): token expiry") == "Token expiry"
    assert fmt.clean_commit_message("-> * - PR 50 fix") == "PR#50 fix"
    assert fmt.clean_commit_message("feat:") == "Feat:"


def test_is_out_of_shift():
    pkt = ZoneInfo("Asia/Karachi")

    # In shift: 12:00 PKT
    in_shift_str = "2026-10-24T12:00:00+05:00"
    assert not fmt.is_out_of_shift(in_shift_str)

    # Shift start: exactly 11:00 PKT
    at_start = datetime(2026, 10, 24, 11, 0, tzinfo=pkt)
    assert not fmt.is_out_of_shift(at_start)

    # Shift end: exactly 20:00 PKT (is >= end_time -> True)
    at_end = datetime(2026, 10, 24, 20, 0, tzinfo=pkt)
    assert fmt.is_out_of_shift(at_end)

    # Before shift: 10:59 PKT
    before_shift = datetime(2026, 10, 24, 10, 59, tzinfo=pkt)
    assert fmt.is_out_of_shift(before_shift)

    # Late night / Overtime: 21:00 PKT
    after_shift = "2026-10-24T21:00:00+05:00"
    assert fmt.is_out_of_shift(after_shift)

    # Custom times and timezone
    custom_dt = datetime(2026, 10, 24, 9, 30, tzinfo=ZoneInfo("UTC"))
    assert not fmt.is_out_of_shift(custom_dt, tz_name="UTC", start_time=time(9, 0), end_time=time(17, 0))
    assert fmt.is_out_of_shift(custom_dt, tz_name="UTC", start_time=time(10, 0), end_time=time(17, 0))


def test_format_status_date():
    assert fmt.format_status_date("2026-10-24") == "24-OCT-2026"
    assert fmt.format_status_date("2026-01-05") == "05-JAN-2026"
    assert fmt.format_status_date("2026-12-31") == "31-DEC-2026"


def test_ensure_period():
    assert fmt.ensure_period("Done.") == "Done."
    assert fmt.ensure_period("Finished!") == "Finished!"
    assert fmt.ensure_period("Question?") == "Question?"
    assert fmt.ensure_period("Completed task") == "Completed task."
    assert fmt.ensure_period("  Spaces around  ") == "Spaces around."


def test_clean_review_finding():
    assert fmt.clean_review_finding("") == []
    assert fmt.clean_review_finding(None) == []

    text = """
    ```python
    def remove_me():
        pass
    ```
    <b>Look at PR 42:</b>
    @teammate please verify this query optimization.
    -> Line that is too short: ok
    Valid finding with enough characters for inclusion
    """
    findings = fmt.clean_review_finding(text)
    assert any("PR#42" in f for f in findings)
    assert not any("remove_me" in f for f in findings)
    assert not any("<b>" in f for f in findings)
    assert not any("@teammate" in f for f in findings)
    assert all(f.endswith(".") for f in findings)

    # Long line truncation with spaces
    long_line = "This is a very long line with many words that will definitely exceed one hundred and sixty characters in total length so that we can test word boundary truncation logic properly."
    res = fmt.clean_review_finding(long_line)
    assert len(res) == 1
    assert res[0].endswith("...")

    # Long line truncation without spaces
    long_no_space = "A" * 170
    res_no_space = fmt.clean_review_finding(long_no_space)
    assert len(res_no_space) == 1
    assert res_no_space[0].startswith("A" * 157)
    assert res_no_space[0].endswith("...")

    # Cap at 3 findings
    many_findings = "\n".join([f"Finding number {i} is here." for i in range(10)])
    assert len(fmt.clean_review_finding(many_findings)) == 3


def test_format_office_status_empty_report():
    report = DailyReport(
        work_date="2026-10-24",
        timezone="Asia/Karachi",
        window={"start": "start", "end": "end"},
        shift={"start": "start", "end": "end"},
        author="alice",
        chunks=(),
        created_at_index={},
        summaries={},
        warnings=(),
    )
    assert fmt.format_office_status(report) == "STATUS (24-OCT-2026)\n"


def test_format_office_status_reviewed_pr_fallback_state():
    # Review with no comment text, fallback to state
    entry = ReportEntry(
        id="e1",
        kind="review",
        text="(No comment provided)",
        created_at="2026-10-24T14:00:00+05:00",
        extra_time=False,
        note=None,
        review_state="APPROVED",
    )
    chunk = ReportChunk(
        repository="org/backend",
        kind="pr",
        key="55",
        title="Quick PR",
        description="",
        url="",
        categories=("reviewed_prs",),
        entries=(entry,),
        extra_time=False,
        note=None,
    )
    report = DailyReport(
        work_date="2026-10-24",
        timezone="Asia/Karachi",
        window={"start": "start", "end": "end"},
        shift={"start": "start", "end": "end"},
        author="alice",
        chunks=(chunk,),
        created_at_index={},
        summaries={},
        warnings=(),
    )
    output = fmt.format_office_status(report)
    assert "Reviewed PRs:" in output
    assert "-> Quick PR -> PR#55" in output
    assert "-> Outcome: Approved." in output


def test_format_office_status_reviewed_pr_commented_state_no_fallback():
    # Review with no comment text and state is COMMENTED -> does not add "Verified and commented PR."
    entry = ReportEntry(
        id="e1",
        kind="review",
        text="(No comment provided)",
        created_at="2026-10-24T14:00:00+05:00",
        extra_time=False,
        note=None,
        review_state="COMMENTED",
    )
    chunk = ReportChunk(
        repository="org/backend",
        kind="pr",
        key="56",
        title="Silent review",
        description="",
        url="",
        categories=("reviewed_prs",),
        entries=(entry,),
        extra_time=False,
        note=None,
    )
    report = DailyReport(
        work_date="2026-10-24",
        timezone="Asia/Karachi",
        window={"start": "start", "end": "end"},
        shift={"start": "start", "end": "end"},
        author="alice",
        chunks=(chunk,),
        created_at_index={},
        summaries={},
        warnings=(),
    )
    output = fmt.format_office_status(report)
    assert "Reviewed PRs:" in output
    assert "-> Silent review -> PR#56" in output
    assert "Verified and" not in output


def test_format_office_status_overtime_pr_without_commits_or_comments():
    entry = ReportEntry(
        id="e1",
        kind="review",
        text="",
        created_at="2026-10-24T22:00:00+05:00",
        extra_time=True,
        note=EXTRA_TIME_NOTE,
    )
    chunk = ReportChunk(
        repository="org/backend",
        kind="pr",
        key="77",
        title="Night review",
        description="",
        url="",
        categories=("prs",),
        entries=(entry,),
        extra_time=True,
        note=EXTRA_TIME_NOTE,
    )
    report = DailyReport(
        work_date="2026-10-24",
        timezone="Asia/Karachi",
        window={"start": "start", "end": "end"},
        shift={"start": "start", "end": "end"},
        author="alice",
        chunks=(chunk,),
        created_at_index={},
        summaries={},
        warnings=(),
    )
    output = fmt.format_office_status(report)
    assert "Overtime:" in output
    assert "-> Night review" in output
    assert "-> PR#77 -> Reviewed and verified PR." in output
    assert EXTRA_TIME_NOTE in output

    ot_breakdown = fmt.format_overtime_breakdown_only(report)
    assert "PR#77 -> Reviewed and verified PR." in ot_breakdown


def test_format_office_status_overtime_extra_task_with_commits():
    entry = ReportEntry(
        id="e1",
        kind="commit",
        text="Late task commit",
        created_at="2026-10-24T22:00:00+05:00",
        extra_time=True,
        note=EXTRA_TIME_NOTE,
        sha="abcdef0123456789",
    )
    chunk = ReportChunk(
        repository=None,
        kind="extra_task",
        key="manual-1",
        title="Night manual task",
        description="",
        url="",
        categories=("extra_tasks",),
        entries=(entry,),
        extra_time=True,
        note=EXTRA_TIME_NOTE,
    )
    report = DailyReport(
        work_date="2026-10-24",
        timezone="Asia/Karachi",
        window={"start": "start", "end": "end"},
        shift={"start": "start", "end": "end"},
        author="alice",
        chunks=(chunk,),
        created_at_index={},
        summaries={},
        warnings=(),
    )
    output = fmt.format_office_status(report)
    assert "Overtime:" in output
    assert "-> Night manual task" in output
    assert "-> Committed: abcdef0" in output
    assert EXTRA_TIME_NOTE in output

    ot_breakdown = fmt.format_overtime_breakdown_only(report)
    assert "-> Night manual task" in ot_breakdown
    assert "-> Committed: abcdef0" in ot_breakdown


def test_format_overtime_breakdown_only_empty():
    report = DailyReport(
        work_date="2026-10-24",
        timezone="Asia/Karachi",
        window={"start": "start", "end": "end"},
        shift={"start": "start", "end": "end"},
        author="alice",
        chunks=(),
        created_at_index={},
        summaries={},
        warnings=(),
    )
    assert fmt.format_overtime_breakdown_only(report) == ""


def test_render_pr_chunks_filters_non_prs():
    entry = ReportEntry("e1", "commit", "2026-10-24T12:00:00+05:00", False, None)
    chunk_pr = ReportChunk("org/repo", "pr", "10", "PR 10", "", "", ("prs",), (entry,), False, None)
    chunk_issue = ReportChunk(
        "org/repo", "issue", "20", "Issue 20", "", "", ("issues",), (entry,), False, None
    )
    report = DailyReport(
        work_date="2026-10-24",
        timezone="Asia/Karachi",
        window={},
        shift={},
        author="alice",
        chunks=(chunk_pr, chunk_issue),
        created_at_index={},
        summaries={},
        warnings=(),
    )
    lines = render_pr_chunks(report).strip().splitlines()
    assert len(lines) == 1
    assert '"key": "10"' in lines[0]
