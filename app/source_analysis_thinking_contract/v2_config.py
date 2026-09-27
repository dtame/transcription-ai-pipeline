"""Configuration thinking V2 uniquement. Ne change pas source_analysis production."""

from __future__ import annotations

from typing import Any

from app.ai.thinking import (
    CONTRACT_THINKING_DISABLED,
    THINKING_MODE_DISABLED,
    thinking_identity,
)
from app.source_analysis_thinking_contract.constants import (
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SELECTED_THINKING_MODE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
)

assert SELECTED_CONTRACT == CONTRACT_THINKING_DISABLED
assert SELECTED_THINKING_MODE == THINKING_MODE_DISABLED
assert SELECTED_EFFORT is None

V2_STAGE = "source_analysis_window_v2"
V2_THINKING_CONTRACT = SELECTED_CONTRACT
V2_THINKING_MODE = SELECTED_THINKING_MODE
V2_EFFORT = SELECTED_EFFORT


def v2_thinking_metadata() -> dict[str, Any]:
    identity = thinking_identity(
        thinking_mode=V2_THINKING_MODE,
        effort=V2_EFFORT,
    )
    return {
        "stage_config": V2_STAGE,
        "thinking_contract": V2_THINKING_CONTRACT,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
        **identity,
    }


__all__ = [
    "V2_EFFORT",
    "V2_STAGE",
    "V2_THINKING_CONTRACT",
    "V2_THINKING_MODE",
    "v2_thinking_metadata",
]
