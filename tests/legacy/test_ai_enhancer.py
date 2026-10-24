from __future__ import annotations

from unittest.mock import MagicMock, patch

from models.models import CommitInfo, PullRequestInfo, ReviewInfo
from processing.ai_enhancer import DEFAULT_FREE_MODELS, AIEnhancer


def test_ai_enhancer_initialization() -> None:
    enhancer = AIEnhancer(api_key="fake-key", model="gemini-2.5-flash-lite")
    assert enhancer.is_available is True
    assert enhancer.model == "gemini-2.5-flash-lite"
    assert DEFAULT_FREE_MODELS[0] in enhancer.models_fallback


def test_ai_enhancer_cache_mechanism(tmp_path) -> None:
    cache_file = tmp_path / "test_cache.json"
    with patch("processing.ai_enhancer.CACHE_FILE", cache_file):
        enhancer = AIEnhancer(api_key="fake-key", cache_enabled=True)

        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.text = (
            "-> PR#348 -> Added search and natural sorting to device-user listings.\n"
            "-> Tested the command."
        )
        fake_client.models.generate_content.return_value = fake_response

        with patch.object(enhancer, "_get_client", return_value=fake_client):
            pr = PullRequestInfo(number=348, title="HMT-258 | Add search", body="Test body")
            commits = [CommitInfo(sha="1234567", message="feat: add search")]

            # First call: hits client
            bullets1 = enhancer.summarize_pr(pr, commits)
            assert len(bullets1) == 2
            assert fake_client.models.generate_content.call_count == 1
            prompt = fake_client.models.generate_content.call_args.kwargs["contents"]
            assert "Verified commits authored by the report subject" in prompt
            assert "feat: add search" in prompt
            assert "Test body" not in prompt

            # Second call with same data: should hit cache without calling client again
            bullets2 = enhancer.summarize_pr(pr, commits)
            assert bullets2 == bullets1
            assert fake_client.models.generate_content.call_count == 1


def test_ai_enhancer_model_failover_on_rate_limit(tmp_path) -> None:
    cache_file = tmp_path / "test_cache.json"
    with patch("processing.ai_enhancer.CACHE_FILE", cache_file):
        enhancer = AIEnhancer(
            api_key="fake-key",
            model="gemini-2.5-flash",
            models_fallback=["gemini-2.5-flash", "gemini-2.5-flash-lite"],
            cache_enabled=False,
        )

        fake_client = MagicMock()

        def side_effect(model, contents):
            if model == "gemini-2.5-flash":
                raise Exception("429 RESOURCE_EXHAUSTED Quota exceeded. Please retry in 20s.")
            resp = MagicMock()
            resp.text = "-> PR#348 -> Success with fallback model."
            return resp

        fake_client.models.generate_content.side_effect = side_effect

        with patch.object(enhancer, "_get_client", return_value=fake_client):
            pr = PullRequestInfo(number=348, title="Test PR")
            commits = [CommitInfo(sha="1234567", message="test commit")]

            bullets = enhancer.summarize_pr(pr, commits)
            assert len(bullets) == 1
            assert "Success with fallback model" in bullets[0]
            # Confirmed it called both the primary and fallback model
            assert fake_client.models.generate_content.call_count == 2


def test_ai_enhancer_summarize_review(tmp_path) -> None:
    cache_file = tmp_path / "test_cache.json"
    with patch("processing.ai_enhancer.CACHE_FILE", cache_file):
        enhancer = AIEnhancer(api_key="fake-key", cache_enabled=True)

        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.text = (
            "-> I have fully tested from FE no breaking changes.\n"
            "-> Highlighted edge case in approval threshold where negative values bypass validation."
        )
        fake_client.models.generate_content.return_value = fake_response

        with patch.object(enhancer, "_get_client", return_value=fake_client):
            review = ReviewInfo(
                pr_number=387,
                pr_title="HTM-219 | Simplify approval amount modification",
                reviewer="Volcann",
                state="APPROVED",
            )
            comments = [
                "I have fully tested from FE no breaking changes.",
                "Edge Case: negative values bypass validation in calculate_amount.",
            ]

            bullets = enhancer.summarize_review(review, comments)
            assert len(bullets) == 2
            assert "fully tested from FE" in bullets[0]
            assert "Highlighted edge case in approval threshold" in bullets[1]

            # Verify caching
            bullets_cached = enhancer.summarize_review(review, comments)
            assert bullets_cached == bullets
            assert fake_client.models.generate_content.call_count == 1
