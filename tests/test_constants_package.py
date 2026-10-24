from __future__ import annotations

import constants
from ai import (
    ACTIVE_FREE_MODELS as AI_ACTIVE_FREE_MODELS,
)
from ai import (
    DEFAULT_MODEL as AI_DEFAULT_MODEL,
)
from ai import (
    TEST_PROMPT_DEFAULT as AI_TEST_PROMPT_DEFAULT,
)
from validator import (
    ALLOWED_HEADINGS as VAL_ALLOWED_HEADINGS,
)
from validator import (
    PROHIBITED_WORDS as VAL_PROHIBITED_WORDS,
)


def test_constants_exports():
    assert constants.ACTIVE_FREE_MODELS is AI_ACTIVE_FREE_MODELS
    assert constants.DEFAULT_MODEL is AI_DEFAULT_MODEL
    assert constants.TEST_PROMPT_DEFAULT is AI_TEST_PROMPT_DEFAULT
    assert constants.ALLOWED_HEADINGS is VAL_ALLOWED_HEADINGS
    assert constants.PROHIBITED_WORDS is VAL_PROHIBITED_WORDS
    assert constants.EXTRA_TIME_NOTE == "(The task is done in extra time)"
    assert len(constants.ACTIVE_FREE_MODELS) >= 5
    assert len(constants.ALLOWED_HEADINGS) >= 5
    assert len(constants.PROHIBITED_WORDS) >= 5
