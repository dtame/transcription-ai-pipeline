"""H02 indeterminate claim review. Does not rewrite the historical human label."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b261.candidates import recover_claim_text
from app.book_semantic_gate_4b272.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b272.identity import load_p3_gate_paragraph
from app.book_semantic_gate_4b274.claims import load_saved_h02_payload, review_h02_claims
from app.book_semantic_gate_4b275.constants import (
    H02_CASE_HANDLE,
    H02_HUMAN_LABEL,
    H02_INDETERMINATE_CLAIM,
    H02_INDETERMINATE_END,
    H02_INDETERMINATE_INDEX,
    H02_INDETERMINATE_START,
    HUMAN_REVIEW_INDETERMINATE,
    P3_EVIDENCE_HANDLES,
    PHASE,
)


def review_h02_indeterminate_claim(*, root: Path | None = None) -> dict[str, Any]:
    inventory = build_canonical_evidence_inventory(root=root)
    paragraph = load_p3_gate_paragraph(root=root)
    text = str(paragraph.get("text") or "")
    payload = load_saved_h02_payload(root=root)
    historical = review_h02_claims(root=root)
    claim_row = next(
        item
        for item in (historical.get("claims") or [])
        if item.get("index") == H02_INDETERMINATE_INDEX
    )
    recovered = recover_claim_text(text, H02_INDETERMINATE_START, H02_INDETERMINATE_END)
    preceding = text[max(0, H02_INDETERMINATE_START - 80) : H02_INDETERMINATE_START]
    following = text[H02_INDETERMINATE_END : H02_INDETERMINATE_END + 80]
    authorized = {}
    for row in (inventory.get("ideas") or []) + (inventory.get("src") or []):
        handle = str(row.get("id") or "")
        if handle in P3_EVIDENCE_HANDLES:
            authorized[handle] = str(row.get("exact_text") or "")
    cited = list(claim_row.get("cited_evidence") or [])
    uncited = {
        handle: authorized[handle]
        for handle in P3_EVIDENCE_HANDLES
        if handle not in cited and handle in authorized
    }
    axes = {
        "factual_assertion": {
            "present": "PARTIAL_PRESUPPOSITION",
            "finding": (
                "The sentence does not name an origin. It presupposes that the "
                "abuse has an origin and that naming it is worthwhile. That "
                "presupposition is weaker than an explicit origin attribution."
            ),
        },
        "rhetorical_function": {
            "role": "EDITORIAL_BRIDGE",
            "finding": (
                "The sentence introduces the following attested material about "
                "the devil and an old strategy. It functions as a discourse "
                "frame, not as the causal clause under dispute."
            ),
        },
        "origin_attribution": {
            "assigns_a_named_origin": False,
            "finding": (
                "The clause does not say who or what the origin is. Combined "
                "with the next sentence, a reader may take it as origin-framing. "
                "'Comes from' is not identical to 'has used it'."
            ),
        },
        "neighboring_propositions": {
            "next_sentence_starts": "The devil has used it since the beginning",
            "finding": (
                "The following proposition is independently reviewed. This "
                "framing sentence points at that content without restating it."
            ),
        },
        "evidence_justification": {
            "cited": cited,
            "uncited_authorized": uncited,
            "explicitly_supported": False,
            "semantically_entailed": False,
            "finding": (
                "SRC006155+SRC006156 and IDEA225 support the devil as user of "
                "an old strategy. They do not attest an editorial evaluation "
                "that naming the origin is worthwhile, and they do not strictly "
                "entail an origin claim."
            ),
        },
    }
    excluded = {
        "SUPPORTED": (
            "The evaluation and origin frame are not strictly entailed."
        ),
        "UNSUPPORTED": (
            "The sentence does not invent a specific origin or a new causal "
            "mechanism. Treating a discourse frame as a fabricated fact would "
            "over-read the text."
        ),
        "NON_SUBSTANTIVE": (
            "The sentence carries an evaluation and an origin presupposition. "
            "An editorial transition is not automatically non-substantive."
        ),
        "QUESTIONABLE": (
            "Terra's conservative reservation is compatible with production "
            "blocking, but the authorized evidence does not uniquely force "
            "that class over remaining uncertainty."
        ),
    }
    return {
        "phase": PHASE,
        "handle": H02_CASE_HANDLE,
        "human_label_unmodified": True,
        "human_label_historical": H02_HUMAN_LABEL,
        "historical_h02_not_pass": True,
        "exact_text": recovered,
        "expected_text": H02_INDETERMINATE_CLAIM,
        "text_match": recovered == H02_INDETERMINATE_CLAIM,
        "offsets": {
            "start": H02_INDETERMINATE_START,
            "end": H02_INDETERMINATE_END,
            "interval": "half_open",
            "python_slice": f"text[{H02_INDETERMINATE_START}:{H02_INDETERMINATE_END}]",
        },
        "index": H02_INDETERMINATE_INDEX,
        "paragraph_exact_text": text,
        "preceding_context": preceding,
        "following_context": following,
        "terra_verdict": claim_row.get("terra_verdict"),
        "terra_reason_codes": claim_row.get("terra_reason_codes"),
        "terra_reason_in_catalog": claim_row.get("terra_reason_in_catalog"),
        "cited_evidence": cited,
        "cited_evidence_texts": claim_row.get("cited_evidence_texts"),
        "uncited_authorized_evidence": uncited,
        "authorized_handles": list(P3_EVIDENCE_HANDLES),
        "analysis_4b274": {
            "offline_category": claim_row.get("offline_category"),
            "disagreement_conclusion": claim_row.get("disagreement_conclusion"),
            "rationale": claim_row.get("rationale"),
        },
        "five_axis_review": axes,
        "forced_conclusions_rejected": excluded,
        "human_review_conclusion": HUMAN_REVIEW_INDETERMINATE,
        "conclusion_is_not_a_provider_verdict": True,
        "conclusion_forced": False,
        "uncertainty_preserved": True,
        "payload_unmodified": isinstance(payload, dict),
        "secrets_included": False,
    }


__all__ = ["review_h02_indeterminate_claim"]
