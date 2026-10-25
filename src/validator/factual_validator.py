from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from difflib import SequenceMatcher

from constants import ALLOWED_HEADINGS
from report.data_classes import EXTRA_TIME_NOTE, DailyReport, ReportChunk, chunk_id
from utils.format import clean_bullet_text, format_office_status, is_out_of_report_shift

from .data_classes.claim_evidence import ClaimEvidence
from .data_classes.factual_validation_result import FactualValidationResult


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _source_lines(report: DailyReport) -> dict[tuple[str, str], list[ReportChunk]]:
    """Associate each rendered line with the activity chunk that produced it."""
    sources: dict[tuple[str, str], list[ReportChunk]] = defaultdict(list)
    for chunk in report.chunks:
        section = ""
        for line in _lines(format_office_status(replace(report, chunks=(chunk,)))):
            if line in ALLOWED_HEADINGS:
                section = line
            elif not (line.startswith("STATUS (") or line in {"HR-Tool", "Foster Ferret", EXTRA_TIME_NOTE}):
                key = (section, line)
                if chunk not in sources[key]:
                    sources[key].append(chunk)
    return sources


class FactualValidator:
    @classmethod
    def validate(cls, text: str, report: DailyReport) -> FactualValidationResult:
        """Check consistency with activity data, not truth of source messages."""
        claims: list[ClaimEvidence] = []
        violations: list[str] = []
        lines = _lines(text)
        canonical = _lines(format_office_status(report))
        sources = _source_lines(report)

        matched: set[int] = set()
        for tag, _, _, start, end in SequenceMatcher(a=canonical, b=lines, autojunk=False).get_opcodes():
            if tag == "equal":
                matched.update(range(start, end))
        if lines != canonical:
            violations.append("Report text differs from the activity-backed rendering.")

        current_section = ""
        current_ticket: str | None = None
        active_chunk: ReportChunk | None = None
        for index, line in enumerate(lines):
            if line in ALLOWED_HEADINGS:
                current_section = line
                active_chunk = None
                current_ticket = None
                continue
            if line.startswith("STATUS (") or line in {"HR-Tool", "Foster Ferret", EXTRA_TIME_NOTE}:
                continue

            pr_match = re.search(r"PR#(\d+)", line)
            pr_num = int(pr_match.group(1)) if pr_match else None
            candidates = sources.get((current_section, line), [])
            is_chunk_header = current_section in {"Backend PR:", "Frontend PR:"} and not line.startswith(
                ("->", "(")
            )
            chunk = active_chunk if not is_chunk_header and active_chunk in candidates else None
            if chunk is None and len(candidates) == 1:
                chunk = candidates[0]
            if chunk is None and candidates and current_section in {"Backend PR:", "Frontend PR:"}:
                label = "frontend" if current_section == "Frontend PR:" else "backend"
                scoped = [c for c in candidates if label in (c.repository or "").lower()]
                if len(scoped) == 1:
                    chunk = scoped[0]
            if (
                chunk is None
                and not is_chunk_header
                and active_chunk is not None
                and (pr_num is not None or line.startswith("-> Committed:"))
            ):
                chunk = active_chunk
            if chunk is None and pr_num is not None:
                same_number = [
                    c for c in report.chunks if c.kind == "pr" and c.key == str(pr_num)
                ]
                if len(same_number) == 1:
                    chunk = same_number[0]

            if is_chunk_header:
                current_ticket = line.split("|", 1)[0].strip() if "|" in line else None
                active_chunk = chunk
                continue
            if chunk is not None:
                active_chunk = chunk

            commit_match = re.fullmatch(r"-> (?:Committed|Merge commit):\s*([A-Za-z0-9,\s]+)", line)
            commit_shas = (
                [sha.strip().lower() for sha in commit_match.group(1).split(",") if sha.strip()]
                if commit_match
                else []
            )
            claim_type = "general"
            if current_section == "Reviewed PRs:":
                claim_type = "review"
            elif current_section == "Merged PRs:":
                claim_type = "merge"
            elif current_section in {"Backend PR:", "Frontend PR:"}:
                claim_type = "pr_implementation" if pr_num else "commit"
            elif current_section == "Out of scope:":
                claim_type = "out_of_scope"
            elif current_section == "Overtime:":
                claim_type = "overtime"
            if line.startswith(("-> Merged", "-> Merge status:")):
                claim_type = "merge_status"
            elif line.startswith("-> Review by"):
                claim_type = "review_action"
            elif line.startswith("-> PR comment by"):
                claim_type = "pr_comment"

            verified = index in matched and chunk is not None
            evidence_id = chunk_id(chunk) if chunk is not None else None
            source_url = chunk.url if chunk is not None else ""
            if index not in matched:
                violations.append(f"Line is not in the activity-backed rendering: {line}")
            if chunk is None:
                violations.append(f"No unique source chunk for: {line}")

            if pr_num is not None and chunk is not None:
                if chunk.kind != "pr" or chunk.key != str(pr_num):
                    verified = False
                    violations.append(f"PR#{pr_num} does not match its source chunk.")
                elif claim_type == "review" and not any(
                    e.kind in {"review", "review_comment", "issue_comment"} for e in chunk.entries
                ):
                    verified = False
                    violations.append(f"PR#{pr_num} has no review event by the author.")
                elif claim_type == "pr_implementation" and not any(
                    e.kind in {"commit", "pr_created"} for e in chunk.entries
                ):
                    verified = False
                    violations.append(f"PR#{pr_num} has no implementation event by the author.")
                elif claim_type == "merge" and not any(e.kind == "pr_merged" for e in chunk.entries):
                    verified = False
                    violations.append(f"PR#{pr_num} has no merge event by the author.")

            if chunk is not None and chunk.kind == "pr":
                if line.startswith("-> Merged") and not (
                    chunk.merge_status_verified and chunk.merged_at
                ):
                    verified = False
                    violations.append(f"PR#{chunk.key} has no verified merge metadata.")
                summary = report.summaries.get(chunk_id(chunk))
                if summary and line == f"-> PR#{chunk.key} -> {clean_bullet_text(summary)}":
                    verified = False
                    violations.append(f"AI summary for PR#{chunk.key} requires independent review.")

            if commit_shas and chunk is not None:
                for sha in commit_shas:
                    found = [
                        e
                        for e in chunk.entries
                        if e.kind == "commit" and e.sha and e.sha.lower().startswith(sha)
                    ]
                    if len(found) != 1:
                        verified = False
                        violations.append(f"Commit {sha} is not unique in its source chunk.")
                        continue
                    evidence_id = found[0].id
                    source_url = found[0].url or source_url
                    if current_section == "Overtime:" and not is_out_of_report_shift(
                        found[0].created_at, report
                    ):
                        verified = False
                        violations.append(f"Commit {sha} occurred during the regular shift.")

            is_pr_metadata = line.startswith(("-> PR link:", "-> Merge status:", "-> Merged"))
            merge_happened_overtime = bool(
                chunk is not None
                and chunk.kind == "pr"
                and line.startswith("-> Merged")
                and any(
                    e.kind == "pr_merged" and is_out_of_report_shift(e.created_at, report)
                    for e in chunk.entries
                )
            )

            if (
                current_section == "Overtime:"
                and chunk is not None
                and not is_pr_metadata
                and not any(is_out_of_report_shift(e.created_at, report) for e in chunk.entries)
            ):
                verified = False
                violations.append(f"No out-of-shift event supports: {line}")

            claims.append(
                ClaimEvidence(
                    claim=line,
                    type=claim_type,
                    date=report.work_date,
                    ticket_id=current_ticket,
                    pr_number=pr_num,
                    commit_sha=commit_shas[0] if commit_shas else None,
                    evidence_id=evidence_id,
                    verified=verified,
                    source=source_url,
                    extra_time=current_section == "Overtime:"
                    and (not is_pr_metadata or merge_happened_overtime),
                )
            )

        total_claims = len(claims)
        supported_claims = sum(claim.verified for claim in claims)
        unsupported_claims = total_claims - supported_claims
        overtime_claims = [claim for claim in claims if claim.extra_time]
        verified_overtime = sum(claim.verified for claim in overtime_claims)
        return FactualValidationResult(
            is_valid=not violations and unsupported_claims == 0,
            fact_support_percent=(supported_claims / total_claims * 100.0) if total_claims else 100.0,
            total_claims=total_claims,
            supported_claims=supported_claims,
            contradicted_claims=sum("does not match" in v for v in violations),
            unsupported_claims=unsupported_claims,
            overtime_attribution_percent=(
                verified_overtime / len(overtime_claims) * 100.0 if overtime_claims else 100.0
            ),
            claims=claims,
            violations=violations,
        )
