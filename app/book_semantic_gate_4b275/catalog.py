"""Closed reason-code catalog documentation. No new codes. No silent aliases."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b274.reasons import DIAGNOSTIC_CANDIDATES
from app.book_semantic_gate_4b275.constants import OBSERVED_H02_REASON_CODES, PHASE

RESERVATION_VERDICTS = (CLASS_QUESTIONABLE, CLASS_UNSUPPORTED)
EMPTY_REASON_VERDICTS = (CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE)

PROBLEM_TYPES = {
    "NEW_FACT": "insufficient_or_absent_evidence",
    "NEW_CAUSAL_LINK": "new_causality",
    "NEW_ARGUMENT": "new_argumentative_step",
    "NEW_CONCLUSION": "new_or_stronger_conclusion",
    "NEW_DOCTRINAL_CLAIM": "new_doctrinal_implication",
    "NEW_IMPLICATION": "new_implication",
    "INVENTED_EXAMPLE": "invented_example",
    "INVENTED_ANECDOTE": "invented_narrative",
    "INVENTED_HYPOTHETICAL": "invented_hypothetical",
    "REFERENCE_COMPLETION": "reference_completed_from_external_knowledge",
    "REFERENCE_EXPANSION": "reference_expanded_beyond_supplied_text",
    "QUOTE_EXPANSION": "quoted_wording_not_supplied",
    "UNCERTAINTY_STRENGTHENED": "unjustified_strengthening",
    "SOURCE_MEANING_DISTORTED": "meaning_changed_under_paraphrase",
    "EVIDENCE_MISMATCH": "cited_evidence_does_not_support_claim",
    "OTHER": "unsupported_extension_without_more_specific_code",
}

EXPECTED_EVIDENCE = {
    "NEW_FACT": "No supplied IDEA/SRC/REF attests the asserted fact.",
    "NEW_CAUSAL_LINK": "Related facts may exist; the because/therefore link does not.",
    "NEW_ARGUMENT": "The argumentative step is absent from supplied evidence.",
    "NEW_CONCLUSION": "The conclusion is stronger than, or absent from, the evidence.",
    "NEW_DOCTRINAL_CLAIM": "The doctrinal assertion is not entailed by supplied evidence.",
    "NEW_IMPLICATION": "The implied meaning or origin is not forced by the evidence.",
    "INVENTED_EXAMPLE": "No EX/SRC/IDEA contains the illustrative case.",
    "INVENTED_ANECDOTE": "No supplied narrative attests the anecdote.",
    "INVENTED_HYPOTHETICAL": "The hypothetical is added from model knowledge.",
    "REFERENCE_COMPLETION": "The REF/SRC fragment does not contain the completed remainder.",
    "REFERENCE_EXPANSION": "The REF/SRC contains less than the expanded reference.",
    "QUOTE_EXPANSION": "Supplied wording does not contain the quoted expansion.",
    "UNCERTAINTY_STRENGTHENED": "Canonical modality is weaker than the generated claim.",
    "SOURCE_MEANING_DISTORTED": "Supplied evidence means something else than the claim.",
    "EVIDENCE_MISMATCH": "Cited handles exist but do not support this assertion.",
    "OTHER": "A residual unsupported extension after more specific codes are ruled out.",
}

GENERIC_EXAMPLES = {
    "NEW_FACT": "A named event, group, or quantity appears in the claim but not in evidence.",
    "NEW_CAUSAL_LINK": "Two attested facts are joined by because/therefore without support.",
    "NEW_ARGUMENT": "A new inferential step is inserted between attested points.",
    "NEW_CONCLUSION": "The claim closes with a stronger takeaway than the evidence.",
    "NEW_DOCTRINAL_CLAIM": "A teaching is stated as doctrine without evidential entailment.",
    "NEW_IMPLICATION": "The claim adds 'which means' content the evidence does not force.",
    "INVENTED_EXAMPLE": "An illustrative scene is added that no EX/SRC/IDEA contains.",
    "INVENTED_ANECDOTE": "A personal story is added from outside the evidence.",
    "INVENTED_HYPOTHETICAL": "A what-if scenario is introduced from model knowledge.",
    "REFERENCE_COMPLETION": "A partial citation is finished from memory.",
    "REFERENCE_EXPANSION": "A supplied reference is broadened beyond its actual text.",
    "QUOTE_EXPANSION": "Quoted words are added that the source fragment does not contain.",
    "UNCERTAINTY_STRENGTHENED": "A possibility or partial statement is raised to certainty.",
    "SOURCE_MEANING_DISTORTED": "A paraphrase changes who did what, or under which condition.",
    "EVIDENCE_MISMATCH": "The claim cites a handle whose text does not actually support it.",
    "OTHER": "An unsupported extension that no more specific catalog code names.",
}

CONFUSION_RISKS = {
    "NEW_FACT": ["EVIDENCE_MISMATCH", "OTHER"],
    "NEW_CAUSAL_LINK": ["NEW_IMPLICATION", "NEW_ARGUMENT"],
    "NEW_ARGUMENT": ["NEW_CONCLUSION", "NEW_IMPLICATION"],
    "NEW_CONCLUSION": ["NEW_ARGUMENT", "NEW_DOCTRINAL_CLAIM"],
    "NEW_DOCTRINAL_CLAIM": ["NEW_IMPLICATION", "NEW_CONCLUSION"],
    "NEW_IMPLICATION": ["NEW_CAUSAL_LINK", "NEW_CONCLUSION"],
    "INVENTED_EXAMPLE": ["INVENTED_ANECDOTE", "INVENTED_HYPOTHETICAL"],
    "INVENTED_ANECDOTE": ["INVENTED_EXAMPLE", "INVENTED_HYPOTHETICAL"],
    "INVENTED_HYPOTHETICAL": ["INVENTED_EXAMPLE", "INVENTED_ANECDOTE"],
    "REFERENCE_COMPLETION": ["REFERENCE_EXPANSION", "QUOTE_EXPANSION"],
    "REFERENCE_EXPANSION": ["REFERENCE_COMPLETION", "QUOTE_EXPANSION"],
    "QUOTE_EXPANSION": ["REFERENCE_COMPLETION", "REFERENCE_EXPANSION"],
    "UNCERTAINTY_STRENGTHENED": ["SOURCE_MEANING_DISTORTED", "NEW_CONCLUSION"],
    "SOURCE_MEANING_DISTORTED": ["UNCERTAINTY_STRENGTHENED", "EVIDENCE_MISMATCH"],
    "EVIDENCE_MISMATCH": ["NEW_FACT", "OTHER"],
    "OTHER": ["NEW_FACT", "EVIDENCE_MISMATCH"],
}


def reason_code_catalog() -> dict[str, Any]:
    entries = []
    for code in REASON_CODES:
        entries.append(
            {
                "id": code,
                "definition": REASON_DEFINITIONS[code],
                "compatible_verdicts": list(RESERVATION_VERDICTS),
                "incompatible_verdicts": list(EMPTY_REASON_VERDICTS),
                "problem_type": PROBLEM_TYPES[code],
                "expected_evidence": EXPECTED_EVIDENCE[code],
                "generic_example": GENERIC_EXAMPLES[code],
                "confusion_risks": CONFUSION_RISKS[code],
            }
        )
    return {
        "phase": PHASE,
        "catalog_closed": True,
        "codes": list(REASON_CODES),
        "entries": entries,
        "other_is_only_fallback": True,
        "no_code_invented": True,
        "no_historical_code_removed": True,
        "observed_h02_codes_remain_outside_catalog": list(OBSERVED_H02_REASON_CODES),
        "diagnostic_candidates_are_not_aliases": {
            code: item["canonical_candidate"]
            for code, item in DIAGNOSTIC_CANDIDATES.items()
        },
        "supported_and_non_substantive_must_have_empty_reasons": True,
        "questionable_and_unsupported_require_at_least_one_catalog_code": True,
        "secrets_included": False,
    }


__all__ = [
    "CONFUSION_RISKS",
    "EMPTY_REASON_VERDICTS",
    "EXPECTED_EVIDENCE",
    "GENERIC_EXAMPLES",
    "PROBLEM_TYPES",
    "RESERVATION_VERDICTS",
    "reason_code_catalog",
]
