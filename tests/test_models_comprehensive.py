from __future__ import annotations

import builtins
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from constants import ACTIVE_FREE_MODELS
from utils.models import (
    ensure_env_loaded,
    get_active_models,
    get_verified_active_models,
    probe_gemini_models,
    test_gemini_models,
)


def test_ensure_env_loaded_noop_when_key_present():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy_key"}, clear=True):
        with patch("pathlib.Path.is_file") as mock_is_file:
            ensure_env_loaded()
            mock_is_file.assert_not_called()


def test_ensure_env_loaded_noop_when_google_key_present():
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "dummy_key"}, clear=True):
        with patch("pathlib.Path.is_file") as mock_is_file:
            ensure_env_loaded()
            mock_is_file.assert_not_called()


def test_ensure_env_loaded_searches_candidates_and_loads(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=loaded_from_test_env\n", encoding="utf-8")

    def fake_is_file(path_self):
        return str(path_self) == str(env_file)

    def fake_load_dotenv(path):
        if str(path) == str(env_file):
            os.environ["GEMINI_API_KEY"] = "loaded_from_test_env"

    with patch.dict(os.environ, {}, clear=True):
        with (
            patch("pathlib.Path.is_file", autospec=True, side_effect=fake_is_file),
            patch("dotenv.load_dotenv", side_effect=fake_load_dotenv) as mock_load,
        ):
            ensure_env_loaded()
            mock_load.assert_called()
            assert os.environ.get("GEMINI_API_KEY") == "loaded_from_test_env"


def test_ensure_env_loaded_handles_dotenv_import_error():
    orig_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("No module named dotenv")
        return orig_import(name, *args, **kwargs)

    with patch.dict(os.environ, {}, clear=True):
        with patch("builtins.__import__", side_effect=failing_import):
            # Must not raise
            ensure_env_loaded()


def test_get_active_models_fallback_when_client_fails():
    bad_client = SimpleNamespace(
        models=SimpleNamespace(list=MagicMock(side_effect=RuntimeError("API failure")))
    )
    assert get_active_models(bad_client) == list(ACTIVE_FREE_MODELS)


def test_get_active_models_filtering_and_priority():
    items = [
        SimpleNamespace(name="models/custom-flash-model", supported_actions=[]),
        SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.5-flash-lite", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/unsupported-model", supported_actions=["embedContent"]),
        "models/unnamed-flash-model",
    ]
    client = SimpleNamespace(models=SimpleNamespace(list=MagicMock(return_value=items)))
    models = get_active_models(client)

    # ACTIVE_FREE_MODELS priority
    assert models[0] == "gemini-3.5-flash-lite"
    assert models[1] == "gemini-2.5-flash"
    assert "custom-flash-model" in models
    assert "unnamed-flash-model" in models
    assert "unsupported-model" not in models


def test_get_active_models_when_filtered_list_is_empty():
    items = [SimpleNamespace(name="models/text-embedding", supported_actions=["embedContent"])]
    client = SimpleNamespace(models=SimpleNamespace(list=MagicMock(return_value=items)))
    assert get_active_models(client) == list(ACTIVE_FREE_MODELS)


def test_probe_gemini_models_client_init_failure():
    orig_import = builtins.__import__

    def failing_genai(name, *args, **kwargs):
        if name == "google.genai" or name == "google":
            raise ImportError("Cannot import genai")
        return orig_import(name, *args, **kwargs)

    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
        with patch("builtins.__import__", side_effect=failing_genai):
            results = probe_gemini_models(client=None)
            assert len(results) == 1
            assert results[0]["name"] == "client_init"
            assert results[0]["status"] == "FAILED"


def test_probe_gemini_models_various_status_codes():
    def fake_generate(model, contents):
        if "3.5-flash-lite" in model:
            return SimpleNamespace(text="  Custom response text  ")
        if "2.5-flash-lite" in model:
            return SimpleNamespace(text="")  # returns OK
        if "2.5-flash" in model:
            raise RuntimeError("429 Resource has been exhausted (quota exceeded)")
        if "flash-lite-latest" in model:
            raise RuntimeError("504 Gateway Timeout: deadline expired")
        if "3.1-flash-lite-preview" in model:
            raise RuntimeError("404 Model not found")
        if "3.1-flash-lite" in model:
            raise RuntimeError("503 Service Unavailable: overloaded")
        raise RuntimeError("Fatal connection aborted")

    client = SimpleNamespace(
        models=SimpleNamespace(
            list=MagicMock(
                return_value=[
                    SimpleNamespace(name="models/gemini-3.5-flash-lite", supported_actions=[]),
                    SimpleNamespace(name="models/gemini-2.5-flash-lite", supported_actions=[]),
                    SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=[]),
                    SimpleNamespace(name="models/gemini-flash-lite-latest", supported_actions=[]),
                    SimpleNamespace(name="models/gemini-3.1-flash-lite", supported_actions=[]),
                    SimpleNamespace(name="models/gemini-3.1-flash-lite-preview", supported_actions=[]),
                    SimpleNamespace(name="models/other-flash-failure", supported_actions=[]),
                ]
            ),
            generate_content=MagicMock(side_effect=fake_generate),
        )
    )

    results = probe_gemini_models(client=client, prompt="Hello", timeout_sec=15)
    by_name = {r["name"]: r for r in results}

    assert by_name["gemini-3.5-flash-lite"]["status"] == "WORKING"
    assert by_name["gemini-3.5-flash-lite"]["note"] == "Custom response text"

    assert by_name["gemini-2.5-flash-lite"]["status"] == "WORKING"
    assert by_name["gemini-2.5-flash-lite"]["note"] == "OK"

    assert by_name["gemini-2.5-flash"]["status"] == "QUOTA_LIMITED (PAID TIER)"
    assert "paid tier" in by_name["gemini-2.5-flash"]["note"]

    assert by_name["gemini-flash-lite-latest"]["status"] == "TIMEOUT (504)"
    assert "15s" in by_name["gemini-flash-lite-latest"]["note"]

    assert by_name["gemini-3.1-flash-lite"]["status"] == "HIGH_DEMAND (503)"
    assert "temporarily unavailable" in by_name["gemini-3.1-flash-lite"]["note"]

    assert by_name["gemini-3.1-flash-lite-preview"]["status"] == "NOT_FOUND (404)"
    assert "deprecated or unavailable" in by_name["gemini-3.1-flash-lite-preview"]["note"]

    assert by_name["other-flash-failure"]["status"] == "FAILED"
    assert "Fatal connection aborted" in by_name["other-flash-failure"]["note"]


def test_get_verified_active_models_filters_only_working():
    mock_results = [
        {"name": "gemini-3.5-flash-lite", "status": "WORKING"},
        {"name": "gemini-2.5-flash", "status": "QUOTA_LIMITED (PAID TIER)"},
        {"name": "gemini-2.5-flash-lite", "status": "WORKING"},
    ]
    with patch("utils.models.probe_gemini_models", return_value=mock_results):
        verified = get_verified_active_models()
        assert verified == ["gemini-3.5-flash-lite", "gemini-2.5-flash-lite"]


def test_test_gemini_models_is_alias():
    assert test_gemini_models is probe_gemini_models
