"""Claim-by-claim comparative forensics. Does not rewrite historical verdicts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b274.coverage import classify_uncovered_gaps_112, validate_coverage
from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b28.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    H01_DISPUTED_CLAUSE,
    H01_EVIDENCE_HANDLES,
    H01_GAPS,
    H01_HUMAN_LABEL,
    H02_EVIDENCE_HANDLES,
    H02_GAPS,
    H02_HUMAN_LABEL,
    H11_DISPUTED_CLAUSE,
    H11_EVIDENCE_HANDLES,
    H11_GAPS,
    H11_HUMAN_LABEL,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
)

H01_ANALYSES: dict[int, dict[str, Any]] = {
    0: {
        "human_label_audit_only": "SUPPORTED",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "EXPLICITLY_SUPPORTED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Direct restatement of SRC006149 'Don't ever be afraid of death.'"
        ),
    },
    1: {
        "human_label_audit_only": "SUPPORTED",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "Paraphrase of IDEA224 'no set time'.",
    },
    2: {
        "human_label_audit_only": "SUPPORTED",
        "agreement": False,
        "disagreement_type": "FALSE_REJECTION_PARAPHRASE",
        "acceptance_impact": "paragraph_QUESTIONABLE_blocks_PASS",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Human review treated 'calculate or bargain with' as stylistic "
            "restatement of IDEA224 'no set time'. Terra required the verb "
            "'bargain' in the evidence. SRC006180 was authorized, unused, and "
            "does not supply bargaining. Visible Terra note: 'Calculation is "
            "implied, but bargaining is not supplied.' No hidden chain of "
            "thought is attributed. Reason codes were empty on QUESTIONABLE."
        ),
    },
    3: {
        "human_label_audit_only": "SUPPORTED",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "Fear out of place follows no-fear / no-set-time evidence.",
    },
    4: {
        "human_label_audit_only": "SUPPORTED",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "EXPLICITLY_SUPPORTED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "SRC006187 'So if somebody has gone to heaven,'.",
    },
    5: {
        "human_label_audit_only": "SUPPORTED",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "IDEA224: going to heaven should bring joy, not fear.",
    },
    6: {
        "human_label_audit_only": "SUPPORTED",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "EXPLICITLY_SUPPORTED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "SRC006183 'It should be our joy.'",
    },
}

H02_ANALYSES: dict[int, dict[str, Any]] = {
    0: {
        "human_assessment": "justified reservation",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "contributes_to_FAIL",
        "offline_category": "UNSUPPORTED",
        "conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Authorized P3 evidence does not mention believers, visible "
            "operation of fear in that group, or abnormality."
        ),
    },
    1: {
        "human_assessment": "agree supported",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "EXPLICITLY_SUPPORTED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "SRC006152 and IDEA225 directly support 'Fear of death is an abuse'.",
    },
    2: {
        "human_assessment": "false rejection",
        "agreement": False,
        "disagreement_type": "FALSE_REJECTION_STYLISTIC_INTENSIFIER",
        "acceptance_impact": "contributes_to_FAIL",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "SRC006154 'It is an abuse to your person.' Adding 'very' is "
            "stylistic. Lexical absence of 'very' is not a new claim."
        ),
    },
    3: {
        "human_assessment": "justified reservation",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "contributes_to_FAIL",
        "offline_category": "UNSUPPORTED",
        "conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "Diminishment, made, and remade are absent from authorized evidence.",
    },
    4: {
        "human_assessment": "indeterminate",
        "agreement": None,
        "disagreement_type": "HUMANLY_INDETERMINATE",
        "acceptance_impact": "contributes_to_FAIL",
        "offline_category": "PLAUSIBLE_BUT_NOT_ENTAILED",
        "conclusion": "INDETERMINATE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Origin-framing plus 'worth naming' is a close implication of "
            "devil-use evidence, not a strict entailment. Terra's reservation "
            "is conservative rather than clearly false."
        ),
    },
    5: {
        "human_assessment": "false rejection",
        "agreement": False,
        "disagreement_type": "FALSE_REJECTION_CONTINUITY_PARAPHRASE",
        "acceptance_impact": "contributes_to_FAIL",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "'And the devil has used it since.' plus 'old strategy' supports "
            "'since the beginning' as continuity restatement. Residual "
            "specificity of 'the beginning' remains a documented limit."
        ),
    },
    6: {
        "human_assessment": "agree supported",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "EXPLICITLY_SUPPORTED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "SRC006157 'He has not changed his style.'",
    },
    7: {
        "human_assessment": "agree supported",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "EXPLICITLY_SUPPORTED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "IDEA225 'the devil's old strategy.'",
    },
    8: {
        "human_assessment": "justified reservation",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "contributes_to_FAIL",
        "offline_category": "UNSUPPORTED",
        "conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "Weaponizing death against humanity is not in authorized evidence.",
    },
    9: {
        "human_assessment": "agree supported",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "Unchanged continuation is entailed by old strategy and unchanged style.",
    },
    10: {
        "human_assessment": "justified reservation of invented causality",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "blocks_acceptance",
        "offline_category": "UNSUPPORTED",
        "conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Terra isolated offsets 406-465 and blocked the invented because-clause. "
            "Effectiveness and resistance-by-truth are new. Produced code "
            "INVENTED_CAUSAL_LINK is outside the closed catalog; matching catalog "
            "codes are NEW_CAUSAL_LINK and NEW_IMPLICATION."
        ),
    },
}

H11_ANALYSES: dict[int, dict[str, Any]] = {
    0: {
        "human_label_audit_only": "SUPPORTED",
        "family": "supported_prefix",
        "agreement": False,
        "disagreement_type": "FALSE_REJECTION_SUPPORTED_PREFIX",
        "acceptance_impact": "contributes_to_FAIL_independent_of_guarantee",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Historically accepted stylistic restatement of the mind-over-matter "
            "refusal. Terra used EVIDENCE_MISMATCH on a broader framing."
        ),
    },
    1: {
        "human_label_audit_only": "SUPPORTED",
        "family": "supported_prefix",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "EXPLICITLY_SUPPORTED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "Direct paraphrase of SRC006192.",
    },
    2: {
        "human_label_audit_only": "SUPPORTED",
        "family": "supported_prefix",
        "agreement": False,
        "disagreement_type": "FALSE_REJECTION_SUPPORTED_PREFIX",
        "acceptance_impact": "contributes_to_FAIL_independent_of_guarantee",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Editorial expansion of 'not mind over matter' without a new relation. "
            "Terra used NEW_FACT. Span also ends two characters short of 'subject'."
        ),
    },
    3: {
        "human_label_audit_only": "SUPPORTED",
        "family": "supported_prefix",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "EXPLICITLY_SUPPORTED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "Attested by IDEA226 and SRC006193.",
    },
    4: {
        "human_label_audit_only": "SUPPORTED",
        "family": "supported_prefix",
        "agreement": False,
        "disagreement_type": "FALSE_REJECTION_SUPPORTED_PREFIX",
        "acceptance_impact": "contributes_to_FAIL_independent_of_guarantee",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Paraphrase of IDEA226 lived reality vs intellectual idea. Terra used "
            "INVENTED_EXAMPLE for the sermon-setting illustration."
        ),
    },
    5: {
        "human_label_audit_only": "SUPPORTED",
        "family": "supported_prefix",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "none",
        "offline_category": "SEMANTICALLY_ENTAILED",
        "conclusion": "AGREE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": "Lived-reality restatement, historically supported.",
    },
    6: {
        "human_label_audit_only": "UNSUPPORTED",
        "family": "universal_guarantee",
        "agreement": True,
        "disagreement_type": None,
        "acceptance_impact": "blocks_acceptance",
        "offline_category": "UNSUPPORTED",
        "conclusion": "TERRA_RESERVATION_SUPPORTED_BY_EVIDENCE",
        "evidence_level": "HUMAN_ASSESSED",
        "analysis": (
            "Universal fearless-death guarantee is not entailed. NEW_CONCLUSION "
            "is an acceptable catalog neighbor, not the primary pair "
            "NEW_IMPLICATION / UNCERTAINTY_STRENGTHENED. Span is two characters "
            "short of 'death.' and starts on the last letter of 'ending'."
        ),
    },
}


def _recover(text: str, start: Any, end: Any) -> str:
    if not isinstance(start, int) or not isinstance(end, int):
        return ""
    if start < 0 or end < start or end > len(text):
        return ""
    return text[start:end]


def _reason_status(claim: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(claim.get("k") or "")
    reasons = [str(item) for item in (claim.get("r") or [])]
    unknown = [code for code in reasons if code not in REASON_CODES]
    missing = kind in {"QUESTIONABLE", "UNSUPPORTED"} and not reasons
    return {
        "codes": reasons,
        "unknown": unknown,
        "missing_on_reservation": missing,
        "in_catalog": [code for code in reasons if code in REASON_CODES],
        "evidence_level": "DETERMINISTICALLY_VERIFIED",
    }


def _row(
    *,
    canary: str,
    text: str,
    claim: Mapping[str, Any],
    analysis: Mapping[str, Any],
    authorized: Sequence[str],
) -> dict[str, Any]:
    start = claim.get("s")
    end = claim.get("e")
    recovered = _recover(text, start, end)
    reasons = _reason_status(claim)
    cited = [str(item) for item in (claim.get("ev") or [])]
    invalid = [handle for handle in cited if handle not in set(authorized)]
    unused = [handle for handle in authorized if handle not in cited]
    return {
        "canary": canary,
        "index": claim.get("i"),
        "exact_text": recovered,
        "offsets": {
            "start": start,
            "end": end,
            "interval": "half_open",
            "python_slice": f"text[{start}:{end}]",
        },
        "terra_verdict": claim.get("k"),
        "reason_codes": reasons["codes"],
        "reason_code_status": reasons,
        "evidence_handles": cited,
        "invalid_evidence_handles": invalid,
        "authorized_uncited": unused,
        "terra_note": str(claim.get("n") or ""),
        "human_label_or_assessment": analysis.get("human_label_audit_only")
        or analysis.get("human_assessment"),
        "analysis_of_evidence": analysis.get("analysis"),
        "agreement": analysis.get("agreement"),
        "disagreement_type": analysis.get("disagreement_type"),
        "acceptance_impact": analysis.get("acceptance_impact"),
        "offline_category": analysis.get("offline_category"),
        "conclusion": analysis.get("conclusion"),
        "family": analysis.get("family"),
        "evidence_level_of_terra_fields": "OBSERVED",
        "evidence_level_of_human_analysis": analysis.get("evidence_level"),
        "span_in_bounds": recovered == text[start:end]
        if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(text)
        else False,
    }


def _gap_classification(text: str, claims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    audit = validate_coverage(text, claims)
    classified = classify_uncovered_gaps_112(text, claims)
    significant = [item for item in classified if item.get("kind") == "significant"]
    admissible = [
        item
        for item in classified
        if item.get("kind") in {"whitespace", "terminator", "admissible_separator"}
    ]
    letter_gaps = [
        item
        for item in classified
        if any(char.isalnum() for char in str(item.get("text") or ""))
    ]
    return {
        "coverage_status": audit.get("status"),
        "classified_gaps": classified,
        "significant_gaps": significant,
        "admissible_gaps": admissible,
        "gaps_containing_letters_or_digits": letter_gaps,
        "contains_substantive_characters": bool(letter_gaps),
        "innocence_not_presumed": True,
        "evidence_level": "DETERMINISTICALLY_VERIFIED",
    }


def h01_claim_forensics(*, root=None) -> dict[str, Any]:
    bundle = load_canary_bundle(root=root)["h01"]
    text = str(bundle.get("text") or "")
    claims = list(bundle.get("claims") or [])
    rows = [
        _row(
            canary="h01",
            text=text,
            claim=claim,
            analysis=H01_ANALYSES.get(int(claim.get("i") or 0), {}),
            authorized=H01_EVIDENCE_HANDLES,
        )
        for claim in claims
    ]
    disputed = next((row for row in rows if row.get("index") == 2), None)
    return {
        "phase": PHASE,
        "handle": "h01",
        "historical_status": HISTORICAL_H01_STATUS,
        "not_converted_to_pass": True,
        "human_label_audit_only": H01_HUMAN_LABEL,
        "human_label_unmodified": True,
        "paragraph_exact_text": text,
        "terra_global_verdict": bundle.get("global_verdict"),
        "terra_paragraph_verdict": bundle.get("paragraph_verdict"),
        "disputed_clause": H01_DISPUTED_CLAUSE,
        "original_vs_generated": {
            "source_core": "IDEA224 no set time; SRC006149 do not fear death",
            "generated_clause": H01_DISPUTED_CLAUSE,
            "terra_interpretation_visible": (
                "Calculation is implied, but bargaining is not supplied."
            ),
            "human_interpretation": (
                "Stylistic co-predicate of the attested absence of an appointed hour."
            ),
            "no_hidden_terra_mechanism_attributed": True,
            "evidence_level": "HUMAN_ASSESSED",
        },
        "claims": rows,
        "false_rejection": disputed,
        "coverage": _gap_classification(text, claims),
        "recorded_gaps": [list(item) for item in H01_GAPS],
        "reason_codes_missing_on_questionable": True,
        "src006180_authorized_not_cited": True,
        "src006180_does_not_supply_bargain": True,
        "claim_count": len(rows),
        "secrets_included": False,
    }


def h02_claim_forensics(*, root=None) -> dict[str, Any]:
    bundle = load_canary_bundle(root=root)["h02"]
    text = str(bundle.get("text") or "")
    claims = list(bundle.get("claims") or [])
    rows = [
        _row(
            canary="h02",
            text=text,
            claim=claim,
            analysis=H02_ANALYSES.get(int(claim.get("i") or 0), {}),
            authorized=H02_EVIDENCE_HANDLES,
        )
        for claim in claims
    ]
    return {
        "phase": PHASE,
        "handle": "h02",
        "historical_status": HISTORICAL_H02_STATUS,
        "not_converted_to_pass": True,
        "human_label_audit_only": H02_HUMAN_LABEL,
        "human_label_unmodified": True,
        "paragraph_exact_text": text,
        "terra_global_verdict": bundle.get("global_verdict"),
        "terra_paragraph_verdict": bundle.get("paragraph_verdict"),
        "causal_clause": DISPUTED_CAUSAL_CLAUSE,
        "invented_causality_detected": True,
        "false_rejections": [row for row in rows if row.get("index") in {2, 5}],
        "justified_reservations": [
            row for row in rows if row.get("index") in {0, 3, 8, 10}
        ],
        "indeterminate_claim": next((row for row in rows if row.get("index") == 4), None),
        "unknown_reason_codes": sorted(
            {
                code
                for row in rows
                for code in (row.get("reason_code_status") or {}).get("unknown") or []
            }
        ),
        "claims": rows,
        "coverage": _gap_classification(text, claims),
        "recorded_gaps": [list(item) for item in H02_GAPS],
        "historical_coverage_note": (
            "4B.2.7.3 recorded significant gaps at separators under the then-"
            "current policy. 4B.2.7.4 later classified those as admissible "
            "separators. The because-clause itself was covered."
        ),
        "claim_count": len(rows),
        "false_rejection_count": 2,
        "justified_reservation_count": 4,
        "indeterminate_count": 1,
        "secrets_included": False,
    }


def h11_claim_forensics(*, root=None) -> dict[str, Any]:
    bundle = load_canary_bundle(root=root)["h11"]
    text = str(bundle.get("text") or "")
    claims = list(bundle.get("claims") or [])
    rows = [
        _row(
            canary="h11",
            text=text,
            claim=claim,
            analysis=H11_ANALYSES.get(int(claim.get("i") or 0), {}),
            authorized=H11_EVIDENCE_HANDLES,
        )
        for claim in claims
    ]
    coverage = _gap_classification(text, claims)
    gap_snippets = [
        {
            "start": item.get("start"),
            "end": item.get("end"),
            "text": item.get("text"),
            "codepoints": item.get("codepoints"),
            "kind": item.get("kind"),
            "contains_letter_or_digit": item.get("contains_letter_or_digit"),
        }
        for item in coverage.get("classified_gaps") or []
    ]
    return {
        "phase": PHASE,
        "handle": "h11",
        "historical_status": HISTORICAL_H11_STATUS,
        "not_converted_to_pass": True,
        "human_label_audit_only": H11_HUMAN_LABEL,
        "human_label_unmodified": True,
        "paragraph_exact_text": text,
        "terra_global_verdict": bundle.get("global_verdict"),
        "terra_paragraph_verdict": bundle.get("paragraph_verdict"),
        "universal_guarantee": H11_DISPUTED_CLAUSE,
        "universal_guarantee_correctly_rejected": True,
        "supported_prefix_correctly_accepted": [
            row for row in rows if row.get("index") in {1, 3, 5}
        ],
        "historically_supported_rejected": [
            row for row in rows if row.get("index") in {0, 2, 4}
        ],
        "new_conclusion_code": {
            "produced": "NEW_CONCLUSION",
            "in_closed_catalog": True,
            "primary_pair": ["NEW_IMPLICATION", "UNCERTAINTY_STRENGTHENED"],
            "acceptable_neighbor": True,
            "evidence_level": "OBSERVED",
        },
        "structural_compliance": {
            "json_parse": "PASS",
            "reason_codes_in_catalog": True,
            "span_validity": "PASS",
            "coverage": "FAIL",
            "contract_1_1_3": "FAIL",
            "evidence_level": "OBSERVED",
        },
        "coverage": coverage,
        "coverage_gap_snippets": gap_snippets,
        "coverage_gaps_classification": (
            "SUBSTANTIVE_WORD_ENDINGS_NOT_SEPARATORS"
            if coverage.get("contains_substantive_characters")
            else "SEPARATORS_ONLY"
        ),
        "coverage_innocence_not_presumed": True,
        "recorded_gaps": [list(item) for item in H11_GAPS],
        "claims": rows,
        "claim_count": len(rows),
        "supported_prefix_agreements": 3,
        "supported_prefix_disagreements": 3,
        "src006195_authorized_unused": True,
        "secrets_included": False,
    }


__all__ = [
    "h01_claim_forensics",
    "h02_claim_forensics",
    "h11_claim_forensics",
]
