"""
Isolated selector for book-generator-faithful-restatement-1.1-candidate.

Disabled by default. Not registered in app.book_generation.prompt_select.
Does not replace 1.0 or 1.0.1. Does not fall back to an older prompt.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from app.book_generation.prompt_select import resolve_prompt_module
from app.book_scale_up_preparation_4b220.constants import (
    FAITHFUL_PROMPT_1_0,
    FAITHFUL_PROMPT_1_1,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    HISTORICAL_PROMPT_V101_ID,
    HISTORICAL_PROMPT_V10_ID,
    PHASE,
    PROMPT_SELECT_VERSION,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
)
from app.book_scale_up_preparation_4b220.guard import (
    BookScaleUpPreparation4220Error,
    reject_prompt_fallback,
)


HISTORICAL_PROMPT_IDS = frozenset(
    {
        HISTORICAL_PROMPT_V10_ID,
        HISTORICAL_PROMPT_V101_ID,
        FAITHFUL_PROMPT_1_0,
    }
)


def prompt_1_1_registered_in_production() -> bool:
    try:
        resolve_prompt_module(FAITHFUL_PROMPT_1_1)
    except ValueError:
        return False
    return True


def load_prompt_1_1_module() -> ModuleType:
    try:
        from app.book_authorial_voice_4b218 import prompt_candidate
    except ImportError as exc:
        reject_prompt_fallback(FAITHFUL_PROMPT_1_1, FAITHFUL_PROMPT_1_0)
        raise BookScaleUpPreparation4220Error(
            "Prompt 1.1 candidate module is unavailable."
        ) from exc
    return prompt_candidate


def inspect_prompt_1_1() -> dict[str, Any]:
    module = load_prompt_1_1_module()
    bundle = module.prompt_bundle()
    if bundle.get("version") != FAITHFUL_PROMPT_1_1:
        raise BookScaleUpPreparation4220Error(
            f"Prompt candidate version is {bundle.get('version')!r}, not "
            f"{FAITHFUL_PROMPT_1_1}."
        )
    return bundle


def resolve_isolated_prompt(
    version: str,
    *,
    activate: bool = False,
    authorization_scope: str | None = None,
    cost_authorization_present: bool = False,
) -> ModuleType:
    requested = str(version or "").strip()
    if requested in HISTORICAL_PROMPT_IDS:
        raise BookScaleUpPreparation4220Error(
            f"Isolated 4B.2.20 selector will not serve historical prompt {requested}."
        )
    if requested != FAITHFUL_PROMPT_1_1:
        raise BookScaleUpPreparation4220Error(
            f"unknown isolated prompt version: {requested}"
        )
    if prompt_1_1_registered_in_production():
        raise BookScaleUpPreparation4220Error(
            "Prompt 1.1 must remain unregistered in production prompt_select."
        )
    module = load_prompt_1_1_module()
    bundle = module.prompt_bundle()
    if bundle.get("version") != FAITHFUL_PROMPT_1_1:
        reject_prompt_fallback(FAITHFUL_PROMPT_1_1, FAITHFUL_PROMPT_1_0)
    if not activate:
        return module
    if FAITHFUL_PROMPT_1_1_ACTIVATED:
        raise BookScaleUpPreparation4220Error(
            "Global prompt 1.1 activation is forbidden."
        )
    if not REAL_CHAPTER_GENERATION_AUTHORIZED:
        raise BookScaleUpPreparation4220Error(
            "Prompt 1.1 activation for generation is disabled in this phase."
        )
    if not cost_authorization_present or not authorization_scope:
        raise BookScaleUpPreparation4220Error(
            "Future prompt 1.1 activation requires an explicit option and a "
            "distinct cost authorization."
        )
    return module


def prompt_select_contract() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": PROMPT_SELECT_VERSION,
        "requested_id": FAITHFUL_PROMPT_1_1,
        "registered_in_production_prompt_select": prompt_1_1_registered_in_production(),
        "replaces_historical_prompt": False,
        "replaces_faithful_prompt_1_0_candidate": False,
        "globally_activated": FAITHFUL_PROMPT_1_1_ACTIVATED,
        "fallback_if_unavailable": None,
        "fallback_forbidden": True,
        "default_state": "inactive_isolated_candidate",
        "future_activation_requires": [
            "explicit prompt version book-generator-faithful-restatement-1.1-candidate",
            "explicit activation option",
            "distinct per-chapter cost authorization",
            "REAL_CHAPTER_GENERATION_AUTHORIZED for that later phase",
        ],
        "historical_versions_left_in_place": sorted(HISTORICAL_PROMPT_IDS),
        "secrets_included": False,
    }


__all__ = [
    "HISTORICAL_PROMPT_IDS",
    "inspect_prompt_1_1",
    "load_prompt_1_1_module",
    "prompt_1_1_registered_in_production",
    "prompt_select_contract",
    "resolve_isolated_prompt",
]
