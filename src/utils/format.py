from __future__ import annotations

import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from ghtoolkit import parse_timestamp
from report.data_classes import EXTRA_TIME_NOTE, DailyReport, ReportChunk, ReportEntry

PKT_ZONE = ZoneInfo("Asia/Karachi")
SHIFT_START_PKT = time(11, 0)
SHIFT_END_PKT = time(20, 0)


def clean_bullet_text(text: str) -> str:
    line = text.strip()
    line = re.sub(r"\bPR\s+(\d+)\b", r"PR#\1", line)
    line = re.sub(r"^->\s*", "", line)
    line = re.sub(r"^[-*]\s*", "", line)
    return line.strip()


def first_line_of(text: str | None) -> str:
    if not text:
        return ""
    lines = text.strip().splitlines()
    return clean_bullet_text(lines[0]) if lines else ""


def parse_ticket_and_title(raw_title: str) -> tuple[str | None, str]:
    cleaned = raw_title.strip()
    cleaned = re.sub(r"\bPR\s+(\d+)\b", r"PR#\1", cleaned)

    def _clean_title(t: str) -> str:
        stripped = re.sub(
            r"^(?:feat|fix|refactor|chore|test|docs|perf|style|ci|build)(?:\([^)]+\))?!?:\s*",
            "",
            t.strip(),
            flags=re.IGNORECASE,
        ).strip()
        if not stripped:
            return t
        return stripped[0].upper() + stripped[1:]

    match = re.match(
        r"^\[?(?:[A-Za-z]{2,4}[/_-])?([A-Za-z]{2,6}-\d+)\]?[\s:|–—-]+(?:(?:BE|FE)\s*[|:–—\-]\s*)?(.*)$",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        ticket = match.group(1).upper()
        title = match.group(2).strip()
        title = re.sub(r"\bPR\s+(\d+)\b", r"PR#\1", title)
        return ticket, _clean_title(title or cleaned)

    branch_match = re.match(
        r"^\[?(?:[A-Za-z]{2,4}[/_-])?([A-Za-z]{2,6}-\d+)[-_]+(.*)$", cleaned, re.IGNORECASE
    )
    if branch_match:
        ticket = branch_match.group(1).upper()
        raw_slug = branch_match.group(2).replace("-", " ").replace("_", " ").strip()
        slug_title = raw_slug[0].upper() + raw_slug[1:] if raw_slug else cleaned
        return ticket, _clean_title(slug_title)

    return None, _clean_title(cleaned)


def is_merge_commit(text: str | None) -> bool:
    if not text:
        return False
    line = first_line_of(text)
    if not line:
        return False
    _, clean_line = parse_ticket_and_title(line)
    lower = clean_line.strip().lower()
    if lower.startswith(
        (
            "merge branch",
            "merge remote-tracking branch",
            "merge pull request",
            "merge into",
            "merge origin/",
            "merge upstream/",
            "merge remote/",
            "resolve merge conflict",
            "resolved merge conflict",
            "resolving merge conflict",
        )
    ):
        return True
    if re.match(r"^merge\s+[^\s]+(?:\s+into\s+[^\s]+)?$", lower):
        return True
    return bool(
        "merge branch '" in lower
        or "merge remote-tracking branch '" in lower
        or "merge conflicts inside branch" in lower
        or "merge conflict in" in lower
    )


def _is_pr_merge_commit(entry: ReportEntry, chunk: ReportChunk) -> bool:
    return bool(
        entry.kind == "commit"
        and entry.sha
        and re.match(
            rf"^Merge pull request #{re.escape(chunk.key)}(?:\s|$)",
            first_line_of(entry.text),
            re.IGNORECASE,
        )
    )


def clean_commit_message(text: str | None) -> str:
    line = first_line_of(text)
    if not line:
        return ""
    line = re.sub(r"\bPR\s+(\d+)\b", r"PR#\1", line)
    _, clean_line = parse_ticket_and_title(line)
    clean_line = re.sub(
        r"^(?:feat|fix|refactor|chore|test|docs|perf|style|ci|build)(?:\([^)]+\))?!?:\s*",
        "",
        clean_line,
        flags=re.IGNORECASE,
    ).strip()
    clean_line = re.sub(r"^(?:->|[-*])\s*", "", clean_line).strip()
    if not clean_line:
        return ""
    clean_line = clean_line[0].upper() + clean_line[1:]
    return clean_line


def is_out_of_shift(
    stamp: str | datetime,
    tz_name: str = "Asia/Karachi",
    start_time: time = SHIFT_START_PKT,
    end_time: time = SHIFT_END_PKT,
) -> bool:
    dt = parse_timestamp(stamp).astimezone(ZoneInfo(tz_name))
    t = dt.time()
    return t < start_time or t >= end_time


def is_out_of_report_shift(stamp: str | datetime, report: DailyReport) -> bool:
    """Compare an event with the report's actual shift, including overnight shifts."""
    event_time = parse_timestamp(stamp)
    start = parse_timestamp(report.shift["start"])
    end = parse_timestamp(report.shift["end"])
    return event_time < start or event_time >= end


def format_status_date(iso_date: str) -> str:
    parts = iso_date.split("-")
    d = date(int(parts[0]), int(parts[1]), int(parts[2]))
    return d.strftime("%d-%b-%Y").upper()


def ensure_period(text: str) -> str:
    cleaned = text.strip()
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def _local_event_time(stamp: str, report: DailyReport) -> str:
    return parse_timestamp(stamp).astimezone(ZoneInfo(report.timezone)).isoformat(timespec="minutes")


def _pr_status_lines(chunk: ReportChunk, report: DailyReport) -> list[str]:
    lines = [f"-> PR link: {chunk.url}"] if chunk.url else []
    if not chunk.merge_status_verified:
        lines.append("-> Merge status: unavailable from GitHub.")
    elif chunk.merged_at:
        actor = f" by @{chunk.merged_by}" if chunk.merged_by else " (merger unknown)"
        sha = f"; merge SHA {chunk.merge_commit_sha}" if chunk.merge_commit_sha else ""
        lines.append(f"-> Merged{actor} at {_local_event_time(chunk.merged_at, report)}{sha}.")
    else:
        lines.append("-> Merge status: not merged at report generation.")
    return lines


def _review_action_lines(entries: list[ReportEntry], report: DailyReport) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        when = _local_event_time(entry.created_at, report)
        actor = entry.actor_login or report.author
        link = f"; {entry.url}" if entry.url else ""
        if entry.kind == "review":
            state = entry.review_state or "UNKNOWN"
            lines.append(f"-> Review by @{actor}: {state} at {when}{link}.")
        elif entry.kind in {"review_comment", "issue_comment"}:
            lines.append(f"-> PR comment by @{actor} at {when}{link}.")
    return lines


def clean_review_finding(text: str) -> list[str]:
    if not text:
        return []
    cleaned = re.sub(r"```[\s\S]*?```", "", text)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"@\w+\b", "", cleaned)

    bullets: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        line = re.sub(r"^->\s*", "", line)
        line = re.sub(r"^[-*#]\s*", "", line)
        line = re.sub(r"\bPR\s+(\d+)\b", r"PR#\1", line)
        line = line.strip()
        if not line or len(line) < 4:
            continue
        if len(line) > 160:
            truncated = line[:157]
            if " " in truncated:
                truncated = truncated.rsplit(" ", 1)[0]
            line = truncated + "..."
        bullets.append(ensure_period(line))
        if len(bullets) >= 3:
            break
    return bullets


