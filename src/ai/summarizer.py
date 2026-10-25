from __future__ import annotations

import os
from typing import Any, Protocol

from constants import ACTIVE_FREE_MODELS
from report.data_classes import ReportChunk
from utils.models import ensure_env_loaded, get_active_models
from utils.prompt import build_prompt, build_review_prompt


class Summarizer(Protocol):
    def summarize(self, chunk: ReportChunk) -> str: ...


class GeminiSummarizer:
    def __init__(self, model: str = "", *, client: Any = None):
        ensure_env_loaded()
        self._owns_client = client is None

        # Resolve model name: explicit argument > GEMINI_MODEL env var > active free models default
        chosen_model = (model or os.getenv("GEMINI_MODEL", "")).strip()
        if not chosen_model:
            active = get_active_models(client)
            if active:
                chosen_model = active[0]
            else:
                raise ValueError("Supply --model or GEMINI_MODEL when AI is enabled.")

        self.model = chosen_model

        if client is None:
            if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
                raise ValueError("Set GEMINI_API_KEY or GOOGLE_API_KEY for AI summaries.")
            try:
                from google import genai
            except ImportError as exc:
                raise ValueError("Install the AI extra: python -m pip install -e './workedTask[ai]'") from exc
            client = genai.Client()
        self.client = client

    def summarize(self, chunk: ReportChunk) -> str:
        return self._generate(build_prompt(chunk))

    def summarize_review(self, chunk: ReportChunk) -> str:
        return self._generate(build_review_prompt(chunk))

    def _generate(self, prompt: str) -> str:
        # Candidates to try: primary model first, followed by active free models fallback (Aevora pattern)
        candidates = [self.model]
        active = get_active_models(self.client)
        for m in active:
            if m not in candidates:
                candidates.append(m)

        last_error: Exception | None = None
        for candidate_model in candidates:
            try:
                response = self.client.models.generate_content(
                    model=candidate_model,
                    contents=prompt,
                )
                if response and hasattr(response, "text") and response.text and response.text.strip():
                    self.model = candidate_model
                    return response.text.strip()
                last_error = RuntimeError("AI returned no summary.")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                err_str = str(exc).lower()
                if any(
                    k in err_str
                    for k in ("429", "quota", "503", "unavailable", "504", "deadline", "404", "not found")
                ):
                    continue
                # For mock clients in unit tests or unrecoverable errors, do not retry further
                break

        if last_error is not None:
            raise last_error
        raise RuntimeError("AI returned no summary.")

    def close(self) -> None:
        if self._owns_client and hasattr(self.client, "close"):
            self.client.close()


__all__ = [
    "ACTIVE_FREE_MODELS",
    "GeminiSummarizer",
    "Summarizer",
]
