"""Activity collector orchestrating GitHub queries across configured projects."""

from __future__ import annotations

import logging
import sys
from datetime import date
from typing import Sequence

from status_reporter.ai_enhancer import AIEnhancer
from status_reporter.github_client import GitHubClient, is_author_match
from status_reporter.models import (
    BranchActivity,
    CommitInfo,
    DailyReport,
    ProjectActivity,
    ProjectConfig,
    PullRequestInfo,
    ReviewInfo,
)
from status_reporter.utils import (
    clean_commit_message,
    clean_markdown_bullets,
    format_status_date,
)

logger = logging.getLogger(__name__)


class ActivityCollector:
    """Collects daily commits, pull requests, reviews, and contributions across projects."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        ai_enhancer: AIEnhancer | None = None,
        use_ai: bool = True,
        verbose: bool = True,
    ) -> None:
        self.github_client = github_client or GitHubClient()
        self.ai_enhancer = ai_enhancer or AIEnhancer()
        self.use_ai = use_ai
        self.verbose = verbose

    def collect_for_date(
        self,
        projects: Sequence[ProjectConfig],
        target_date: date,
    ) -> DailyReport:
        """Scan all projects for a specific date and compile a DailyReport."""
        project_activities: list[ProjectActivity] = []

        for p in projects:
            if not p.enabled:
                continue
            activity = self._collect_project_activity(p, target_date)
            if activity.has_activity:
                project_activities.append(activity)

        date_display = format_status_date(target_date)
        return DailyReport(
            target_date=target_date,
            date_display=date_display,
            projects=project_activities,
        )

    def _collect_project_activity(
        self,
        project: ProjectConfig,
        target_date: date,
    ) -> ProjectActivity:
        """Collect activity for a single project configuration."""
        owner = project.owner
        repo = project.repo
        author = project.author
        local_path = project.local_path

        activity = ProjectActivity(
            project_name=project.name,
            category=project.category,
            owner=owner,
            repo=repo,
        )

        if self.verbose:
            print(
                f"\n📂 [{project.name} / {project.category}] ({project.full_name})",
                file=sys.stderr,
            )
            print(f"   ↳ Author: {author}", file=sys.stderr)

        # 1. Fetch own PRs created/merged on that day
        prs = self.github_client.get_user_prs_for_date(
            owner, repo, author, target_date, local_path=local_path
        )
        own_prs_map: dict[int, PullRequestInfo] = {}
        for pr in prs:
            pr.project_name = project.name
            pr.category = project.category

            # Search results do not always contain commit details. Hydrate the PR
            # before attributing implementation work to the configured author.
            if not pr.commits:
                full_pr = self.github_client.get_pr_details(
                    owner, repo, pr.number, local_path=local_path, author=author
                )
                if isinstance(full_pr, PullRequestInfo):
                    pr.body = full_pr.body or pr.body
                    pr.commits = full_pr.commits
                    pr.head_ref = full_pr.head_ref or pr.head_ref

            pr.author_commits = [
                commit
                for commit in pr.commits
                if is_author_match(
                    author,
                    name=commit.author_name,
                    login=commit.author_login,
                )
            ]
            own_prs_map[pr.number] = pr

        # 2. Fetch commits on that day
        commits = self.github_client.get_user_commits_for_date(
            owner, repo, author, target_date, local_path=local_path
        )

        if self.verbose:
            if commits:
                print(
                    f"   ↳ Found {len(commits)} commit(s) authored on {target_date}:",
                    file=sys.stderr,
                )
            else:
                print(f"   ↳ No commits authored on {target_date}", file=sys.stderr)

        foreign_prs_map: dict[int, PullRequestInfo] = {}
        branch_commits_map: dict[str, list[CommitInfo]] = {}

        for commit in commits:
            # Check if this commit belongs to an already loaded own PR
            matched_pr_num = None
            for pr_num, pr in own_prs_map.items():
                if any(c.sha == commit.sha for c in pr.commits):
                    if not any(c.sha == commit.sha for c in pr.author_commits):
                        pr.author_commits.append(commit)
                    matched_pr_num = pr_num
                    break

            if matched_pr_num is not None:
                if self.verbose:
                    print(
                        f'      • {commit.short_sha}: "{commit.headline[:48]}" ➔ PR#{matched_pr_num}',
                        file=sys.stderr,
                    )
                continue

            for pr_num, pr in foreign_prs_map.items():
                if any(c.sha == commit.sha for c in pr.commits):
                    if not any(c.sha == commit.sha for c in pr.author_commits):
                        pr.author_commits.append(commit)
                    matched_pr_num = pr_num
                    break

            if matched_pr_num is not None:
                if self.verbose:
                    print(
                        f'      • {commit.short_sha}: "{commit.headline[:48]}" ➔ PR#{matched_pr_num} (foreign)',
                        file=sys.stderr,
                    )
                continue

            # Check what PRs this commit belongs to via git ancestry or GitHub API
            pulls = self.github_client.get_commit_pull_requests(
                owner, repo, commit.sha, local_path=local_path
            )
            if pulls:
                pr_item = pulls[0]
                pr_num = pr_item.get("number")
                if pr_num:
                    if pr_num in own_prs_map:
                        if not any(c.sha == commit.sha for c in own_prs_map[pr_num].author_commits):
                            own_prs_map[pr_num].author_commits.append(commit)
                    elif pr_num in foreign_prs_map:
                        if not any(
                            c.sha == commit.sha for c in foreign_prs_map[pr_num].author_commits
                        ):
                            foreign_prs_map[pr_num].author_commits.append(commit)
                    else:
                        # Fetch full PR details
                        full_pr = self.github_client.get_pr_details(
                            owner, repo, pr_num, local_path=local_path, author=author
                        )
                        if full_pr:
                            full_pr.project_name = project.name
                            full_pr.category = project.category
                            full_pr.author_commits.append(commit)
                            if full_pr.author_login:
                                is_own = is_author_match(author, login=full_pr.author_login)
                            else:
                                is_own = full_pr.is_own
                            full_pr.is_own = is_own
                            if is_own:
                                own_prs_map[pr_num] = full_pr
                            else:
                                foreign_prs_map[pr_num] = full_pr

                    if self.verbose:
                        print(
                            f'      • {commit.short_sha}: "{commit.headline[:48]}" ➔ PR#{pr_num}',
                            file=sys.stderr,
                        )
            else:
                # Commit is not in any PR -> Standalone branch commit
                branch = (
                    commit.branch
                    or self.github_client.get_commit_branch(
                        owner,
                        repo,
                        commit.sha,
                        commit_message=commit.message,
                        local_path=local_path,
                    )
                    or "main"
                )
                branch_commits_map.setdefault(branch, []).append(commit)
                if self.verbose:
                    print(
                        f"      • {commit.short_sha}: \"{commit.headline[:48]}\" ➔ Branch: '{branch}'",
                        file=sys.stderr,
                    )

        # 3. Fetch reviewed PRs and their comments
        reviewed = self.github_client.get_user_reviewed_prs_for_date(
            owner, repo, author, target_date, local_path=local_path
        )
        for r in reviewed:
            r.project_name = project.name
            r.category = project.category
            if r.pr_number:
                comments = self.github_client.get_pr_user_comments(
                    owner, repo, r.pr_number, author, target_date, local_path=local_path
                )
                if isinstance(comments, list) and comments:
                    r.comments = comments
                    r.review_bullets = self._synthesize_review_bullets(r)

        activity.reviewed_prs = reviewed

        if self.verbose:
            if reviewed:
                print(
                    f"   ↳ Found {len(reviewed)} reviewed/merged PR(s):",
                    file=sys.stderr,
                )
                for r in reviewed:
                    comment_info = f" ({len(r.comments)} user comment(s))" if r.comments else ""
                    print(
                        f"      • PR#{r.pr_number}: {r.pr_title[:60]}{comment_info}",
                        file=sys.stderr,
                    )
                    for c in r.comments:
                        print(
                            f'        💬 Comment: "{c[:60]}"',
                            file=sys.stderr,
                        )
            else:
                print(f"   ↳ No reviewed PRs on {target_date}", file=sys.stderr)

        # Fetch PR comments for own and foreign PRs
        for pr in (*own_prs_map.values(), *foreign_prs_map.values()):
            if pr.number:
                comments = self.github_client.get_pr_user_comments(
                    owner, repo, pr.number, author, target_date, local_path=local_path
                )
                if isinstance(comments, list) and comments:
                    pr.comments = comments
                    if self.verbose:
                        for c in comments:
                            print(
                                f'      💬 PR#{pr.number} comment: "{c[:60]}"',
                                file=sys.stderr,
                            )

        # 4. Summarize PRs
        total_prs = len(own_prs_map) + len(foreign_prs_map)
        if self.verbose and total_prs > 0:
            engine_name = (
                f"Gemini Free API ({self.ai_enhancer.model})"
                if (self.use_ai and self.ai_enhancer.is_available)
                else "Deterministic Engine"
            )
            print(
                f"   ↳ Generating summaries for {total_prs} PR(s) with {engine_name}...",
                file=sys.stderr,
            )

        # Synthesize bullets for own PRs
        for pr in own_prs_map.values():
            pr.bullets = self._synthesize_pr_bullets(pr, is_foreign=False)
            activity.own_prs.append(pr)

        # Synthesize bullets for foreign PRs
        for pr in foreign_prs_map.values():
            pr.bullets = self._synthesize_pr_bullets(pr, is_foreign=True)
            activity.foreign_contributions.append(pr)

        # 5. Assemble branch activities
        for b_name, b_commits in branch_commits_map.items():
            activity.branch_commits.append(
                BranchActivity(
                    branch_name=b_name,
                    commits=b_commits,
                    project_name=project.name,
                    category=project.category,
                )
            )

        return activity

    def _synthesize_pr_bullets(
        self,
        pr: PullRequestInfo,
        is_foreign: bool = False,
    ) -> list[str]:
        """Synthesize bullets either with AI or deterministic fallback."""
        # Never fall back to every commit in the PR. Mixed-author PRs are common,
        # and doing so would present teammates' implementation work as the
        # configured contributor's own work.
        author_commits = pr.author_commits

        # Try AI synthesis if available
        if author_commits and self.use_ai and self.ai_enhancer.is_available:
            ai_bullets = self.ai_enhancer.summarize_pr(
                pr, author_commits, is_foreign=is_foreign, comments=pr.comments
            )
            if ai_bullets:
                return ai_bullets

        # Deterministic generation
        bullets: list[str] = []

        if is_foreign:
            bullets.append(f"PR#{pr.number} -> Contributed authored commit(s) to this PR.")
            for c in author_commits:
                msg = clean_commit_message(c.headline)
                if msg:
                    bullets.append(msg)
                if c.body:
                    for body_bullet in clean_markdown_bullets(c.body):
                        bullets.append(body_bullet)
            if pr.comments:
                for comment in pr.comments:
                    cleaned = comment.strip()
                    if cleaned and cleaned not in bullets:
                        bullets.append(cleaned)
        else:
            # Describe implementation only from commits attributed to the
            # configured contributor. A PR body can summarize teammates' work.
            if author_commits:
                summary_text = clean_commit_message(author_commits[0].headline)
                bullets.append(f"PR#{pr.number} -> {summary_text}")
                for c in author_commits[1:4]:
                    msg = clean_commit_message(c.headline)
                    if msg:
                        bullets.append(msg)
            else:
                bullets.append(
                    f"PR#{pr.number} -> Opened this PR; no authored commit details were found."
                )

            if pr.comments:
                for comment in pr.comments:
                    cleaned = comment.strip()
                    if cleaned and cleaned not in bullets:
                        bullets.append(cleaned)

        return bullets

    def _synthesize_review_bullets(self, review: ReviewInfo) -> list[str]:
        """Synthesize bullets for a reviewed PR evaluating severe issues or test notes."""
        if not review.comments:
            return []

        # Try AI synthesis if available
        if self.use_ai and self.ai_enhancer.is_available:
            ai_bullets = self.ai_enhancer.summarize_review(review, review.comments)
            if ai_bullets:
                return ai_bullets

        # Deterministic fallback: clean and format comments
        bullets: list[str] = []
        for c in review.comments:
            cleaned = c.strip()
            if cleaned and cleaned not in bullets:
                bullets.append(cleaned)
        return bullets
