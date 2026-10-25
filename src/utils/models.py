from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

TEST_PROMPT_DEFAULT: str = "Reply with 'MODEL_NAME is active' in 5 words or less."


def ensure_env_loaded() -> None:
    """Ensure environment variables are loaded from .env if not already set."""
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return
    try:
        from dotenv import load_dotenv

        candidates = [
            Path.cwd() / ".env",
            Path(__file__).parents[3] / ".env",
            Path("/home/folium/Documents/Aevora/backend/.env"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                load_dotenv(candidate)
                if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
                    break
    except ImportError:
        pass


def get_active_models(client: Any = None) -> list[str]:
    """Retrieve active Gemini models supporting content generation, prioritizing free/flash-lite models.

    Matches Aevora's active model discovery.
    """
    from constants import ACTIVE_FREE_MODELS

    if client is not None and hasattr(client, "models") and hasattr(client.models, "list"):
        try:
            available: list[str] = []
            for item in client.models.list():
                actions = getattr(item, "supported_actions", []) or []
                if not actions or "generateContent" in actions:
                    raw_name = getattr(item, "name", str(item))
                    name = raw_name.removeprefix("models/")
                    available.append(name)
            # Prioritize verified active free models first
            active = [m for m in ACTIVE_FREE_MODELS if m in available]
            # Add other available flash-tier models
            active.extend([m for m in available if m not in active and "flash" in m])
            if active:
                return active
        except Exception:  # noqa: BLE001
            pass
    return list(ACTIVE_FREE_MODELS)


def probe_gemini_models(
    client: Any = None,
    prompt: str = TEST_PROMPT_DEFAULT,
    timeout_sec: int = 10,
) -> list[dict[str, Any]]:
    """Test available Gemini models by sending a live prompt and recording status and latency.

    Directly ported from Aevora's test_gemini_models.
    """
    ensure_env_loaded()
    if client is None:
        try:
            from google import genai

            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            client = genai.Client(api_key=api_key)
        except Exception as exc:  # noqa: BLE001
            return [{"name": "client_init", "status": "FAILED", "latency": 0, "note": str(exc)}]

    active_models = get_active_models(client)
    results: list[dict[str, Any]] = []

    for model_name in active_models:
        start_time = time.time()
        try:
            res = client.models.generate_content(model=model_name, contents=prompt)
            duration_ms = round((time.time() - start_time) * 1000)
            output_text = res.text.strip().replace("\n", " ") if hasattr(res, "text") and res.text else "OK"
            results.append(
                {
                    "name": model_name,
                    "status": "WORKING",
                    "latency": duration_ms,
                    "note": output_text[:50],
                }
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = round((time.time() - start_time) * 1000)
            err_str = str(exc).replace("\n", " ")
            if "429" in err_str or "quota" in err_str.lower():
                status_label = "QUOTA_LIMITED (PAID TIER)"
                note = "Requires paid tier or separate billing"
            elif "504" in err_str or "deadline" in err_str.lower():
                status_label = "TIMEOUT (504)"
                note = f"Deadline expired after {timeout_sec}s"
            elif "404" in err_str or "not found" in err_str.lower():
                status_label = "NOT_FOUND (404)"
                note = "Model endpoint deprecated or unavailable"
            elif "503" in err_str or "unavailable" in err_str.lower():
                status_label = "HIGH_DEMAND (503)"
                note = "Model temporarily unavailable"
            else:
                status_label = "FAILED"
                note = err_str[:60]
            results.append(
                {
                    "name": model_name,
                    "status": status_label,
                    "latency": duration_ms,
                    "note": note,
                }
            )
    return results


def get_verified_active_models(client: Any = None, timeout_sec: int = 10) -> list[str]:
    """Return only verified working active models tested with a live prompt."""
    results = probe_gemini_models(client=client, timeout_sec=timeout_sec)
    return [r["name"] for r in results if r["status"] == "WORKING"]


# Aevora alias
test_gemini_models = probe_gemini_models

__all__ = [
    "ensure_env_loaded",
    "get_active_models",
    "get_verified_active_models",
    "probe_gemini_models",
    "test_gemini_models",
]
