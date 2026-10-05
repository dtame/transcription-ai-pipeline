"""Candidate authorial-voice policy. Not activated in production."""

from __future__ import annotations

from typing import Any

from app.book_authorial_voice_4b218.constants import (
    AUTHORIAL_VOICE_POLICY_ACTIVATED,
    AUTHORIAL_VOICE_POLICY_VERSION,
    FORBIDDEN_EXTERNAL_FRAMES,
    PHASE,
)
from app.book_editorial_alignment_4b216.constants import EDITORIAL_POLICY_VERSION


NARRATION_RULES: tuple[dict[str, str], ...] = (
    {
        "id": "A",
        "name": "first_person",
        "statement": (
            "Use I, me, my, we, and our when the original context justifies "
            "that the author is speaking of personal experiences, actions, "
            "memories, convictions, teaching, or spiritual experience."
        ),
    },
    {
        "id": "B",
        "name": "second_person",
        "statement": (
            "Keep you when the speaker addresses the reader or the audience "
            "and that address remains natural in a book."
        ),
    },
    {
        "id": "C",
        "name": "third_person",
        "statement": (
            "Keep third person when the referent is actually another person, "
            "a biblical figure, a witness, an interlocutor, a secondary "
            "speaker, or a reported quotation."
        ),
    },
    {
        "id": "D",
        "name": "general_teaching",
        "statement": (
            "Do not force first person onto a general teaching. "
            "'Prayer requires sincerity.' is acceptable. "
            "'I believe that prayer requires sincerity.' is not required "
            "unless the source states that personal stance."
        ),
        "allowed_example": "Prayer requires sincerity.",
        "forbidden_example": (
            "I believe that prayer requires sincerity. "
            "(unless the source states that personal stance)"
        ),
    },
)

ATTRIBUTION_RULES: tuple[dict[str, str], ...] = (
    {
        "id": "no_speaker_field",
        "statement": (
            "Clean-transcript segments have no speaker field. AUDIO001 to "
            "AUDIO004 name recordings, not four proven persons."
        ),
    },
    {
        "id": "no_audio_inference",
        "statement": (
            "Do not infer a speaker identity from an AUDIO identifier alone."
        ),
    },
    {
        "id": "no_unproven_first_person",
        "statement": (
            "Never transform a third-person testimony into a first-person "
            "testimony without sufficient proof that it belongs to the "
            "main author."
        ),
    },
    {
        "id": "uncertain_keep_original",
        "statement": (
            "If attribution is uncertain: keep the original passage, mark "
            "ATTRIBUTION_UNCERTAIN, record the SRC handles, propose a "
            "candidate correction if useful, and require human review "
            "before application."
        ),
    },
    {
        "id": "secondary_voices",
        "statement": (
            "A main speaker, secondary speakers, questions, reported "
            "quotations, interpretation, and testimonies attributed to "
            "other persons may all be present. Do not merge them."
        ),
    },
)


def authorial_voice_policy() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": AUTHORIAL_VOICE_POLICY_VERSION,
        "activated_in_production": AUTHORIAL_VOICE_POLICY_ACTIVATED,
        "inherits_editorial_policy": EDITORIAL_POLICY_VERSION,
        "guiding_principle": (
            "The book must preserve the main author's narrative voice "
            "rather than describe the author as an external speaker."
        ),
        "product_definition": (
            "The book restores the original teaching as teaching written "
            "by its principal author. It is not a conference report."
        ),
        "narration_rules": [dict(item) for item in NARRATION_RULES],
        "attribution_rules": [dict(item) for item in ATTRIBUTION_RULES],
        "formulations_to_avoid_when_they_name_the_main_author": list(
            FORBIDDEN_EXTERNAL_FRAMES
        ),
        "automatic_global_replacement_forbidden": True,
        "decision_depends_on_context_and_provenance": True,
        "deterministic_controls_do_not_establish_speaker_identity": True,
        "does_not_modify_historical_prompts": True,
        "does_not_modify_canonical_artifacts": True,
        "secrets_included": False,
    }


__all__ = [
    "ATTRIBUTION_RULES",
    "NARRATION_RULES",
    "authorial_voice_policy",
]
