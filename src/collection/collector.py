from __future__ import annotations

import logging
import sys
from datetime import date
from typing import Sequence

from ghtoolkit import GitHubClient
from ghtoolkit.github_client import is_author_match
from ghtoolkit.models import CommitInfo, ProjectConfig, PullRequestInfo, ReviewInfo

from models.models import BranchActivity, DailyReport, ProjectActivity
from processing.ai_enhancer import AIEnhancer
from shared.utils import (
    clean_commit_message,
    clean_markdown_bullets,
    format_status_date,
)

logger = logging.getLogger(__name__)


class ActivityCollector:
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

        # Fetch own PRs created/merged on that day
        prs = self.github_client.get_user_prs_for_date(
            owner, repo, author, target_date, local_path=local_path
        )
        own_prs_map: dict[int, PullRequestInfo] = {}
        for pr in prs:
            pr.project_name = project.name
            pr.category = project.category

            # Search results omit commit details — hydrate before attributing work
            if not pr.commits:
                full_pr = self.github_client.get_pr_details(
                    owner, repo, pr.number, local_path=local_path, author=author
                )
                if isinstance(full_pr, PullRequestInfo):
                    pr.body = full_pr.body or pr.body
                    pr.commits = full_pr.commits
                    pr.head_ref = full_pr.head_ref or pr.head_ref
                    if not pr.files_changed and full_pr.files_changed:
                        pr.files_changed = full_pr.files_changed

            own_prs_map[pr.number] = pr

        # Fetch commits on that day
        commits = self.github_client.get_user_commits_for_date(
            owner, repo, author, target_date, local_path=local_path
        )
        daily_shas = {commit.sha for commit in commits if commit.sha}

        # A PR merged today can contain commits authored on earlier days. Only
        # the date-filtered commit query can establish authored work for this
        # report; the PR's full commit list is used solely to associate SHAs.
        for pr in own_prs_map.values():
            pr.author_commits = [
                commit
                for commit in pr.commits
                if commit.sha in daily_shas
                and is_author_match(
                    author,
                    name=commit.author_name,
                    login=commit.author_login,
                )
            ]

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
            matched_pr_num = None
            for pr_num, pr in own_prs_map.items():
                if any(c.sha == commit.sha for c in pr.commits):
                    if not any(c.sha == commit.sha for c in pr.author_commits):
                        pr.author_commits = [*pr.author_commits, commit]
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
                        pr.author_commits = [*pr.author_commits, commit]
                    matched_pr_num = pr_num
                    break

            if matched_pr_num is not None:
                if self.verbose:
                    print(
                        f'      • {commit.short_sha}: "{commit.headline[:48]}" ➔ PR#{matched_pr_num} (foreign)',
                        file=sys.stderr,
                    )
                continue

            pulls = self.github_client.get_commit_pull_requests(
                owner, repo, commit.sha, local_path=local_path
            )
            if pulls:
                pr_item = pulls[0]
                pr_num = pr_item.get("number")
                if pr_num:
                    if pr_num in own_prs_map:
                        if not any(c.sha == commit.sha for c in own_prs_map[pr_num].author_commits):
                            own_prs_map[pr_num].author_commits = [
                                *own_prs_map[pr_num].author_commits,
                                commit,
                            ]
                    elif pr_num in foreign_prs_map:
                        if not any(
                            c.sha == commit.sha for c in foreign_prs_map[pr_num].author_commits
                        ):
                            foreign_prs_map[pr_num].author_commits = [
                                *foreign_prs_map[pr_num].author_commits,
                                commit,
                            ]
                    else:
                        full_pr = self.github_client.get_pr_details(
                            owner, repo, pr_num, local_path=local_path, author=author
                        )
                        if full_pr:
                            full_pr.project_name = project.name
                            full_pr.category = project.category
                            full_pr.author_commits = [*full_pr.author_commits, commit]
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
                # Standalone branch commit — not part of any PR
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

        # Fetch reviewed PRs and their user comments
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
                r.comments = (
                    [comment for comment in comments if isinstance(comment, str)]
                    if isinstance(comments, list)
                    else []
                )
                if r.comments:
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

        for pr in (*own_prs_map.values(), *foreign_prs_map.values()):
            if pr.number:
                comments = self.github_client.get_pr_user_comments(
                    owner, repo, pr.number, author, target_date, local_path=local_path
                )
                pr.comments = (
                    [comment for comment in comments if isinstance(comment, str)]
                    if isinstance(comments, list)
                    else []
                )
                if self.verbose:
                    for c in pr.comments:
                        print(
                            f'      💬 PR#{pr.number} comment: "{c[:60]}"',
                            file=sys.stderr,
                        )

        # Merge-day discovery may return an older PR with no work authored on
        # the requested day. Its merge remains visible under reviewed PRs.
        own_prs_map = {
            number: pr
            for number, pr in own_prs_map.items()
            if pr.state.upper() != "MERGED" or pr.author_commits
        }

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

        for pr in own_prs_map.values():
            pr.bullets = self._synthesize_pr_bullets(pr, is_foreign=False)
            activity.own_prs.append(pr)

        for pr in foreign_prs_map.values():
            pr.bullets = self._synthesize_pr_bullets(pr, is_foreign=True)
            activity.foreign_contributions.append(pr)

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
        # Only use commits attributed to the configured author — never fall back to
        # all PR commits, as mixed-author PRs would misattribute teammates' work.
        author_commits = pr.author_commits

        if author_commits and self.use_ai and self.ai_enhancer.is_available:
            ai_bullets = self.ai_enhancer.summarize_pr(
                pr, author_commits, is_foreign=is_foreign, comments=pr.comments
            )
            if ai_bullets:
                return ai_bullets

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
            # Describe only work from commits by the configured contributor;
            # the PR body can summarize teammates' work and must not be used.
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
        if not review.comments:
            return []

        if self.use_ai and self.ai_enhancer.is_available:
            ai_bullets = self.ai_enhancer.summarize_review(review, review.comments)
            if ai_bullets:
                return ai_bullets

        bullets: list[str] = []
        for c in review.comments:
            cleaned = c.strip()
            if cleaned and cleaned not in bullets:
                bullets.append(cleaned)
        return bullets
