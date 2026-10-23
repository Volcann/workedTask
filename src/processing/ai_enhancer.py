from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from models.models import CommitInfo, PullRequestInfo, ReviewInfo
from shared.utils import format_arrow_lines

warnings.filterwarnings("ignore", category=UserWarning)
logging.getLogger("google.genai").setLevel(logging.ERROR)

load_dotenv()
load_dotenv("/home/folium/Documents/volcanai/.env")

logger = logging.getLogger(__name__)

# Free-tier models in descending quota resilience order (verified only)
DEFAULT_FREE_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

DEFAULT_MIN_REQUEST_INTERVAL = 5.0  # Free tier: 15 RPM → ~1 request per 4-5s
DEFAULT_RETRY_DELAY = 6.0  # Wait before trying next fallback on 429
MAX_MODELS_PER_ITEM = 3  # Cap quota burn at 3 models per item

CACHE_FILE = Path(".cache/gemini_summary_cache.json")


class AIEnhancer:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        models_fallback: list[str] | None = None,
        cache_enabled: bool = True,
        min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        raw_model = model or DEFAULT_FREE_MODELS[0]
        self.model = raw_model.strip("'\"")
        self.models_fallback = [m.strip("'\"") for m in (models_fallback or DEFAULT_FREE_MODELS)]
        self.cache_enabled = cache_enabled
        self.min_request_interval = min_request_interval
        self.retry_delay = retry_delay
        self._last_request_time: float = 0.0
        self._client = None
        self._cache: dict[str, list[str]] = self._load_cache()

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None and self.is_available:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.debug("Failed to initialize Google GenAI Client: %s", e)
                self._client = None
        return self._client

    def _wait_for_rate_limit(self) -> None:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return
        if self._last_request_time <= 0:
            self._last_request_time = time.time()
            return
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_request_interval:
            wait_sec = self.min_request_interval - elapsed
            print(
                f"      ⏳ Pacing request: waiting {wait_sec:.1f}s to respect 15 RPM free limit...",
                file=sys.stderr,
            )
            time.sleep(wait_sec)
        self._last_request_time = time.time()

    def _load_cache(self) -> dict[str, list[str]]:
        if not self.cache_enabled or not CACHE_FILE.exists():
            return {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_cache(self) -> None:
        if not self.cache_enabled:
            return
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except OSError as e:
            logger.debug("Could not save Gemini cache: %s", e)

    def _compute_cache_key(
        self,
        pr: PullRequestInfo,
        commits: Sequence[CommitInfo],
        is_foreign: bool,
        comments: Sequence[str] | None = None,
    ) -> str:
        shas = "_".join(c.short_sha for c in commits)
        comments_str = "_".join(sorted(comments or []))
        comments_suffix = f":{comments_str}" if comments_str else ""
        # Version prefix prevents reuse of summaries generated before attribution safeguards
        raw = f"attribution-v2:{pr.project_name}:{pr.repo_name}#{pr.number}:{pr.title}:{is_foreign}:{shas}{comments_suffix}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def summarize_pr(
        self,
        pr: PullRequestInfo,
        author_commits: Sequence[CommitInfo],
        is_foreign: bool = False,
        comments: Sequence[str] | None = None,
    ) -> list[str]:
        client = self._get_client()
        if not client:
            return []

        cache_key = self._compute_cache_key(pr, author_commits, is_foreign, comments=comments)
        if cache_key in self._cache:
            print(f"      ⚡ PR#{pr.number}: Loaded human summary from cache", file=sys.stderr)
            return self._cache[cache_key]

        commits_text = "\n".join(
            f"- {c.short_sha}: {c.headline}\n  {c.body}" for c in author_commits
        )

        role_instruction = (
            "You are a pragmatic senior software engineer writing your daily end-of-day standup status update for your engineering team.\n"
            "It MUST sound 100% human-written, authentic, grounded, and concise — NOT robotic, marketing-heavy, or AI-generated.\n\n"
            "STRICT HUMAN-WRITING RULES:\n"
            "1. Absolutely NO AI buzzwords or filler (NO 'delve', 'spearheaded', 'seamlessly', 'pivotal', 'testament', 'cutting-edge', 'holistic', 'robust framework').\n"
            "2. Use active, direct past/present engineering verbs ('Added', 'Restricted', 'Refactored', 'Fixed', 'Enforces', 'Restructures', 'Tested').\n"
            "3. Reference real technical symbols, functions, class names, files, commit hashes (e.g. fd3cfbc), or database constraints directly present in the commits. DO NOT invent endpoints or API paths unless they explicitly exist in the listed commits or files.\n"
            "4. If no API views, URLs, or serializers were modified in the author's commits, DO NOT claim that endpoints were added, tested, or modified.\n"
            "5. Attribute implementation only when it is directly supported by the listed author commits. The PR title is context, not proof that the contributor implemented every change in the PR.\n"
            "6. Every single line MUST start with '-> '.\n"
            "7. If this is a foreign PR (work contributed to someone else's PR):\n"
            f"   - Line 1 MUST be: '-> PR#{pr.number} -> Contributed authored commit(s) to this PR.'\n"
            "   - Following lines: Specific concrete tasks supported by commits attributed to the report subject (e.g. '-> Machine Logs API: Added missing employee profile pictures...', '-> 30 tests and Ruff passed (Committed: fd3cfbc)').\n"
            "8. If this is your own PR:\n"
            f"   - Line 1: '-> PR#{pr.number} -> <One crisp sentence explaining what changed and why>'\n"
            "   - Optional Line 2: Concrete test verification or implementation detail (e.g. '-> Tested the command.', '-> Tested the platform. Deleted users are accessing endpoints fixed inside #385.').\n"
            "9. Output 1 to 4 bullets max. Do not include markdown codeblocks, greeting, or extra commentary."
        )

        files_section = ""
        all_files: set[str] = set()
        for c in author_commits:
            for f in c.files:
                if isinstance(f, str) and f.strip():
                    all_files.add(f.strip())
                elif isinstance(f, dict):
                    fname = f.get("filename") or f.get("path") or f.get("name")
                    if isinstance(fname, str) and fname.strip():
                        all_files.add(fname.strip())

        for f in pr.files_changed:
            if isinstance(f, str) and f.strip():
                all_files.add(f.strip())
            elif isinstance(f, dict):
                fname = f.get("filename") or f.get("path") or f.get("name")
                if isinstance(fname, str) and fname.strip():
                    all_files.add(fname.strip())
        if all_files:
            file_sample = sorted(all_files)[:20]
            files_section = (
                "\nFiles modified in author commits:\n"
                + "\n".join(f"- {f}" for f in file_sample)
                + "\n"
            )

        comments_section = ""
        if comments:
            comments_text = "\n".join(f"- {c}" for c in comments)
            comments_section = (
                f"\nAuthor Comments / Testing Verification Notes on PR:\n{comments_text}\n"
                "IMPORTANT: Reflect the author's testing / verification comments in the bullets "
                "(e.g., '-> Fully tested from frontend side with no breaking changes.').\n"
            )

        prompt = (
            f"{role_instruction}\n\n"
            f"Target PR: #{pr.number}\n"
            f"PR Title: {pr.title}\n"
            f"{files_section}"
            f"Verified commits authored by the report subject:\n{commits_text}\n"
            f"{comments_section}"
        )

        models_to_try = [self.model]
        for m in self.models_fallback:
            if m not in models_to_try:
                models_to_try.append(m)
        models_to_try = models_to_try[:MAX_MODELS_PER_ITEM]

        for model_name in models_to_try:
            try:
                self._wait_for_rate_limit()
                print(
                    f"      ✨ PR#{pr.number}: Generating standup summary with {model_name}...",
                    file=sys.stderr,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    raw_lines = [
                        line.strip()
                        for line in response.text.strip().splitlines()
                        if line.strip() and not line.strip().startswith("```")
                    ]
                    cleaned_bullets = format_arrow_lines(raw_lines)
                    # Strip leading arrow so the formatter controls prefixing consistently
                    processed_bullets = [re.sub(r"^->\s*", "", b).strip() for b in cleaned_bullets]

                    if is_foreign:
                        canonical_header = (
                            f"PR#{pr.number} -> Contributed authored commit(s) to this PR."
                        )
                        if not processed_bullets or f"PR#{pr.number}" not in processed_bullets[0]:
                            processed_bullets.insert(0, canonical_header)
                        else:
                            processed_bullets[0] = canonical_header

                    self._cache[cache_key] = processed_bullets
                    self._save_cache()
                    self._last_request_time = time.time()
                    return processed_bullets
            except Exception as e:
                err_msg = str(e)
                logger.debug("Model %s failed: %s", model_name, err_msg)

                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    print(
                        f"      ⏳ Rate limit (429) on {model_name}. Pausing {self.retry_delay:.0f}s before trying next fallback...",
                        file=sys.stderr,
                    )
                    if not os.getenv("PYTEST_CURRENT_TEST"):
                        time.sleep(self.retry_delay)
                    self._last_request_time = time.time()
                    continue
                if "404" in err_msg or "NOT_FOUND" in err_msg:
                    continue

        return []

    def _compute_review_cache_key(
        self,
        review: ReviewInfo,
        comments: Sequence[str],
    ) -> str:
        comments_str = "_".join(sorted(comments))
        raw = f"review:{review.project_name}:{review.category}#{review.pr_number}:{review.pr_title}:{comments_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def summarize_review(
        self,
        review: ReviewInfo,
        comments: Sequence[str],
    ) -> list[str]:
        if not comments:
            return []

        client = self._get_client()
        if not client:
            return []

        cache_key = self._compute_review_cache_key(review, comments)
        if cache_key in self._cache:
            print(
                f"      ⚡ Review PR#{review.pr_number}: Loaded review summary from cache",
                file=sys.stderr,
            )
            return self._cache[cache_key]

        comments_text = "\n".join(f"- {c}" for c in comments)

        role_instruction = (
            "You are a pragmatic senior software engineer writing your daily end-of-day standup status update for your engineering team.\n"
            "Summarize the code review and evaluation you performed on this pull request.\n"
            "It MUST sound 100% human-written, authentic, grounded, and concise — NOT robotic, marketing-heavy, or AI-generated.\n\n"
            "STRICT HUMAN-WRITING RULES:\n"
            "1. Absolutely NO AI buzzwords or filler (NO 'delve', 'spearheaded', 'seamlessly', 'pivotal', 'testament', 'cutting-edge', 'holistic', 'robust framework').\n"
            "2. Focus strictly on:\n"
            "   - Severe issues, critical bugs, edge cases, breaking changes, or architectural flaws you caught/highlighted during the PR review.\n"
            "   - Concrete testing confirmations (e.g. 'I have fully tested from FE no breaking changes.', 'Verified zero regressions on staging.').\n"
            "3. If you highlighted a severe issue or edge case, state the issue directly (e.g. '-> Edge Case Identified: ...', '-> Flagged breaking change in approval calculations...').\n"
            "4. Do NOT output generic filler like 'LGTM' or 'Code reviewed'. If no severe issues or testing notes were found, output nothing.\n"
            "5. Every line MUST start with '-> '.\n"
            "6. Output 1 to 3 bullets max. Do not include markdown codeblocks, greeting, or extra commentary."
        )

        prompt = (
            f"{role_instruction}\n\n"
            f"Reviewed PR: #{review.pr_number} - {review.pr_title}\n"
            f"Reviewer: {review.reviewer}\n"
            f"Reviewer Comments & Feedback on PR:\n{comments_text}\n"
        )

        models_to_try = [self.model]
        for m in self.models_fallback:
            if m not in models_to_try:
                models_to_try.append(m)
        models_to_try = models_to_try[:MAX_MODELS_PER_ITEM]

        for model_name in models_to_try:
            try:
                self._wait_for_rate_limit()
                print(
                    f"      ✨ Review PR#{review.pr_number}: Evaluating review findings with {model_name}...",
                    file=sys.stderr,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    raw_lines = [
                        line.strip()
                        for line in response.text.strip().splitlines()
                        if line.strip() and not line.strip().startswith("```")
                    ]
                    cleaned_bullets = format_arrow_lines(raw_lines)
                    processed_bullets = [re.sub(r"^->\s*", "", b).strip() for b in cleaned_bullets]
                    self._cache[cache_key] = processed_bullets
                    self._save_cache()
                    self._last_request_time = time.time()
                    return processed_bullets
            except Exception as e:
                err_msg = str(e)
                logger.debug("Model %s failed on review: %s", model_name, err_msg)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    print(
                        f"      ⏳ Rate limit (429) on {model_name}. Pausing {self.retry_delay:.0f}s before trying next fallback...",
                        file=sys.stderr,
                    )
                    if not os.getenv("PYTEST_CURRENT_TEST"):
                        time.sleep(self.retry_delay)
                    self._last_request_time = time.time()
                    continue
                if "404" in err_msg or "NOT_FOUND" in err_msg:
                    continue

        return []
