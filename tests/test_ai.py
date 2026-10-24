from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from ai import (
    ACTIVE_FREE_MODELS,
    GeminiSummarizer,
    build_prompt,
    get_active_models,
    probe_gemini_models,
)
from report.data_classes import ReportChunk, ReportEntry


@pytest.fixture
def sample_pr_chunk() -> ReportChunk:
    entry = ReportEntry(
        id="c1",
        kind="commit",
        text="feat: add active model detection",
        created_at="2026-10-24T14:00:00+05:00",
        extra_time=False,
        note=None,
    )
    return ReportChunk(
        repository="owner/repo",
        kind="pr",
        key="101",
        title="Add active model detection",
        description="",
        url="https://github.com/owner/repo/pull/101",
        categories=("prs",),
        entries=(entry,),
        extra_time=False,
        note=None,
    )


def test_active_free_models_list():
    assert "gemini-3.5-flash-lite" in ACTIVE_FREE_MODELS
    assert "gemini-2.5-flash-lite" in ACTIVE_FREE_MODELS
    assert "gemini-2.5-flash" in ACTIVE_FREE_MODELS
    assert len(ACTIVE_FREE_MODELS) >= 5


def test_ai_package_exports_and_identity():
    import ai
    import ai.summarizer
    import constants
    import utils
    import utils.models
    import utils.prompt

    assert ai.ACTIVE_FREE_MODELS is constants.ACTIVE_FREE_MODELS
    assert ai.DEFAULT_MODEL is constants.DEFAULT_MODEL
    assert ai.GeminiSummarizer is ai.summarizer.GeminiSummarizer
    assert ai.Summarizer is ai.summarizer.Summarizer
    assert ai.build_prompt is utils.build_prompt is utils.prompt.build_prompt
    assert ai.get_active_models is utils.get_active_models is utils.models.get_active_models
    assert ai.probe_gemini_models is utils.probe_gemini_models is utils.models.probe_gemini_models


def test_get_active_models_fallback():
    models = get_active_models(None)
    assert models == list(ACTIVE_FREE_MODELS)


def test_get_active_models_with_client_list():
    fake_model1 = SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=["generateContent"])
    fake_model2 = SimpleNamespace(name="models/gemini-3.5-flash-lite", supported_actions=["generateContent"])
    fake_model3 = SimpleNamespace(name="models/text-embedding-004", supported_actions=["embedContent"])
    fake_client = SimpleNamespace(
        models=SimpleNamespace(list=Mock(return_value=[fake_model1, fake_model2, fake_model3]))
    )
    models = get_active_models(fake_client)
    # gemini-3.5-flash-lite is prioritized before gemini-2.5-flash per ACTIVE_FREE_MODELS
    assert models[0] == "gemini-3.5-flash-lite"
    assert models[1] == "gemini-2.5-flash"
    assert "text-embedding-004" not in models


def test_build_prompt_format(sample_pr_chunk):
    prompt = build_prompt(sample_pr_chunk)
    assert "Summarize this single pull request's daily work" in prompt
    assert "BEGIN_PR_DATA_JSON" in prompt
    assert "END_PR_DATA_JSON" in prompt
    assert "untrusted data" in prompt
    assert "Add active model detection" in prompt


def test_build_prompt_rejects_non_pr(sample_pr_chunk):
    issue_chunk = ReportChunk(
        repository="owner/repo",
        kind="issue",
        key="12",
        title="Bug issue",
        description="",
        url="https://github.com/owner/repo/issues/12",
        categories=("issues",),
        entries=(),
        extra_time=False,
        note=None,
    )
    with pytest.raises(ValueError, match="PR-wise"):
        build_prompt(issue_chunk)


def test_gemini_summarizer_with_fallback(sample_pr_chunk):
    call_records = []

    def fake_generate(model, contents):
        call_records.append(model)
        if model == "gemini-3.5-flash-lite":
            raise RuntimeError("503 UNAVAILABLE: Model experiencing high demand")
        return SimpleNamespace(text="Summary from fallback model")

    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=fake_generate)))
    ai = GeminiSummarizer("gemini-3.5-flash-lite", client=fake_client)
    result = ai.summarize(sample_pr_chunk)
    assert result == "Summary from fallback model"
    assert call_records[0] == "gemini-3.5-flash-lite"
    assert call_records[1] == "gemini-2.5-flash-lite"


def test_gemini_summarizer_empty_summary_raises(sample_pr_chunk):
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=Mock(return_value=SimpleNamespace(text="  ")))
    )
    ai = GeminiSummarizer("gemini-3.5-flash-lite", client=fake_client)
    with pytest.raises(RuntimeError, match="no summary"):
        ai.summarize(sample_pr_chunk)


def test_probe_gemini_models_with_mock():
    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            list=Mock(return_value=[]),
            generate_content=Mock(return_value=SimpleNamespace(text="gemini is active")),
        )
    )
    results = probe_gemini_models(fake_client, prompt="test prompt")
    assert len(results) > 0
    assert results[0]["status"] == "WORKING"
    assert "active" in results[0]["note"]


@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_GEMINI_TESTS"),
    reason="Live Gemini API test requires RUN_LIVE_GEMINI_TESTS=1",
)
def test_live_gemini_free_api(sample_pr_chunk):

    ai = GeminiSummarizer("gemini-3.5-flash-lite")
    summary = ai.summarize(sample_pr_chunk)
    assert summary
    assert isinstance(summary, str)
    assert len(summary) > 5
