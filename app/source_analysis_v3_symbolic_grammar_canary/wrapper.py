"""
Wrapper canary minuscule.

N'altère PAS window-analysis-1.3. Réutilise le system prompt 1.3 tel quel
et ajoute un user wrapper dédié (fixture synthétique + consigne triviale).
"""

from __future__ import annotations

from app.file_utils import content_hash
from app.source_analysis_local_v3.prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    build_window_system_prompt_v13,
    window_prompt_v13_sha256,
)
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    DEFERRED_KINDS,
    LOCAL_KINDS,
    SEMANTIC_TRANSPORT_VERSION_V3,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_TEXTS,
    WRAPPER_VERSION,
)
from app.source_analysis_v3_symbolic_grammar_canary.fixture import SyntheticCanaryFixture

_CANARY_USER_PREFIX = f"""V3 SYMBOLIC-HANDLE GRAMMAR/CONFIG CANARY — synthetic only.

Wrapper version: {WRAPPER_VERSION}
Prompt family: {WINDOW_ANALYSIS_PROMPT_VERSION_V13} compatible contract (system prompt unchanged).
Transport: {SEMANTIC_TRANSPORT_VERSION_V3}.
Architecture: LOCAL_SYMBOLIC_HANDLES.
This is NOT a pastoral transcript and NOT a quality benchmark.

Produce a very small valid {SEMANTIC_TRANSPORT_VERSION_V3} object that exercises symbolic handles:
- exactly two TOPIC records owning T handles (T1, T2, …)
- exactly three IDEA records owning I handles (I1, I2, I3, …)
- exactly one RELATION with l = two distinct I handles
- exactly one EXAMPLE with l = one or more I handles
At least one IDEA must target a T handle.
Do not use numeric global record indexes in l.
Do not invent owner handles on RELATION or EXAMPLE.
Use only the synthetic source ids listed below.
Allowed local kinds: {", ".join(LOCAL_KINDS)}.
Forbidden deferred kinds: {", ".join(DEFERRED_KINDS)}.
Do not emit analysis_capacity_exceeded.
Do not invent production SRC or WIN identifiers.

WINDOW — {CANARY_WINDOW_ID} — transcript {CANARY_TRANSCRIPT_ID}
OWNED SOURCES
"""


def build_canary_system_prompt(primary_language: str = "en") -> str:
    return build_window_system_prompt_v13(primary_language)


def prompt_1_3_hash(primary_language: str = "en") -> str:
    return window_prompt_v13_sha256(build_canary_system_prompt(primary_language))


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
        "\n<<<CANARY_V3_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<CANARY_V3_USER>>>\n"
        + (user_prompt or "")
    )


__all__ = [
    "build_canary_system_prompt",
    "build_canary_user_prompt",
    "prompt_1_3_hash",
    "wrapper_hash",
]
