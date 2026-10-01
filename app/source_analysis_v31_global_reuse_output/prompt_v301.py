"""Prompt successeur global-consolidation-3.0.1. Ne mute pas 3.0.

Désigné pour les consolidations futures. Aucun appel provider ici.
Transport / schéma restent 3.0 — l'identité de requête changera, pas le schéma.
"""

from __future__ import annotations

from typing import Any

from app.file_utils import content_hash
from app.source_analysis_v31_global_output_architecture.constants import (
    GLOBAL_INTENT_MAX_CHARS,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_reuse_output.constants import (
    FUTURE_PROMPT_VERSION,
    NEXT_PROMPT_VERSION,
    NEXT_TRANSPORT_VERSION,
    SYNTHESIZED_IDEA_MAX_CHARS,
)
from app.source_analysis_v31_global_reuse_output.prompt_v30 import (
    INSTRUCTIONS,
    SYSTEM_PROMPT as SYSTEM_PROMPT_V30,
    prompt_v30_bundle,
)

assert NEXT_PROMPT_VERSION == "global-consolidation-3.0"
assert FUTURE_PROMPT_VERSION == "global-consolidation-3.0.1"
assert "- intent <= 240" in SYSTEM_PROMPT_V30
assert GLOBAL_INTENT_MAX_CHARS == 320
assert TEXT_LIMITS["intent"] == GLOBAL_INTENT_MAX_CHARS

SYSTEM_PROMPT = SYSTEM_PROMPT_V30.replace(
    "- intent <= 240",
    f"- intent <= {GLOBAL_INTENT_MAX_CHARS}",
)
assert f"- intent <= {GLOBAL_INTENT_MAX_CHARS}" in SYSTEM_PROMPT
assert "- intent <= 240" not in SYSTEM_PROMPT
assert "- intent <= 240" in SYSTEM_PROMPT_V30


def prompt_v301_bundle() -> dict[str, Any]:
    system = SYSTEM_PROMPT.strip() + "\n"
    instructions = INSTRUCTIONS.strip() + "\n"
    previous = prompt_v30_bundle()
    return {
        "prompt_version": FUTURE_PROMPT_VERSION,
        "activated_production": "FUTURE_ONLY",
        "sent_to_provider": False,
        "authorized_for_a48_call": False,
        "previous_prompt_version": previous.get("prompt_version"),
        "previous_prompt_mutated": False,
        "previous_prompt_hash": previous.get("combined_sha256"),
        "system": system,
        "instructions": instructions,
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "combined_sha256": content_hash(system + "\n" + instructions),
        "hard_single_member_reuse": True,
        "synthesized_idea_max_chars": SYNTHESIZED_IDEA_MAX_CHARS,
        "text_limits": dict(TEXT_LIMITS),
        "transport_version": NEXT_TRANSPORT_VERSION,
        "intent_limit": GLOBAL_INTENT_MAX_CHARS,
        "schema_identity_unchanged": True,
        "prompt_identity_affects_request_not_schema": True,
        "do_not_reuse_historical_a45_request_hash": True,
    }


__all__ = ["INSTRUCTIONS", "SYSTEM_PROMPT", "prompt_v301_bundle"]