def _review_summary_lines(entries: list[ReportEntry]) -> list[str]:
    """Keep the review's concrete findings together, without check-in notes."""
    findings: list[tuple[int, str]] = []
    check_ins: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not entry.text or entry.text.startswith("(No comment"):
            continue
        cleaned = re.sub(r"```[\s\S]*?```", " ", entry.text)
        cleaned = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", cleaned)
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        cleaned = re.sub(r"@\w+\b", "", cleaned)
        cleaned = re.sub(r"(?m)^\s*(?:->|[-*#])\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\bPR\s*#?\s*(\d+)\b", r"PR#\1", cleaned)
        if not cleaned:
            continue
        key = cleaned.casefold().rstrip(".!? ")
        if key in seen:
            continue
        seen.add(key)
        if re.fullmatch(
            r"(?:reviewed(?: my own pr| (?:changes|chnages))?|approved changes|"
            r"verified and approved pr|reviewed and merged)",
            key,
        ):
            check_ins.append(ensure_period(cleaned))
        else:
            if len(cleaned) > 320:
                sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", cleaned)
                shortened = ""
                for sentence in sentences:
                    if shortened and len(shortened) + len(sentence) + 1 > 320:
                        break
                    shortened = f"{shortened} {sentence}".strip()
                cleaned = (
                    shortened
                    if shortened and len(shortened) <= 320
                    else cleaned[:317].rsplit(" ", 1)[0] + "..."
                )
            priority = 0 if entry.kind == "review_comment" else 1
            findings.append((priority, ensure_period(cleaned)))
    if not findings:
        return check_ins[:2]
    ordered = sorted(findings, key=lambda item: item[0])[:4]
    inline_count = sum(priority == 0 for priority, _ in findings)
    if inline_count:
        count_line = f"Documented {inline_count} review finding{'s' if inline_count != 1 else ''}."
        return [count_line, *(line for _, line in ordered)]
    return [line for _, line in ordered]


