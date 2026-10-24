from __future__ import annotations

EXTRA_TIME_NOTE = "(The task is done in extra time)"

ALLOWED_HEADINGS = {
    "Reviewed PRs:",
    "Backend PR:",
    "Frontend PR:",
    "Out of scope:",
    "Overtime:",
}

PROHIBITED_WORDS = [
    "successfully leveraged",
    "seamless integration",
    "enhanced system robustness",
    "spearheaded",
    "game-changing",
    "synergized",
    "innovative solutions",
]

# Verified responsive, free-tier accessible models tested with live prompts in Aevora
ACTIVE_FREE_MODELS: tuple[str, ...] = (
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
)

DEFAULT_MODEL: str = "gemini-3.5-flash-lite"
TEST_PROMPT_DEFAULT: str = "Reply with 'MODEL_NAME is active' in 5 words or less."

__all__ = [
    "ACTIVE_FREE_MODELS",
    "ALLOWED_HEADINGS",
    "DEFAULT_MODEL",
    "EXTRA_TIME_NOTE",
    "PROHIBITED_WORDS",
    "TEST_PROMPT_DEFAULT",
]
