"""
Wrapper canary minuscule.

N'altère PAS window-analysis-1.2. Réutilise le system prompt 1.2 tel quel
et ajoute un user wrapper dédié (fixture synthétique + consigne triviale).
"""

from __future__ import annotations

from app.file_utils import content_hash
from app.source_analysis_local_v2.prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
    build_window_system_prompt_v12,
)
from app.source_analysis_v2_grammar_canary.constants import (
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    DEFERRED_KINDS,
    LOCAL_KINDS,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_TEXTS,
)
from app.source_analysis_v2_grammar_canary.fixture import SyntheticCanaryFixture

_CANARY_USER_PREFIX = f"""V2 GRAMMAR/CONFIG CANARY — synthetic only.

Prompt family: {WINDOW_ANALYSIS_PROMPT_VERSION_V12} compatible contract.
Transport: {SEMANTIC_TRANSPORT_VERSION_V2}.
This is NOT a pastoral transcript and NOT a quality benchmark.

Produce a very small valid {SEMANTIC_TRANSPORT_VERSION_V2} object:
- one TOPIC
- one IDEA
- optionally one EXAMPLE
Use only the synthetic source ids listed below.
Allowed local kinds: {", ".join(LOCAL_KINDS)}.
Forbidden deferred kinds: {", ".join(DEFERRED_KINDS)}.
Do not emit analysis_capacity_exceeded.
Do not invent production SRC or WIN identifiers.

WINDOW — {CANARY_WINDOW_ID} — transcript {CANARY_TRANSCRIPT_ID}
OWNED SOURCES
"""


def build_canary_system_prompt(primary_language: str = "en") -> str:
    return build_window_system_prompt_v12(primary_language)


def build_canary_user_prompt(fixture: SyntheticCanaryFixture) -> str:
    lines = [_CANARY_USER_PREFIX.rstrip(), ""]
    for src_id, text in zip(SYNTHETIC_SRC_IDS, SYNTHETIC_TEXTS, strict=True):
        lines.append(f"[{src_id}] {text}")
    lines.extend(
        [
            "",
            "CONTEXT-ONLY SOURCES",
            "(none)",
            "",
            "Return only the JSON transport.",
        ]
    )
    owned = list(fixture.window.owned_src_refs)
    if owned != list(SYNTHETIC_SRC_IDS):
        raise ValueError("wrapper refused non-synthetic owned refs")
    return "\n".join(lines)


def wrapper_hash(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<CANARY_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<CANARY_USER>>>\n"
        + (user_prompt or "")
    )


__all__ = [
    "build_canary_system_prompt",
    "build_canary_user_prompt",
    "wrapper_hash",
]