def format_office_status(report: DailyReport, default_project: str = "HR-Tool") -> str:
    date_header = f"STATUS ({format_status_date(report.work_date)})"
    if not report.chunks:
        return f"{date_header}\n"

    def infer_project(chunk: ReportChunk) -> str:
        repo = (chunk.repository or "").lower()
        if "foster-ferret" in repo or "fosterferret" in repo:
            return "Foster Ferret"
        return default_project

    projects: dict[str, dict[str, list[tuple[ReportChunk, list[ReportEntry]]]]] = {}

    for chunk in report.chunks:
        proj = infer_project(chunk)
        p_data = projects.setdefault(
            proj,
            {
                "reviewed": [],
                "merged": [],
                "backend": [],
                "frontend": [],
                "out_of_scope": [],
                "overtime": [],
            },
        )

        regular_entries: list[ReportEntry] = []
        overtime_entries: list[ReportEntry] = []

        for entry in chunk.entries:
            if is_out_of_report_shift(entry.created_at, report):
                overtime_entries.append(entry)
            else:
                regular_entries.append(entry)

        if regular_entries:
            has_review_action = any(
                entry.kind in {"review", "review_comment"} for entry in regular_entries
            )
            review_entries = [
                e
                for e in regular_entries
                if e.kind in {"review", "review_comment"}
                or (
                    e.kind == "issue_comment"
                    and chunk.kind == "pr"
                    and ("prs" not in chunk.categories or has_review_action)
                )
            ]
            merge_entries = [e for e in regular_entries if e.kind == "pr_merged"]
            pr_merge_commits = [e for e in regular_entries if _is_pr_merge_commit(e, chunk)]
            impl_entries = [
                e
                for e in regular_entries
                if e.kind in {"commit", "pr_created"} and (not merge_entries or e not in pr_merge_commits)
            ]

            if merge_entries:
                p_data["merged"].append((chunk, [*merge_entries, *pr_merge_commits]))

            if review_entries and not impl_entries:
                p_data["reviewed"].append((chunk, review_entries))
            elif impl_entries and not review_entries:
                if chunk.kind in {"issue", "extra_task"} or not chunk.repository:
                    p_data["out_of_scope"].append((chunk, regular_entries))
                elif "frontend" in (chunk.repository or "").lower() or any(
                    "frontend" in str(c).lower() for c in chunk.categories
                ):
                    p_data["frontend"].append((chunk, impl_entries))
                else:
                    p_data["backend"].append((chunk, impl_entries))
            elif review_entries and impl_entries:
                p_data["reviewed"].append((chunk, review_entries))
                if "frontend" in (chunk.repository or "").lower() or any(
                    "frontend" in str(c).lower() for c in chunk.categories
                ):
                    p_data["frontend"].append((chunk, impl_entries))
                else:
                    p_data["backend"].append((chunk, impl_entries))
            elif not merge_entries:
                p_data["out_of_scope"].append((chunk, regular_entries))

        if overtime_entries:
            p_data["overtime"].append((chunk, overtime_entries))

    lines: list[str] = [date_header]

    for proj_name, p_data in projects.items():
        has_any = any(len(items) > 0 for items in p_data.values())
        if not has_any:
            continue

        lines.append(proj_name)

        if p_data["reviewed"]:
            lines.append("Reviewed PRs:")
            for chunk, entries in p_data["reviewed"]:
                ticket, clean_title = parse_ticket_and_title(chunk.title)
                pr_label = f"PR#{chunk.key}" if chunk.kind == "pr" else f"#{chunk.key}"
                if ticket:
                    lines.append(f"-> {ticket}: {clean_title} -> {pr_label}")
                else:
                    lines.append(f"-> {clean_title} -> {pr_label}")

                review_summary = report.summaries.get(
                    f"review:{chunk.repository or 'non-github'}:{chunk.kind}:{chunk.key}"
                )
                review_lines = _review_summary_lines(entries)
                if review_summary:
                    if review_lines and review_lines[0].startswith("Documented "):
                        lines.append(f"-> {review_lines[0]}")
                    compact_summary = re.sub(r"\s+", " ", clean_bullet_text(review_summary))
                    lines.append(f"-> Review impact: {ensure_period(compact_summary)}")
                lines.extend(_review_action_lines(entries, report))
                if not review_summary:
                    for finding in review_lines:
                        lines.append(f"-> {finding}")
                lines.extend(_pr_status_lines(chunk, report))
            lines.append("")

        if p_data["merged"]:
            lines.append("Merged PRs:")
            for chunk, entries in p_data["merged"]:
                _, clean_title = parse_ticket_and_title(chunk.title)
                lines.append(f"-> {clean_title} -> PR#{chunk.key}")
                merge_shas = [e.sha for e in entries if _is_pr_merge_commit(e, chunk) and e.sha]
                if merge_shas:
                    lines.append(f"-> Merge commit: {', '.join(dict.fromkeys(merge_shas))}")
                lines.extend(_pr_status_lines(chunk, report))
            lines.append("")

        if p_data["backend"]:
            lines.append("Backend PR:")
            for chunk, entries in p_data["backend"]:
                ticket, clean_title = parse_ticket_and_title(chunk.title)
                header_title = f"{ticket} | {clean_title}" if ticket else clean_title
                lines.append(header_title)

                pr_num = chunk.key
                summary = report.summaries.get(f"{chunk.repository}:{chunk.kind}:{chunk.key}")
                if summary:
                    lines.append(f"-> PR#{pr_num} -> {clean_bullet_text(summary)}")
                else:
                    non_merge_commits = [
                        e for e in entries if e.sha and first_line_of(e.text) and not is_merge_commit(e.text)
                    ]
                    if non_merge_commits:
                        primary_text = clean_commit_message(non_merge_commits[0].text)
                        lines.append(f"-> PR#{pr_num} -> {primary_text or clean_title}")
                    else:
                        lines.append(f"-> PR#{pr_num} -> {clean_title}")

                seen_bullets = {clean_title.lower()}
                non_merge_commits = [
                    e for e in entries if e.sha and first_line_of(e.text) and not is_merge_commit(e.text)
                ]
                if non_merge_commits:
                    seen_bullets.add(clean_commit_message(non_merge_commits[0].text).lower())

                added_secondary = 0
                for c in non_merge_commits[1:]:
                    cleaned_c = clean_commit_message(c.text)
                    if not cleaned_c or is_merge_commit(cleaned_c):
                        continue
                    c_lower = cleaned_c.lower()
                    if c_lower in seen_bullets:
                        continue
                    seen_bullets.add(c_lower)
                    lines.append(f"-> {ensure_period(cleaned_c)}")
                    added_secondary += 1
                    if added_secondary >= 3:
                        break

                commits = [e for e in entries if e.sha]
                if commits:
                    short_shas = [c.sha[:7] for c in commits if c.sha]
                    if short_shas:
                        lines.append(f"-> Committed: {', '.join(dict.fromkeys(short_shas))}")
                lines.extend(_pr_status_lines(chunk, report))
                lines.append("")

        if p_data["frontend"]:
            lines.append("Frontend PR:")
            for chunk, entries in p_data["frontend"]:
                ticket, clean_title = parse_ticket_and_title(chunk.title)
                header_title = f"{ticket} | {clean_title}" if ticket else clean_title
                lines.append(header_title)

                pr_num = chunk.key
                summary = report.summaries.get(f"{chunk.repository}:{chunk.kind}:{chunk.key}")
                if summary:
                    lines.append(f"-> PR#{pr_num} -> {clean_bullet_text(summary)}")
                else:
                    non_merge_commits = [
                        e for e in entries if e.sha and first_line_of(e.text) and not is_merge_commit(e.text)
                    ]
                    if non_merge_commits:
                        primary_text = clean_commit_message(non_merge_commits[0].text)
                        lines.append(f"-> PR#{pr_num} -> {primary_text or clean_title}")
                    else:
                        lines.append(f"-> PR#{pr_num} -> {clean_title}")

                seen_bullets = {clean_title.lower()}
                non_merge_commits = [
                    e for e in entries if e.sha and first_line_of(e.text) and not is_merge_commit(e.text)
                ]
                if non_merge_commits:
                    seen_bullets.add(clean_commit_message(non_merge_commits[0].text).lower())

                added_secondary = 0
                for c in non_merge_commits[1:]:
                    cleaned_c = clean_commit_message(c.text)
                    if not cleaned_c or is_merge_commit(cleaned_c):
                        continue
                    c_lower = cleaned_c.lower()
                    if c_lower in seen_bullets:
                        continue
                    seen_bullets.add(c_lower)
                    lines.append(f"-> {ensure_period(cleaned_c)}")
                    added_secondary += 1
                    if added_secondary >= 3:
                        break

                commits = [e for e in entries if e.sha]
                if commits:
                    short_shas = [c.sha[:7] for c in commits if c.sha]
                    if short_shas:
                        lines.append(f"-> Committed: {', '.join(dict.fromkeys(short_shas))}")
                lines.extend(_pr_status_lines(chunk, report))
                lines.append("")

        if p_data["out_of_scope"]:
            lines.append("Out of scope:")
            for chunk, entries in p_data["out_of_scope"]:
                if chunk.kind == "issue":
                    desc = chunk.title
                elif chunk.kind == "pr":
                    comment = next((first_line_of(e.text) for e in entries if e.text.strip()), "")
                    desc = f"Commented on PR#{chunk.key}: {comment or chunk.title}"
                else:
                    desc = chunk.description or chunk.title
                clean_desc = first_line_of(desc) or clean_bullet_text(desc)
                lines.append(f"-> {clean_desc}")
            lines.append("")

        if p_data["overtime"]:
            lines.append("Overtime:")
            for chunk, entries in p_data["overtime"]:
                ticket, clean_title = parse_ticket_and_title(chunk.title)
                pr_label = f"PR#{chunk.key}" if chunk.kind == "pr" else chunk.title
                lines.append(
                    f"-> Issue #{chunk.key}: {clean_title}" if chunk.kind == "issue" else f"-> {clean_title}"
                )
                if chunk.kind == "pr":
                    lines.extend(_review_action_lines(entries, report))
                    authored_commits = [e for e in entries if e.kind == "commit" and e.sha]
                    if authored_commits:
                        non_merge = [
                            e
                            for e in authored_commits
                            if first_line_of(e.text) and not is_merge_commit(e.text)
                        ]
                        work_desc = clean_commit_message(non_merge[0].text) if non_merge else clean_title
                        lines.append(f"-> {pr_label} -> {work_desc}")
                        short_shas = [c.sha[:7] for c in authored_commits if c.sha]
                        if short_shas:
                            lines.append(f"-> Committed: {', '.join(dict.fromkeys(short_shas))}")
                    else:
                        findings: list[str] = []
                        for e in entries:
                            if e.text and not e.text.startswith("(No comment"):
                                findings.extend(clean_review_finding(e.text))
                        work_desc = findings[0] if findings else "PR activity recorded."
                        lines.append(f"-> {pr_label} -> {work_desc}")
                    lines.extend(_pr_status_lines(chunk, report))
                elif chunk.kind == "issue":
                    for entry in entries:
                        if entry.kind == "issue_comment" and entry.text.strip():
                            comment = re.sub(r"^#+\s*", "", first_line_of(entry.text))
                            lines.append(f"-> Commented: {comment}")
                else:
                    authored_commits = [e for e in entries if e.kind == "commit" and e.sha]
                    if authored_commits:
                        short_shas = [c.sha[:7] for c in authored_commits if c.sha]
                        if short_shas:
                            lines.append(f"-> Committed: {', '.join(dict.fromkeys(short_shas))}")
                lines.append(EXTRA_TIME_NOTE)
            lines.append("")

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines).rstrip() + "\n"


