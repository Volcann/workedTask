"""Validation Pipeline for verifying status report claims against ground-truth Git evidence.

Filters out hallucinated, misleading, or low-evidence claims (such as fabricated endpoints,
unsupported testing assertions, or nonexistent commit hashes) and reports what was removed and why.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field

from status_reporter.models.models import (
    DailyReport,
    ProjectActivity,
    PullRequestInfo,
    RemovedItem,
    ReviewInfo,
)
from status_reporter.shared.utils import clean_commit_message

logger = logging.getLogger(__name__)

# Common English and Markdown stopwords for keyword overlap checking
STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "cannot",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "its",
    "itself",
    "let",
    "me",
    "more",
    "most",
    "must",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "with",
    "would",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "pr",
    "commit",
    "tested",
    "added",
    "updated",
    "via",
    "new",
    "allows",
    "allowing",
    "using",
    "across",
    "within",
    "per",
    "well",
    "pass",
    "passes",
}


@dataclass
class ValidationResult:
    """Result of passing a report or activity through the validation pipeline."""

    report: DailyReport
    total_checked: int = 0
    total_passed: int = 0
    total_removed: int = 0
    removed_items: list[RemovedItem] = field(default_factory=list)

    @property
    def has_removals(self) -> bool:
        return bool(self.removed_items)

    def format_summary(self) -> str:
        """Format a human-readable summary of removed items and rationale."""
        if not self.removed_items:
            return "✅ Validation Pipeline: All claims verified against Git commits and diffs (0 removed)."

        lines = [
            f"🛡️ Validation Pipeline: Excluded {len(self.removed_items)} misleading or low-validation claim(s):"
        ]
        for item in self.removed_items:
            lines.append(f'   • [{item.target}] Removed: "{item.bullet}"')
            lines.append(f"     ↳ Reason: {item.reason}")
        return "\n".join(lines)


class StatusValidator:
    """Validates daily status report items against actual Git commits, diffs, and PR evidence."""

    def __init__(
        self,
        sleep_interval: float = 0.0,
        verbose: bool = True,
        strict_endpoints: bool = True,
        strict_commits: bool = True,
    ) -> None:
        self.sleep_interval = sleep_interval
        self.verbose = verbose
        self.strict_endpoints = strict_endpoints
        self.strict_commits = strict_commits

    def _sleep_pacing(self) -> None:
        """Pause execution to preserve API rate limits and quota if sleep_interval > 0."""
        if self.sleep_interval > 0 and not os.getenv("PYTEST_CURRENT_TEST"):
            if self.verbose:
                print(
                    f"      ⏳ Quota guard: sleeping {self.sleep_interval:.1f}s to protect API quota...",
                    file=sys.stderr,
                )
            time.sleep(self.sleep_interval)

    def validate_report(self, report: DailyReport) -> ValidationResult:
        """Validate an entire DailyReport, stripping low-validation claims and logging reasons."""
        result = ValidationResult(report=report)

        for project_activity in report.projects:
            self._validate_project_activity(project_activity, result)

        report.removed_items = result.removed_items
        return result

    def _validate_project_activity(
        self,
        activity: ProjectActivity,
        result: ValidationResult,
    ) -> None:
        """Validate activities for a single project configuration."""
        for pr in activity.own_prs:
            self._validate_pr_bullets(pr, activity, is_foreign=False, result=result)

        for pr in activity.foreign_contributions:
            self._validate_pr_bullets(pr, activity, is_foreign=True, result=result)

        for review in activity.reviewed_prs:
            self._validate_review_bullets(review, activity, result=result)

    def _validate_pr_bullets(
        self,
        pr: PullRequestInfo,
        activity: ProjectActivity,
        is_foreign: bool,
        result: ValidationResult,
    ) -> None:
        """Validate bullets for a pull request against author commits, diffs, and comments."""
        if not pr.bullets:
            return

        author_commits = pr.author_commits or pr.commits
        valid_shas = {c.short_sha.lower() for c in author_commits if c.short_sha}
        valid_shas.update(c.sha[:7].lower() for c in author_commits if c.sha)

        # Collect changed files across author commits and PR
        changed_files: set[str] = set()
        for c in author_commits:
            changed_files.update(c.files)
        changed_files.update(pr.files_changed)

        # Build corpus of verified commit messages and bodies
        commit_corpus = " ".join(f"{c.headline} {c.body}" for c in author_commits).lower()
        pr_corpus = f"{pr.title} {pr.body} {' '.join(pr.comments)} {commit_corpus}".lower()

        # Determine if any API endpoint/view/url files were touched
        has_api_files = any(
            re.search(
                r"(?:views?|urls?|routes?|endpoints?|serializers?|controllers?|api\/)",
                f,
                re.IGNORECASE,
            )
            for f in changed_files
        )

        validated_bullets: list[str] = []

        for bullet in pr.bullets:
            result.total_checked += 1
            clean_b = bullet.strip()
            if not clean_b:
                continue

            # Keep canonical header for foreign PRs
            if is_foreign and clean_b.startswith(f"PR#{pr.number} -> Contributed authored commit"):
                validated_bullets.append(bullet)
                result.total_passed += 1
                continue

            # Check 1: Commit hash verification
            if self.strict_commits:
                cited_shas = re.findall(
                    r"(?:commit|hash)?[:\s]*([0-9a-fA-F]{7,40})", clean_b, re.IGNORECASE
                )
                invalid_shas = [s for s in cited_shas if s.lower()[:7] not in valid_shas]
                if invalid_shas:
                    reason = f"Referenced commit hash(es) {invalid_shas} not found in author's commits for this PR."
                    result.total_removed += 1
                    result.removed_items.append(
                        RemovedItem(
                            target=f"PR#{pr.number}",
                            project=f"{activity.project_name} / {activity.category}",
                            bullet=clean_b,
                            reason=reason,
                        )
                    )
                    continue

            # Check 2: Endpoint creation & testing verification
            if self.strict_endpoints:
                # Detect claims of endpoint creation or specific endpoint routes
                has_endpoint_mention = bool(
                    re.search(
                        r"(?:added|created|implemented|new|delivery)\s+(?:[a-zA-Z0-9_\-\s]*)(?:endpoints?|api endpoints?)",
                        clean_b,
                        re.IGNORECASE,
                    )
                    or re.search(r"\/api\/v\d+\/[a-zA-Z0-9_\-\/]+", clean_b)
                    or re.search(
                        r"(?:POST|GET|PUT|DELETE|PATCH)\s+endpoint", clean_b, re.IGNORECASE
                    )
                )

                if has_endpoint_mention:
                    # 1. Look for explicit route mentioned in the bullet
                    route_match = re.search(r"(\/api\/v\d+\/[a-zA-Z0-9_\-\/]+)", clean_b)
                    if route_match:
                        route = route_match.group(1).lower()
                        # The route must explicitly appear in commit messages, bodies, or PR comments
                        if route not in pr_corpus:
                            reason = (
                                f"Referenced fictitious endpoint '{route_match.group(1)}' and delivery testing "
                                f"not supported by actual commits or files."
                            )
                            result.total_removed += 1
                            result.removed_items.append(
                                RemovedItem(
                                    target=f"PR#{pr.number}",
                                    project=f"{activity.project_name} / {activity.category}",
                                    bullet=clean_b,
                                    reason=reason,
                                )
                            )
                            continue

                    # 2. Check general endpoint creation / testing claims
                    # Extract the subject/feature before "endpoint(s)"
                    m_feature = re.search(
                        r"(\b\w+\b)\s+(?:creation\s+|api\s+)?endpoints?",
                        clean_b,
                        re.IGNORECASE,
                    )
                    feature_keyword = m_feature.group(1).lower() if m_feature else ""

                    # Check if there are API view/url/serializer files for this specific feature
                    has_feature_api = False
                    if feature_keyword and feature_keyword not in (
                        "new",
                        "added",
                        "created",
                        "the",
                        "post",
                        "get",
                    ):
                        has_feature_api = any(
                            feature_keyword in f.lower()
                            and re.search(
                                r"(?:views?|urls?|routes?|endpoints?|serializers?)",
                                f,
                                re.IGNORECASE,
                            )
                            for f in changed_files
                        )
                    else:
                        has_feature_api = has_api_files

                    if not has_feature_api and "endpoint" not in commit_corpus:
                        target_mention = m_feature.group(0) if m_feature else "endpoints"
                        reason = (
                            f"Claimed endpoint creation or testing ('{target_mention}'), "
                            f"but no matching API view, URL, or serializer files were added or modified in the commits."
                        )
                        result.total_removed += 1
                        result.removed_items.append(
                            RemovedItem(
                                target=f"PR#{pr.number}",
                                project=f"{activity.project_name} / {activity.category}",
                                bullet=clean_b,
                                reason=reason,
                            )
                        )
                        continue

            # Check 3: Semantic grounding / evidence check
            # Extract distinctive alphanumeric words (length >= 4) not in stopwords
            tokens = {
                w.lower()
                for w in re.findall(r"\b[A-Za-z][A-Za-z0-9_]{3,}\b", clean_b)
                if w.lower() not in STOPWORDS
            }

            if tokens:
                # Count how many tokens are supported by commits, files, or comments
                supported_tokens = {
                    t
                    for t in tokens
                    if t in pr_corpus or any(t in f.lower() for f in changed_files)
                }
                support_ratio = len(supported_tokens) / len(tokens)

                # If support ratio is extremely low (< 20%) and multiple tokens exist
                if len(tokens) >= 4 and support_ratio < 0.20:
                    unsupported = tokens - supported_tokens
                    reason = (
                        f"Low evidence in Git commits (support ratio: {support_ratio:.0%}). "
                        f"Unverified terms: {sorted(unsupported)[:5]}."
                    )
                    result.total_removed += 1
                    result.removed_items.append(
                        RemovedItem(
                            target=f"PR#{pr.number}",
                            project=f"{activity.project_name} / {activity.category}",
                            bullet=clean_b,
                            reason=reason,
                        )
                    )
                    continue

            # Passed all checks
            result.total_passed += 1
            validated_bullets.append(bullet)

        # Fallback handling: If all bullets were filtered out or only the foreign header remains
        non_header_bullets = [
            b
            for b in validated_bullets
            if not b.startswith(f"PR#{pr.number} -> Contributed authored commit")
        ]

        if not non_header_bullets:
            if author_commits:
                # Construct grounded fallback bullet from the most significant author commit headline
                fallback_text = clean_commit_message(author_commits[0].headline)
                if fallback_text:
                    if is_foreign:
                        validated_bullets.append(fallback_text)
                    else:
                        validated_bullets = [f"PR#{pr.number} -> {fallback_text}"]
                    if self.verbose:
                        print(
                            f'      🛡️ [PR#{pr.number}] Replaced filtered bullets with grounded commit headline: "{fallback_text[:50]}"',
                            file=sys.stderr,
                        )

        pr.bullets = validated_bullets
        self._sleep_pacing()

    def _validate_review_bullets(
        self,
        review: ReviewInfo,
        activity: ProjectActivity,
        result: ValidationResult,
    ) -> None:
        """Validate review bullets against actual review comments."""
        if not review.review_bullets:
            return

        comments_corpus = " ".join(review.comments).lower()
        validated: list[str] = []

        for bullet in review.review_bullets:
            result.total_checked += 1
            clean_b = bullet.strip()
            if not clean_b:
                continue

            tokens = {
                w.lower()
                for w in re.findall(r"\b[A-Za-z][A-Za-z0-9_]{3,}\b", clean_b)
                if w.lower() not in STOPWORDS
            }

            if tokens and review.comments:
                supported = {
                    t for t in tokens if t in comments_corpus or t in review.pr_title.lower()
                }
                support_ratio = len(supported) / len(tokens)
                if len(tokens) >= 4 and support_ratio < 0.20:
                    reason = f"Review bullet not supported by review comments (support ratio: {support_ratio:.0%})."
                    result.total_removed += 1
                    result.removed_items.append(
                        RemovedItem(
                            target=f"Review PR#{review.pr_number}",
                            project=f"{activity.project_name} / {activity.category}",
                            bullet=clean_b,
                            reason=reason,
                        )
                    )
                    continue

            result.total_passed += 1
            validated.append(bullet)

        review.review_bullets = validated
        self._sleep_pacing()
