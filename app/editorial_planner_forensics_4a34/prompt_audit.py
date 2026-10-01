"""Prompt 1.0 / 1.0.1 coverage-instruction analysis. Does not mutate prompts."""

from __future__ import annotations

from typing import Any

from app.editorial_planning.prompt import (
    instruction_prompt as instruction_10,
    system_prompt as system_10,
)
from app.editorial_planning.prompt_v101 import (
    instruction_prompt as instruction_101,
    system_prompt as system_101,
)
from app.editorial_planning.prompt_v102 import (
    coverage_hardening_rule,
    instruction_prompt as instruction_102,
    system_prompt as system_102,
)

_COVERAGE_PHRASES = (
    "Toute IDEA",
    "disposition explicite",
    "omission silencieuse",
    "deferred",
    "excluded",
)


def _positions(text: str) -> dict[str, Any]:
    length = max(1, len(text))
    found: dict[str, Any] = {}
    for phrase in _COVERAGE_PHRASES:
        pos = text.find(phrase)
        found[phrase] = {
            "present": pos >= 0,
            "offset": pos,
            "fraction": round(pos / length, 3) if pos >= 0 else None,
            "band": (
                "early"
                if 0 <= pos < length * 0.33
                else "middle"
                if pos >= 0 and pos < length * 0.66
                else "late"
                if pos >= 0
                else None
            ),
        }
    return {"chars": len(text), "phrases": found}


def prompt_coverage_analysis() -> dict[str, Any]:
    sys10 = system_10()
    inst10 = instruction_10()
    sys101 = system_101("en")
    inst101 = instruction_101("en")
    sys102 = system_102("en")
    inst102 = instruction_102("en")
    hardening = coverage_hardening_rule()
    mid_system_rule = (
        "Toute IDEA du SourceMap doit avoir une disposition explicite"
        in sys10
    )
    late_output_repeat_101 = (
        "Toute IDEA du SourceMap doit avoir une disposition explicite" in inst101
    )
    return {
        "historical_1_0_mutated": False,
        "historical_1_0_1_mutated": False,
        "principal_1_0_vs_1_0_1_diff": "canonical language rule only",
        "language_rule_preserved_in_1_0_2": (
            "LANGUE DE SORTIE OBLIGATOIRE" in sys102
            and "canonical_document_language" in inst102
        ),
        "v10": {
            "system": _positions(sys10),
            "instructions": _positions(inst10),
        },
        "v101": {
            "system": _positions(sys101),
            "instructions": _positions(inst101),
        },
        "v102": {
            "system": _positions(sys102),
            "instructions": _positions(inst102),
            "contains_hardening": hardening.strip() in sys102
            and hardening.strip() in inst102,
            "mentions_IDEA007": "IDEA007" in sys102 or "IDEA007" in inst102,
            "mentions_IDEA008": "IDEA008" in sys102 or "IDEA008" in inst102,
            "mentions_pastoral_specifics": any(
                token in sys102.lower() or token in inst102.lower()
                for token in ("sinners", "hebrews", "long life", "planted")
            ),
        },
        "coverage_wording_1_0_system": (
            "Toute IDEA du SourceMap doit avoir une disposition explicite :\n"
            "- présente dans une section (ASSIGNED), ou\n"
            "- listed in deferred avec motif, ou\n"
            "- listed in excluded avec motif.\n\n"
            "L'omission silencieuse est interdite."
        ),
        "coverage_wording_1_0_instructions": (
            "deferred[] / excluded[] : IDEA absentes des sections, motif fermé."
        ),
        "explicit_every_idea_exactly_once": mid_system_rule,
        "exactly_once_primary_disposition_stated": False,
        "repeated_near_output_contract_in_1_0_1": late_output_repeat_101,
        "coverage_salience_1_0_1": {
            "system_band": "middle",
            "instructions_near_output_contract": False,
            "language_rule_appended_after_coverage": True,
        },
        "ambiguity": {
            "could_organize_important_ideas_without_emitting_every_handle": True,
            "why": (
                "The exhaustive-handle rule sits mid-system. Instructions "
                "require non-empty section i[] and closed deferred/excluded "
                "reasons but do not restate that every input IDEA ID must "
                "appear. A model can emit a coherent book structure and "
                "still drop two handles."
            ),
        },
        "prompt_coverage_weakness": "YES",
        "prompt_1_0_2_hardening_present": hardening.strip() in sys102,
    }


__all__ = ["prompt_coverage_analysis"]
