"""H02 claim-by-claim offline semantic review. Labels are not modified."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b261.candidates import recover_claim_text
from app.book_semantic_gate_4b272.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b272.identity import clause_offsets, load_p3_gate_paragraph
from app.book_semantic_gate_4b274.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_CLAUSE_END,
    EXPECTED_CLAUSE_START,
    H02_CASE_HANDLE,
    H02_CASE_ID,
    H02_HUMAN_LABEL,
    P3_EVIDENCE_HANDLES,
    PHASE,
)
from app.book_semantic_gate_4b274.paths import historical_h02_dir
from app.book_semantic_gate_4b274.reasons import classify_reason_payload

ANALYSIS_CATEGORIES = (
    "EXPLICITLY_SUPPORTED",
    "SEMANTICALLY_ENTAILED",
    "PLAUSIBLE_BUT_NOT_ENTAILED",
    "UNSUPPORTED",
    "INSUFFICIENT_EVIDENCE",
)
DISAGREEMENT_CONCLUSIONS = (
    "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
    "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
    "HUMAN_LABEL_REVIEW_RECOMMENDED",
    "INDETERMINATE",
)


def load_saved_h02_payload(*, root: Path | None = None) -> dict[str, Any]:
    path = historical_h02_dir(root=root) / "p3_real_raw_structured_response.json"
    if not path.is_file():
        return {"MISSING_HISTORICAL_EVIDENCE": str(path).replace("\\", "/")}
    payload = json.loads(path.read_text(encoding="utf-8"))
    parsed = payload.get("parsed")
    if not isinstance(parsed, dict):
        return {"MISSING_HISTORICAL_EVIDENCE": "parsed_object"}
    return parsed


def _evidence_texts(inventory: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in inventory.get("ideas") or []:
        handle = str(row.get("id") or "")
        if handle:
            out[handle] = str(row.get("exact_text") or "")
    for row in inventory.get("src") or []:
        handle = str(row.get("id") or "")
        if handle:
            out[handle] = str(row.get("exact_text") or "")
    return out


def _combined_evidence(texts: dict[str, str]) -> str:
    return "\n".join(texts[handle] for handle in P3_EVIDENCE_HANDLES if handle in texts)


def _offline_reviews() -> dict[int, dict[str, Any]]:
    """Motivated offline conclusions. Not Terra output. Not label changes."""
    return {
        0: {
            "offline_category": "UNSUPPORTED",
            "explicitly_supported": False,
            "semantically_entailed": False,
            "adds_new_assertion": True,
            "disagreement_conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
            "rationale": (
                "Authorized P3 evidence does not mention believers, visible "
                "operation of fear in that group, or abnormality. IDEA225 "
                "attests that living is abused when death is feared. That is "
                "not the same assertion. H01 SRC006180/SRC006182 are not "
                "authorized for h02 and were not used."
            ),
        },
        1: {
            "offline_category": "EXPLICITLY_SUPPORTED",
            "explicitly_supported": True,
            "semantically_entailed": True,
            "adds_new_assertion": False,
            "disagreement_conclusion": None,
            "rationale": (
                "SRC006152 'It is an abuse' and IDEA225 'Living is abused when "
                "death is feared' directly support 'Fear of death is an abuse'."
            ),
        },
        2: {
            "offline_category": "SEMANTICALLY_ENTAILED",
            "explicitly_supported": False,
            "semantically_entailed": True,
            "adds_new_assertion": False,
            "disagreement_conclusion": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
            "rationale": (
                "SRC006154 states 'It is an abuse to your person.' The generated "
                "span adds the intensifier 'very'. High stylistic freedom permits "
                "that restatement; it does not add a new person, a new abuse, or "
                "a new relation. Lexical absence of 'very' is not a new claim. "
                "Terra's UNJUSTIFIED_STRENGTHENING over-reads a stylistic intensifier."
            ),
        },
        3: {
            "offline_category": "UNSUPPORTED",
            "explicitly_supported": False,
            "semantically_entailed": False,
            "adds_new_assertion": True,
            "disagreement_conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
            "rationale": (
                "Diminishment, being made, and being remade are absent from "
                "authorized IDEA225/SRC texts. SRC006153 'to live.' is neighboring "
                "canonical speech but is not an authorized P3 handle and was not "
                "used as support."
            ),
        },
        4: {
            "offline_category": "PLAUSIBLE_BUT_NOT_ENTAILED",
            "explicitly_supported": False,
            "semantically_entailed": False,
            "adds_new_assertion": True,
            "disagreement_conclusion": "INDETERMINATE",
            "rationale": (
                "SRC006155+SRC006156 attribute use of the abuse to the devil. "
                "The generated sentence additionally frames an origin ('where "
                "this abuse comes from') and an editorial evaluation ('worth "
                "naming'). Origin is a close implication, not a strict entailment. "
                "Terra's reservation is conservative rather than clearly false."
            ),
        },
        5: {
            "offline_category": "SEMANTICALLY_ENTAILED",
            "explicitly_supported": False,
            "semantically_entailed": True,
            "adds_new_assertion": False,
            "disagreement_conclusion": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
            "rationale": (
                "SRC006155+SRC006156 read together: 'And the devil has used it "
                "since.' IDEA225 calls it 'the devil's old strategy.' Completing "
                "the truncated spoken 'since.' as 'since the beginning' restates "
                "attested continuity of an old strategy. It is not a biblical "
                "reference completion. Residual specificity of 'the beginning' "
                "remains a documented limit, but the offline 4B.2.7.2 inventory "
                "already treated this nearby clause as supported by SRC006156."
            ),
        },
        6: {
            "offline_category": "EXPLICITLY_SUPPORTED",
            "explicitly_supported": True,
            "semantically_entailed": True,
            "adds_new_assertion": False,
            "disagreement_conclusion": None,
            "rationale": "SRC006157 is 'He has not changed his style.'",
        },
        7: {
            "offline_category": "EXPLICITLY_SUPPORTED",
            "explicitly_supported": True,
            "semantically_entailed": True,
            "adds_new_assertion": False,
            "disagreement_conclusion": None,
            "rationale": "IDEA225 attests 'the devil's old strategy.'",
        },
        8: {
            "offline_category": "UNSUPPORTED",
            "explicitly_supported": False,
            "semantically_entailed": False,
            "adds_new_assertion": True,
            "disagreement_conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
            "rationale": (
                "Weaponizing death against humanity is not in authorized evidence. "
                "Old strategy and unchanged style do not entail that first-use "
                "weaponization claim."
            ),
        },
        9: {
            "offline_category": "SEMANTICALLY_ENTAILED",
            "explicitly_supported": False,
            "semantically_entailed": True,
            "adds_new_assertion": False,
            "disagreement_conclusion": None,
            "rationale": (
                "SRC006157 'He has not changed his style' plus 'old strategy' "
                "and 'has used it since' entail present unchanged continuation. "
                "This is not the disputed because-clause."
            ),
        },
        10: {
            "offline_category": "UNSUPPORTED",
            "explicitly_supported": False,
            "semantically_entailed": False,
            "adds_new_assertion": True,
            "disagreement_conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
            "rationale": (
                "The causal clause is examined independently. Authorized evidence "
                "attests abuse, the devil as agent, use since, and unchanged style. "
                "It does not affirm or entail that the strategy is still run because "
                "it still works wherever it is not resisted by truth. Effectiveness "
                "and resistance-by-truth are new. Terra correctly isolated offsets "
                "406-465 and blocked acceptance. The produced code INVENTED_CAUSAL_LINK "
                "is outside the catalog; the matching catalog codes are NEW_CAUSAL_LINK "
                "and NEW_IMPLICATION. h02 is not a PASS."
            ),
        },
    }


def review_h02_claims(*, root: Path | None = None) -> dict[str, Any]:
    inventory = build_canonical_evidence_inventory(root=root)
    paragraph = load_p3_gate_paragraph(root=root)
    text = str(paragraph.get("text") or inventory.get("paragraph", {}).get("exact_text") or "")
    payload = load_saved_h02_payload(root=root)
    if payload.get("MISSING_HISTORICAL_EVIDENCE"):
        return {
            "phase": PHASE,
            "MISSING_HISTORICAL_EVIDENCE": payload["MISSING_HISTORICAL_EVIDENCE"],
            "historical_labels_unmodified": True,
        }
    para = next(
        item for item in payload.get("pr") or [] if item.get("h") == H02_CASE_HANDLE
    )
    evidence = _evidence_texts(inventory)
    combined = _combined_evidence(evidence)
    offsets = clause_offsets(text)
    reviews = _offline_reviews()
    claims: list[dict[str, Any]] = []
    for claim in para.get("c") or []:
        index = int(claim.get("i") or 0)
        start = int(claim.get("s") or 0)
        end = int(claim.get("e") or 0)
        recovered = recover_claim_text(text, start, end)
        cited = [str(item) for item in (claim.get("ev") or [])]
        reasons = [str(item) for item in (claim.get("r") or [])]
        verdict = str(claim.get("k") or "")
        offline = reviews[index]
        cited_texts = {handle: evidence.get(handle) for handle in cited}
        uncited_relevant = {
            handle: evidence[handle]
            for handle in P3_EVIDENCE_HANDLES
            if handle not in cited
        }
        claims.append(
            {
                "index": index,
                "exact_text": recovered,
                "offsets": {"start": start, "end": end, "interval": "half_open"},
                "terra_verdict": verdict,
                "terra_reason_codes": reasons,
                "terra_reason_in_catalog": all(code in REASON_CODES for code in reasons),
                "terra_reason_catalog_defs": [
                    REASON_DEFINITIONS[code] for code in reasons if code in REASON_CODES
                ],
                "reason_compliance": classify_reason_payload(
                    classification=verdict, reasons=reasons
                ),
                "terra_note": str(claim.get("n") or ""),
                "cited_evidence": cited,
                "cited_evidence_texts": cited_texts,
                "uncited_authorized_evidence_examined": uncited_relevant,
                "explicitly_supported": offline["explicitly_supported"],
                "semantically_entailed": offline["semantically_entailed"],
                "adds_new_assertion": offline["adds_new_assertion"],
                "offline_category": offline["offline_category"],
                "disagreement_conclusion": offline["disagreement_conclusion"],
                "rationale": offline["rationale"],
                "overlaps_causal_clause": start < EXPECTED_CLAUSE_END
                and end > EXPECTED_CLAUSE_START,
                "is_disputed_causal_clause": recovered == DISPUTED_CAUSAL_CLAUSE,
                "different_vocabulary_not_automatic_unsupported": True,
                "plausible_not_automatic_supported": True,
            }
        )
    flagged = [
        item
        for item in claims
        if item["terra_verdict"] in {"QUESTIONABLE", "UNSUPPORTED"}
        and item["disagreement_conclusion"]
    ]
    false_rejections = [
        item
        for item in flagged
        if item["disagreement_conclusion"] == "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE"
    ]
    justified = [
        item
        for item in flagged
        if item["disagreement_conclusion"] == "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE"
    ]
    indeterminate = [
        item
        for item in flagged
        if item["disagreement_conclusion"] == "INDETERMINATE"
    ]
    causal = next(item for item in claims if item["is_disputed_causal_clause"])
    return {
        "phase": PHASE,
        "handle": H02_CASE_HANDLE,
        "case_id_audit_only": H02_CASE_ID,
        "human_label_audit_only": H02_HUMAN_LABEL,
        "human_label_unmodified": True,
        "historical_h02_not_pass": True,
        "paragraph_exact_text": text,
        "authorized_handles": list(P3_EVIDENCE_HANDLES),
        "authorized_evidence_texts": evidence,
        "combined_authorized_text": combined,
        "h01_evidence_not_used": True,
        "causal_clause_offsets": offsets,
        "causal_clause_examined_independently": True,
        "claims": claims,
        "claims_reviewed": len(claims),
        "flagged_neighbor_reviews": flagged,
        "false_rejections": false_rejections,
        "justified_reservations": justified,
        "indeterminate_claims": indeterminate,
        "false_rejection_count": len(false_rejections),
        "justified_reservation_count": len(justified),
        "indeterminate_count": len(indeterminate),
        "causal_clause": {
            "text": causal["exact_text"],
            "offsets": causal["offsets"],
            "terra_verdict": causal["terra_verdict"],
            "terra_reason_codes": causal["terra_reason_codes"],
            "offline_category": causal["offline_category"],
            "correctly_isolated": causal["offsets"]["start"] == EXPECTED_CLAUSE_START
            and causal["offsets"]["end"] == EXPECTED_CLAUSE_END,
            "correctly_blocked": causal["terra_verdict"] in {"QUESTIONABLE", "UNSUPPORTED"},
            "catalog_codes_that_would_fit": ["NEW_CAUSAL_LINK", "NEW_IMPLICATION"],
            "produced_code_outside_catalog": True,
        },
        "analysis_categories": list(ANALYSIS_CATEGORIES),
        "disagreement_conclusions": list(DISAGREEMENT_CONCLUSIONS),
        "secrets_included": False,
    }


def disagreement_matrix(review: dict[str, Any] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    payload = review or review_h02_claims(root=root)
    rows = []
    for item in payload.get("claims") or []:
        terra = item["terra_verdict"]
        offline = item["offline_category"]
        supported_offline = offline in {"EXPLICITLY_SUPPORTED", "SEMANTICALLY_ENTAILED"}
        terra_flagged = terra in {"QUESTIONABLE", "UNSUPPORTED"}
        rows.append(
            {
                "index": item["index"],
                "text": item["exact_text"],
                "terra_verdict": terra,
                "offline_category": offline,
                "neighbor_disagreement": bool(terra_flagged and supported_offline),
                "conclusion": item["disagreement_conclusion"],
                "terra_reason_codes": item["terra_reason_codes"],
            }
        )
    return {
        "phase": PHASE,
        "handle": H02_CASE_HANDLE,
        "human_label_unmodified": True,
        "rows": rows,
        "false_rejections": [
            row for row in rows if row["conclusion"] == "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE"
        ],
        "justified_reservations": [
            row
            for row in rows
            if row["conclusion"] == "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE"
        ],
        "indeterminate": [
            row for row in rows if row["conclusion"] == "INDETERMINATE"
        ],
        "causal_clause_independent": True,
        "secrets_included": False,
    }


__all__ = [
    "ANALYSIS_CATEGORIES",
    "DISAGREEMENT_CONCLUSIONS",
    "disagreement_matrix",
    "load_saved_h02_payload",
    "review_h02_claims",
]
