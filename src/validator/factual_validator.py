from __future__ import annotations

import re

from constants import ALLOWED_HEADINGS
from report.data_classes import EXTRA_TIME_NOTE, DailyReport, ReportChunk, ReportEntry
from utils.format import is_out_of_shift

from .data_classes.claim_evidence import ClaimEvidence
from .data_classes.factual_validation_result import FactualValidationResult


class FactualValidator:
    @classmethod
    def validate(cls, text: str, report: DailyReport) -> FactualValidationResult:
        claims: list[ClaimEvidence] = []
        violations: list[str] = []

        pr_chunks_by_number: dict[int, list[ReportChunk]] = {}
        commits_by_sha: dict[str, ReportEntry] = {}
        all_entries: list[ReportEntry] = []

        for chunk in report.chunks:
            if chunk.kind == "pr":
                try:
                    pr_num = int(chunk.key)
                    pr_chunks_by_number.setdefault(pr_num, []).append(chunk)
                except ValueError:
                    pass
            for entry in chunk.entries:
                all_entries.append(entry)
                if entry.sha:
                    commits_by_sha[entry.sha[:7].lower()] = entry
                    commits_by_sha[entry.sha.lower()] = entry

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        current_section = None
        current_ticket = None

        for line in lines:
            if line in ALLOWED_HEADINGS:
                current_section = line
                continue
            if line.startswith("STATUS (") or line in {"HR-Tool", "Foster Ferret"}:
                continue
            if line == EXTRA_TIME_NOTE:
                continue

            if (
                current_section in {"Backend PR:", "Frontend PR:"}
                and not line.startswith("->")
                and not line.startswith("(")
            ):
                if "|" in line:
                    parts = line.split("|", 1)
                    t_id = parts[0].strip()
                    current_ticket = t_id
                else:
                    current_ticket = None
                continue

            pr_match = re.search(r"PR#(\d+)", line)
            pr_num = int(pr_match.group(1)) if pr_match else None

            commit_match = re.search(r"Committed:\s*([0-9a-fA-F,\s]+)", line)
            commit_shas: list[str] = []
            if commit_match:
                commit_shas = [s.strip().lower() for s in commit_match.group(1).split(",") if s.strip()]

            claim_type = "general"
            if current_section == "Reviewed PRs:":
                claim_type = "review"
            elif current_section in {"Backend PR:", "Frontend PR:"}:
                claim_type = "pr_implementation" if pr_num else "commit"
            elif current_section == "Out of scope:":
                claim_type = "out_of_scope"
            elif current_section == "Overtime:":
                claim_type = "overtime"

            verified = True
            source_url = ""
            evidence_id = None
            notes = ""
            extra_time = current_section == "Overtime:"

            if pr_num is not None:
                matching_chunks = pr_chunks_by_number.get(pr_num, [])
                if not matching_chunks:
                    verified = False
                    violations.append(f"PR#{pr_num} cited in text but not present in daily report evidence.")
                else:
                    if claim_type == "review":
                        target_chunk = next(
                            (
                                c
                                for c in matching_chunks
                                if any(
                                    e.kind in {"review", "review_comment", "issue_comment"} for e in c.entries
                                )
                            ),
                            matching_chunks[0],
                        )
                        has_review_event = any(
                            e.kind in {"review", "review_comment", "issue_comment"}
                            for e in target_chunk.entries
                        )
                        if not has_review_event:
                            verified = False
                            violations.append(
                                f"PR#{pr_num} listed as review but contains no review events by author."
                            )
                    elif claim_type == "pr_implementation":
                        target_chunk = next(
                            (
                                c
                                for c in matching_chunks
                                if any(e.sha or e.kind == "pr_created" for e in c.entries)
                            ),
                            matching_chunks[0],
                        )
                        has_author_work = any(e.sha or e.kind == "pr_created" for e in target_chunk.entries)
                        if not has_author_work:
                            notes = "PR listed under implementation based on comments/presence."
                    else:
                        target_chunk = matching_chunks[0]

                    source_url = target_chunk.url
                    evidence_id = f"{target_chunk.repository}:pr:{pr_num}"

            if commit_shas:
                for sha in commit_shas:
                    clean_sha = sha[:7]
                    matched_entry = next(
                        (e for s, e in commits_by_sha.items() if s.startswith(clean_sha)), None
                    )
                    if not matched_entry:
                        verified = False
                        violations.append(f"Commit {sha} cited in text but not present in daily commits.")
                    else:
                        evidence_id = matched_entry.id
                        if current_section == "Overtime:" and not is_out_of_shift(
                            matched_entry.created_at, report.timezone
                        ):
                            verified = False
                            violations.append(
                                f"Commit {sha} listed in Overtime occurred during regular shift."
                            )

            if current_section == "Overtime:":
                extra_time = True
                if pr_num and pr_num in pr_chunks_by_number:
                    matching_chunks = pr_chunks_by_number[pr_num]
                    target_chunk = next(
                        (
                            c
                            for c in matching_chunks
                            if any(is_out_of_shift(e.created_at, report.timezone) for e in c.entries)
                        ),
                        matching_chunks[0],
                    )
                    has_overtime_event = any(
                        is_out_of_shift(e.created_at, report.timezone) for e in target_chunk.entries
                    )
                    if not has_overtime_event:
                        verified = False
                        violations.append(
                            f"PR#{pr_num} listed in Overtime but all events occurred during regular shift."
                        )

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
                    extra_time=extra_time,
                    notes=notes,
                )
            )

        total_claims = len(claims)
        supported_claims = sum(1 for c in claims if c.verified)
        unsupported_claims = total_claims - supported_claims
        contradicted_claims = len([v for v in violations if "not present" in v])

        overtime_claims = [c for c in claims if c.extra_time]
        verified_overtime = sum(1 for c in overtime_claims if c.verified)
        ot_attrib_pct = (verified_overtime / len(overtime_claims) * 100.0) if overtime_claims else 100.0

        fact_support_pct = (supported_claims / total_claims * 100.0) if total_claims else 100.0

        return FactualValidationResult(
            is_valid=(fact_support_pct == 100.0 and contradicted_claims == 0 and unsupported_claims == 0),
            fact_support_percent=fact_support_pct,
            total_claims=total_claims,
            supported_claims=supported_claims,
            contradicted_claims=contradicted_claims,
            unsupported_claims=unsupported_claims,
            overtime_attribution_percent=ot_attrib_pct,
            claims=claims,
            violations=violations,
        )
