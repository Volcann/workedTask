from __future__ import annotations

import re

from constants import ALLOWED_HEADINGS, PROHIBITED_WORDS
from report.data_classes import EXTRA_TIME_NOTE

from .data_classes.format_validation_result import FormatValidationResult


class StrictFormatValidator:
    @classmethod
    def validate(cls, text: str) -> FormatValidationResult:
        lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
        if not lines:
            return FormatValidationResult(
                is_valid=False,
                compliance_percent=0.0,
                total_rules=8,
                passed_rules=0,
                failed_rules=["Empty status report"],
            )

        passed: dict[str, bool] = {}

        header = lines[0]
        header_match = re.match(r"^STATUS \((\d{2}-[A-Z]{3}-\d{4})\)$", header)
        passed["rule_status_header"] = bool(header_match)

        if len(lines) == 1:
            compliance = 100.0 if passed["rule_status_header"] else 0.0
            return FormatValidationResult(
                is_valid=passed["rule_status_header"],
                compliance_percent=compliance,
                total_rules=1,
                passed_rules=1 if passed["rule_status_header"] else 0,
                failed_rules=[] if passed["rule_status_header"] else ["Invalid STATUS header"],
                details=passed,
            )

        project_name = lines[1]
        passed["rule_project_header"] = bool(
            project_name
            and not project_name.startswith("->")
            and not project_name.startswith("#")
            and project_name not in ALLOWED_HEADINGS
        )

        headings_found = [
            line
            for line in lines[2:]
            if line.endswith(":")
            and not line.startswith("->")
            and not line.startswith("(")
            and ("|" not in line or line in ALLOWED_HEADINGS)
        ]
        invalid_headings = [h for h in headings_found if h not in ALLOWED_HEADINGS]
        passed["rule_category_headings"] = len(invalid_headings) == 0

        bullets_valid = True
        for i, line in enumerate(lines[2:], start=2):
            if line in ALLOWED_HEADINGS or line == EXTRA_TIME_NOTE:
                continue
            if "|" in line and not line.startswith("->"):
                continue
            if line in {"HR-Tool", "Foster Ferret"} or (
                i + 1 < len(lines) and lines[i + 1] in ALLOWED_HEADINGS
            ):
                continue
            if not line.startswith("->") and not line.startswith("("):
                if i + 1 < len(lines) and (
                    lines[i + 1].startswith("-> PR#")
                    or lines[i + 1].startswith("-> #")
                    or lines[i + 1].startswith("->")
                ):
                    continue
                bullets_valid = False
                break
        passed["rule_arrow_bullets"] = bullets_valid

        has_overtime_section = "Overtime:" in lines
        if has_overtime_section:
            ot_idx = lines.index("Overtime:")
            ot_lines = lines[ot_idx + 1 :]
            passed["rule_overtime_sentence"] = EXTRA_TIME_NOTE in ot_lines
        else:
            passed["rule_overtime_sentence"] = True

        has_markdown_artifacts = any(line.startswith(("#", "|")) or "|---" in line for line in lines)
        passed["rule_no_markdown_artifacts"] = not has_markdown_artifacts

        lower_text = text.lower()
        has_prohibited_words = any(buzz in lower_text for buzz in PROHIBITED_WORDS)
        passed["rule_no_corporate_buzzwords"] = not has_prohibited_words

        has_pr_without_hash = bool(re.search(r"\bPR\s+\d+\b", text))
        passed["rule_identifier_format"] = not has_pr_without_hash

        total_rules = len(passed)
        passed_rules = sum(1 for v in passed.values() if v)
        failed_rules = [k for k, v in passed.items() if not v]
        compliance_percent = (passed_rules / total_rules) * 100.0

        return FormatValidationResult(
            is_valid=compliance_percent == 100.0,
            compliance_percent=compliance_percent,
            total_rules=total_rules,
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            details=passed,
        )
