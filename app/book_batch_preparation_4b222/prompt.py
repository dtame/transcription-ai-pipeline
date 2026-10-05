"""Verify prompt 1.1 hash and keep it an isolated explicit selection."""

from __future__ import annotations

from typing import Any

from app.book_batch_preparation_4b222.constants import EXPECTED_PROMPT_1_1_SHA256, PHASE
from app.book_batch_preparation_4b222.guard import BookBatchPreparation4222Error
from app.book_scale_up_preparation_4b220.prompt_readiness import generator_prompt_11_readiness


def verify_prompt_1_1() -> dict[str, Any]:
    prompt = generator_prompt_11_readiness()
    observed = str(prompt.get("prompt_sha256") or "")
    if observed != EXPECTED_PROMPT_1_1_SHA256:
        raise BookBatchPreparation4222Error(
            "Prompt 1.1 hash mismatch. STOP. "
            f"observed={observed} expected={EXPECTED_PROMPT_1_1_SHA256}"
        )
    if prompt.get("activated") is True:
        raise BookBatchPreparation4222Error("Prompt 1.1 must remain globally inactive.")
    if prompt.get("registered_in_prompt_select") is True:
        raise BookBatchPreparation4222Error(
            "Prompt 1.1 must remain unregistered in production prompt_select."
        )
    return {
        "phase": PHASE,
        "version": prompt.get("version"),
        "available": prompt.get("available"),
        "isolated": prompt.get("isolated"),
        "activated": False,
        "explicitly_selected": True,
        "globally_activated": False,
        "historical_prompts_modified": False,
        "hash_match": True,
        "prompt_sha256": observed,
        "expected_prompt_sha256": EXPECTED_PROMPT_1_1_SHA256,
        "system_sha256": prompt.get("system_sha256"),
        "instructions_sha256": prompt.get("instructions_sha256"),
        "ready_as_isolated_candidate": prompt.get("ready_as_isolated_candidate"),
        "ready_for_production": False,
        "readiness": prompt,
        "secrets_included": False,
    }


__all__ = ["verify_prompt_1_1"]