def format_overtime_breakdown_only(report: DailyReport) -> str:
    overtime_chunks: list[tuple[ReportChunk, list[ReportEntry]]] = []
    for chunk in report.chunks:
        overtime_entries = [e for e in chunk.entries if is_out_of_report_shift(e.created_at, report)]
        if overtime_entries:
            overtime_chunks.append((chunk, overtime_entries))

    if not overtime_chunks:
        return ""

    lines: list[str] = []
    for chunk, entries in overtime_chunks:
        _, clean_title = parse_ticket_and_title(chunk.title)
        pr_label = f"PR#{chunk.key}" if chunk.kind == "pr" else chunk.title
        lines.append(
            f"-> Issue #{chunk.key}: {clean_title}" if chunk.kind == "issue" else f"-> {clean_title}"
        )
        if chunk.kind == "pr":
            lines.extend(_review_action_lines(entries, report))
            authored_commits = [e for e in entries if e.kind == "commit" and e.sha]
            if authored_commits:
                non_merge = [
                    e for e in authored_commits if first_line_of(e.text) and not is_merge_commit(e.text)
                ]
                work_desc = clean_commit_message(non_merge[0].text) if non_merge else clean_title
                lines.append(f"-> {pr_label} -> {work_desc}")
                short_shas = [c.sha[:7] for c in authored_commits if c.sha]
                if short_shas:
                    lines.append(f"-> Committed: {', '.join(dict.fromkeys(short_shas))}")
            else:
                findings: list[str] = []
                for e in entries:
                    if e.text and not e.text.startswith("(No comment"):
                        findings.extend(clean_review_finding(e.text))
                work_desc = findings[0] if findings else "PR activity recorded."
                lines.append(f"-> {pr_label} -> {work_desc}")
            lines.extend(_pr_status_lines(chunk, report))
        elif chunk.kind == "issue":
            for entry in entries:
                if entry.kind == "issue_comment" and entry.text.strip():
                    comment = re.sub(r"^#+\s*", "", first_line_of(entry.text))
                    lines.append(f"-> Commented: {comment}")
        else:
            authored_commits = [e for e in entries if e.kind == "commit" and e.sha]
            if authored_commits:
                short_shas = [c.sha[:7] for c in authored_commits if c.sha]
                if short_shas:
                    lines.append(f"-> Committed: {', '.join(dict.fromkeys(short_shas))}")
        lines.append(EXTRA_TIME_NOTE)
    return "\n".join(lines).strip()
