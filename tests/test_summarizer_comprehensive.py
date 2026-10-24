from __future__ import annotations

import builtins
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from ai.summarizer import GeminiSummarizer
from report.data_classes import ReportChunk, ReportEntry


@pytest.fixture
def dummy_pr_chunk() -> ReportChunk:
    entry = ReportEntry(
        id="c1",
        kind="commit",
        text="feat: dummy commit",
        created_at="2026-10-24T12:00:00+05:00",
        extra_time=False,
        note=None,
    )
    return ReportChunk(
        repository="org/repo",
        kind="pr",
        key="10",
        title="Dummy PR",
        description="",
        url="https://github.com/org/repo/pull/10",
        categories=("prs",),
        entries=(entry,),
        extra_time=False,
        note=None,
    )


def test_summarizer_init_model_from_env(dummy_pr_chunk):
    client = SimpleNamespace(models=SimpleNamespace())
    with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-env-model"}):
        summarizer = GeminiSummarizer("", client=client)
        assert summarizer.model == "gemini-env-model"
        assert summarizer._owns_client is False


def test_summarizer_init_model_from_active_fallback(dummy_pr_chunk):
    client = SimpleNamespace(models=SimpleNamespace())
    with (
        patch.dict(os.environ, {"GEMINI_MODEL": ""}),
        patch("ai.summarizer.get_active_models", return_value=["fallback-model"]),
    ):
        summarizer = GeminiSummarizer("", client=client)
        assert summarizer.model == "fallback-model"


def test_summarizer_init_model_empty_and_no_active_raises():
    client = SimpleNamespace(models=SimpleNamespace())
    with (
        patch.dict(os.environ, {"GEMINI_MODEL": ""}),
        patch("ai.summarizer.get_active_models", return_value=[]),
    ):
        with pytest.raises(ValueError, match="Supply --model or GEMINI_MODEL"):
            GeminiSummarizer("", client=client)


def test_summarizer_init_missing_api_keys_raises():
    with patch.dict(os.environ, {}, clear=True):
        with patch("utils.models.ensure_env_loaded"):
            with pytest.raises(ValueError, match="Set GEMINI_API_KEY or GOOGLE_API_KEY"):
                GeminiSummarizer("gemini-2.5-flash", client=None)


def test_summarizer_init_missing_genai_package_raises():
    orig_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if "google" in name:
            raise ImportError("No module named google.genai")
        return orig_import(name, *args, **kwargs)

    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy_key"}):
        with patch("builtins.__import__", side_effect=failing_import):
            with pytest.raises(ValueError, match="Install the AI extra"):
                GeminiSummarizer("gemini-2.5-flash", client=None)


def test_summarizer_init_owns_client_when_created(dummy_pr_chunk):
    fake_client = SimpleNamespace(close=MagicMock())
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy_key"}):
        with patch("google.genai.Client", return_value=fake_client):
            summarizer = GeminiSummarizer("gemini-2.5-flash", client=None)
            assert summarizer._owns_client is True
            assert summarizer.client is fake_client

            summarizer.close()
            fake_client.close.assert_called_once()


def test_summarizer_close_does_not_close_unowned_client():
    fake_client = SimpleNamespace(close=MagicMock())
    summarizer = GeminiSummarizer("gemini-2.5-flash", client=fake_client)
    assert summarizer._owns_client is False
    summarizer.close()
    fake_client.close.assert_not_called()


def test_summarizer_non_retryable_error_stops_retry_loop(dummy_pr_chunk):
    call_counts = []

    def failing_generate(model, contents):
        call_counts.append(model)
        raise ValueError("Invalid argument prompt value")

    client = SimpleNamespace(models=SimpleNamespace(generate_content=MagicMock(side_effect=failing_generate)))
    with patch("ai.summarizer.get_active_models", return_value=["model-1", "model-2", "model-3"]):
        summarizer = GeminiSummarizer("model-1", client=client)
        with pytest.raises(ValueError, match="Invalid argument"):
            summarizer.summarize(dummy_pr_chunk)

    # Must NOT retry model-2 or model-3
    assert len(call_counts) == 1
    assert call_counts[0] == "model-1"


def test_summarizer_retries_through_multiple_transient_errors(dummy_pr_chunk):
    models_tried = []

    def multi_fail_generate(model, contents):
        models_tried.append(model)
        if model == "model-1":
            raise RuntimeError("429 Quota Exceeded")
        if model == "model-2":
            raise RuntimeError("504 Deadline Exceeded")
        if model == "model-3":
            raise RuntimeError("404 Model Not Found")
        if model == "model-4":
            raise RuntimeError("503 Service Unavailable")
        return SimpleNamespace(text="Finally succeeded on model-5")

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=MagicMock(side_effect=multi_fail_generate))
    )
    with patch(
        "ai.summarizer.get_active_models",
        return_value=["model-1", "model-2", "model-3", "model-4", "model-5"],
    ):
        summarizer = GeminiSummarizer("model-1", client=client)
        res = summarizer.summarize(dummy_pr_chunk)

    assert res == "Finally succeeded on model-5"
    assert summarizer.model == "model-5"
    assert models_tried == ["model-1", "model-2", "model-3", "model-4", "model-5"]


def test_summarizer_empty_and_none_text_responses_retried(dummy_pr_chunk):
    attempts = []

    def varying_responses(model, contents):
        attempts.append(model)
        if model == "model-1":
            return None
        if model == "model-2":
            return SimpleNamespace(text=None)
        if model == "model-3":
            return SimpleNamespace(text="    ")
        return SimpleNamespace(text="Valid final summary")

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=MagicMock(side_effect=varying_responses))
    )
    with patch(
        "ai.summarizer.get_active_models",
        return_value=["model-1", "model-2", "model-3", "model-4"],
    ):
        summarizer = GeminiSummarizer("model-1", client=client)
        res = summarizer.summarize(dummy_pr_chunk)

    assert res == "Valid final summary"
    assert attempts == ["model-1", "model-2", "model-3", "model-4"]


def test_summarizer_all_candidates_fail_raises_last_error(dummy_pr_chunk):
    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=MagicMock(side_effect=RuntimeError("503 Server Unavailable")))
    )
    with patch("ai.summarizer.get_active_models", return_value=["m1", "m2"]):
        summarizer = GeminiSummarizer("m1", client=client)
        with pytest.raises(RuntimeError, match="503 Server Unavailable"):
            summarizer.summarize(dummy_pr_chunk)
