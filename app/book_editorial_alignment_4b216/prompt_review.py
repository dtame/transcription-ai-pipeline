"""Read-only review of the historical Book Generator prompts.

Does not mutate book-generator-1.0 or book-generator-1.0.1.
"""

from __future__ import annotations

from typing import Any

from app.book_editorial_alignment_4b216.constants import (
    FROZEN_GENERATOR_INSTRUCTIONS_SHA256,
    FROZEN_GENERATOR_PROMPT_SHA256,
    FROZEN_GENERATOR_SYSTEM_SHA256,
    PHASE,
)
from app.book_generation.prompt import prompt_bundle as historical_v10_bundle
from app.book_generation.prompt_v101 import prompt_bundle as historical_v101_bundle
from app.editorial_planning.prompt import prompt_bundle as planner_bundle

_FINDINGS: tuple[dict[str, str], ...] = (
    {
        "prompt": "book-generator-1.0",
        "clause": "High stylistic freedom, low semantic freedom.",
        "risk": "literary_rewrite",
        "note": (
            "Low semantic freedom is protective. High stylistic freedom can "
            "still be read as a license to recast a clear sentence into more "
            "impressive prose."
        ),
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "Write a book, not a cleaned transcript.",
        "risk": "literary_rewrite",
        "note": (
            "This pushes the model away from the spoken teaching and toward "
            "a literary object. The candidate prompt does not use this sentence."
        ),
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "improve transitions",
        "risk": "interpretive_transition",
        "note": (
            "Improving transitions is allowed only when the transition stays "
            "neutral. The historical sentence does not state that limit."
        ),
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "combine compatible source statements",
        "risk": "excessive_fusion",
        "note": (
            "Compatible fusion is narrower than fusion of distinct reasonings. "
            "The word compatible is not defined in the prompt."
        ),
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "paraphrase/synthesis is",
        "risk": "unsupported_development",
        "note": (
            "Synthesis can become a new conclusion. The candidate prompt "
            "requires the content of each assigned idea to remain represented."
        ),
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "Remove oral-language artifacts, unnecessary spoken repetition",
        "risk": "nuance_loss",
        "note": (
            "Unnecessary is undefined. Pedagogical, rhetorical, and "
            "nuance-bearing repetitions can be removed under that wording."
        ),
    },
    {
        "prompt": "book-generator-1.0.1",
        "clause": "Stylistic expansion is allowed. Semantic expansion is not.",
        "risk": "literary_rewrite",
        "note": (
            "The second sentence is protective. The first sentence still "
            "authorizes expansion, which can add connective claims."
        ),
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "You do not add new substantive content.",
        "risk": "protective",
        "note": "Already forbids invention. Retained as a constraint, not a defect.",
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "Do not invent arguments, facts, examples",
        "risk": "protective",
        "note": "Already forbids invented examples and arguments.",
    },
    {
        "prompt": "book-generator-1.0.1",
        "clause": "Do not create new examples, illustrations, anecdotes",
        "risk": "protective",
        "note": "Already forbids invented illustrations.",
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "EditorialPlan controls WHERE material belongs.",
        "risk": "protective",
        "note": (
            "Structure remains the Editorial Planner's responsibility. "
            "This phase does not move that responsibility into the generator."
        ),
    },
    {
        "prompt": "book-generator-1.0",
        "clause": "Do not automatically write repetitive chapter conclusions.",
        "risk": "protective",
        "note": "Already resists a synthetic closing. The candidate keeps that limit.",
    },
)


def _joined_historical() -> str:
    first = historical_v10_bundle()
    second = historical_v101_bundle()
    return "\n".join(
        (
            first["system"],
            first["instructions"],
            second["system"],
            second["instructions"],
        )
    )


def current_prompt_review() -> dict[str, Any]:
    corpus = _joined_historical()
    rows = []
    for item in _FINDINGS:
        present = item["clause"] in corpus
        rows.append({**item, "clause_found_in_historical_prompt": present})
    missing = [row["clause"] for row in rows if not row["clause_found_in_historical_prompt"]]
    v10 = historical_v10_bundle()
    v101 = historical_v101_bundle()
    planner = planner_bundle()
    return {
        "phase": PHASE,
        "historical_prompts_modified": False,
        "book_generator_1_0": {
            "version": v10["version"],
            "system_sha256": v10["system_sha256"],
            "instructions_sha256": v10["instructions_sha256"],
            "prompt_sha256": v10["prompt_sha256"],
            "matches_frozen_system": v10["system_sha256"] == FROZEN_GENERATOR_SYSTEM_SHA256,
            "matches_frozen_instructions": (
                v10["instructions_sha256"] == FROZEN_GENERATOR_INSTRUCTIONS_SHA256
            ),
            "matches_frozen_prompt": v10["prompt_sha256"] == FROZEN_GENERATOR_PROMPT_SHA256,
        },
        "book_generator_1_0_1": {
            "version": v101["version"],
            "system_sha256": v101["system_sha256"],
            "instructions_sha256": v101["instructions_sha256"],
            "prompt_sha256": v101["prompt_sha256"],
            "historical_prompt_mutated": v101["historical_prompt_mutated"],
        },
        "editorial_planner": {
            "version": planner["version"],
            "organizes_and_does_not_write_manuscript": (
                "Tu n'écris AUCUN paragraphe de manuscrit." in planner["system"]
            ),
            "does_not_invent_substantive_content": (
                "Tu n'ajoutes aucun argument" in planner["system"]
            ),
            "responsibility_left_in_place": True,
        },
        "findings": rows,
        "clauses_not_found": missing,
        "review_complete": not missing,
        "candidate_does_not_overwrite_these_prompts": True,
        "secrets_included": False,
    }


__all__ = ["current_prompt_review"]
