"""Candidate editorial policy. Not activated in production."""

from __future__ import annotations

from typing import Any

from app.book_editorial_alignment_4b216.constants import (
    EDITORIAL_POLICY_ACTIVATED,
    EDITORIAL_POLICY_VERSION,
    PHASE,
    THEMATIC_RULES_VERSION,
)

ALLOWED_TRANSFORMATIONS: tuple[dict[str, str], ...] = (
    {
        "id": "grammatical_correction",
        "statement": "Grammatical correction of an already stated teaching.",
    },
    {
        "id": "spelling_correction",
        "statement": "Spelling correction of an already stated teaching.",
    },
    {
        "id": "punctuation_correction",
        "statement": "Punctuation correction of an already stated teaching.",
    },
    {
        "id": "hesitation_removal",
        "statement": "Removal of a hesitation that carries no semantic value.",
    },
    {
        "id": "accidental_repetition_removal",
        "statement": "Removal of an accidental repetition.",
    },
    {
        "id": "light_reformulation",
        "statement": "Light reformulation that improves readability without adding meaning.",
    },
    {
        "id": "thematic_reorganization",
        "statement": "Thematic reorganization of teachings that are already in the sources.",
    },
    {
        "id": "same_subject_grouping",
        "statement": "Grouping of passages that treat the same subject.",
    },
    {
        "id": "controlled_redundant_fusion",
        "statement": "Controlled fusion of redundant passages that do not add a new nuance.",
    },
    {
        "id": "title_creation",
        "statement": "Creation of titles and subtitles.",
    },
    {
        "id": "neutral_transition",
        "statement": "Neutral editorial transitions that introduce no new claim.",
    },
    {
        "id": "chapter_section_organization",
        "statement": "Organization into chapters and sections.",
    },
)

FORBIDDEN_TRANSFORMATIONS: tuple[dict[str, str], ...] = (
    {"id": "new_fact", "statement": "A new fact."},
    {"id": "new_argument", "statement": "A new argument."},
    {"id": "new_example", "statement": "A new example."},
    {"id": "new_reference", "statement": "A new reference."},
    {"id": "new_interpretation", "statement": "A new interpretation."},
    {"id": "new_causality", "statement": "A new causal relation."},
    {"id": "new_implication", "statement": "A new implication."},
    {"id": "new_guarantee", "statement": "A new guarantee."},
    {"id": "certainty_strengthening", "statement": "Strengthening of certainty."},
    {
        "id": "important_reservation_removed",
        "statement": "Removal of an important reservation.",
    },
    {"id": "condition_distortion", "statement": "Distortion of a condition."},
    {"id": "incorrect_attribution", "statement": "Incorrect attribution."},
    {
        "id": "absent_conclusion",
        "statement": "A conclusion that is absent from the sources.",
    },
    {
        "id": "opinion_stated_as_fact",
        "statement": "A speaker's opinion transformed into an established fact.",
    },
)

THEMATIC_RULES: tuple[dict[str, str], ...] = (
    {
        "id": "A",
        "name": "grouping",
        "statement": (
            "Passages from different moments may be grouped when they really "
            "treat the same subject."
        ),
    },
    {
        "id": "B",
        "name": "reasoning_preservation",
        "statement": (
            "Do not separate a claim from the conditions, reservations, or "
            "examples required to understand it."
        ),
    },
    {
        "id": "C",
        "name": "no_invented_causality",
        "statement": (
            "Placing two passages together does not authorize a claim that "
            "one explains, proves, or causes the other."
        ),
    },
    {
        "id": "D",
        "name": "neutral_transitions",
        "statement": (
            "A neutral transition such as 'Another aspect of this teaching "
            "concerns prayer.' is allowed. A transition that introduces an "
            "unproven necessity, cause, or universal result is not."
        ),
        "allowed_example": "Another aspect of this teaching concerns prayer.",
        "forbidden_example": (
            "This necessarily proves that prayer is the cause of every spiritual victory."
        ),
    },
    {
        "id": "E",
        "name": "repetition_classes",
        "statement": (
            "Distinguish accidental repetition from pedagogical repetition, "
            "rhetorical repetition, and repetition that adds a new nuance. "
            "Do not delete the last three classes automatically."
        ),
    },
    {
        "id": "F",
        "name": "attribution",
        "statement": (
            "When several interventions or voices are present, do not merge "
            "their positions as if they necessarily came from the same speaker."
        ),
    },
)

RESPONSIBILITY_SPLIT: dict[str, Any] = {
    "editorial_planner": {
        "owns": [
            "thematic organization",
            "assignment of ideas",
            "chapter structure",
            "section structure",
            "coherence of the plan",
        ],
        "must_not": [
            "create new ideas in order to improve the structure artificially",
            "write manuscript paragraphs",
        ],
        "already_stated_by": "app.editorial_planning.prompt",
        "moved_into_book_generator": False,
    },
    "book_generator": {
        "owns": [
            "faithful wording",
            "fluency",
            "readability",
            "local coherence",
            "preservation of reasonings",
            "preservation of examples",
            "preservation of nuances",
        ],
        "must_not": [
            "freely reconstruct the intellectual content",
            "invent arguments, examples, causalities, implications, guarantees, or conclusions",
            "replace the EditorialPlan's structure",
        ],
    },
}


def editorial_policy() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": EDITORIAL_POLICY_VERSION,
        "activated_in_production": EDITORIAL_POLICY_ACTIVATED,
        "guiding_principle": (
            "Freedom to organize the teachings. Strict fidelity to their "
            "content and to their relations of meaning."
        ),
        "product_definition": (
            "The book restores the original teaching in an organized, "
            "coherent, and readable form. It is not a new intellectual work "
            "inspired by the recordings."
        ),
        "thematic_reorganization_authorized": True,
        "intellectual_invention_authorized": False,
        "fidelity_is_more_than_absence_of_invention": (
            "Important ideas, reasonings, examples, and nuances must also be kept."
        ),
        "allowed_transformations": [dict(item) for item in ALLOWED_TRANSFORMATIONS],
        "forbidden_transformations": [dict(item) for item in FORBIDDEN_TRANSFORMATIONS],
        "thematic_rules_version": THEMATIC_RULES_VERSION,
        "thematic_rules": [dict(item) for item in THEMATIC_RULES],
        "responsibility_split": RESPONSIBILITY_SPLIT,
        "does_not_modify_historical_prompts": True,
        "does_not_modify_canonical_artifacts": True,
        "secrets_included": False,
    }


def allowed_ids() -> tuple[str, ...]:
    return tuple(item["id"] for item in ALLOWED_TRANSFORMATIONS)


def forbidden_ids() -> tuple[str, ...]:
    return tuple(item["id"] for item in FORBIDDEN_TRANSFORMATIONS)


__all__ = [
    "ALLOWED_TRANSFORMATIONS",
    "FORBIDDEN_TRANSFORMATIONS",
    "THEMATIC_RULES",
    "allowed_ids",
    "editorial_policy",
    "forbidden_ids",
]
