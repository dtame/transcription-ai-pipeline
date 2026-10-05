"""Offline semantic analyses for h01. No provider calls. No label mutation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b261.candidates import recover_claim_text
from app.book_semantic_gate_4b262.contract import validate_compact_payload
from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b271.constants import (
    DISPUTED_CLAIM_INDEX,
    DISPUTED_CLAUSE,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SEMANTIC_FINDING,
    SEMANTIC_FINDING_CODE,
)
from app.book_semantic_gate_4b271.coverage import analyze_terra_h01_gaps
from app.book_semantic_gate_4b271.evidence import (
    build_canonical_evidence_inventory,
    load_saved_terra_payload,
)

EXPLICIT = "EXPLICITLY_SUPPORTED"
ENTAILED = "SEMANTICALLY_ENTAILED"
PLAUSIBLE = "PLAUSIBLE_BUT_NOT_ENTAILED"
UNSUPPORTED = "UNSUPPORTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


def _supplied_blob(inventory: Mapping[str, Any]) -> str:
    parts = [str(((inventory.get("ideas") or [{}])[0]).get("exact_text") or "")]
    for row in inventory.get("src") or []:
        parts.append(str(row.get("exact_text") or ""))
    return "\n".join(parts)


def analyze_disputed_clause(
    inventory: Mapping[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    inventory = inventory or build_canonical_evidence_inventory(root=root)
    paragraph = str(((inventory.get("paragraph") or {}).get("exact_text")) or "")
    idea_text = str(((inventory.get("ideas") or [{}])[0]).get("exact_text") or "")
    src_texts = {
        str(row.get("id")): str(row.get("exact_text") or "")
        for row in inventory.get("src") or []
    }
    supplied = _supplied_blob(inventory)
    bargain_present = "bargain" in supplied.lower()
    calculate_present = "calculat" in supplied.lower()
    no_set_time = "no set time" in idea_text.lower()
    components = {
        "fear": {
            "classification": EXPLICIT,
            "evidence": ["SRC006149", "IDEA224", "SRC006180"],
            "rationale": (
                "SRC006149: 'Don't ever be afraid of death.' IDEA224: "
                "believers should not fear death. SRC006180: 'But you can "
                "see fear'."
            ),
        },
        "calculate": {
            "classification": ENTAILED,
            "evidence": ["IDEA224"],
            "rationale": (
                "IDEA224 states there is no set time. A time that is not set "
                "cannot be calculated. The paragraph does not add a new "
                "computational event; it restates the unavailability of an "
                "appointed hour."
            ),
        },
        "bargain with": {
            "classification": ENTAILED,
            "evidence": ["IDEA224"],
            "lexical_present_in_supplied_evidence": bargain_present,
            "rationale": (
                "No supplied SRC or IDEA sentence contains bargain, "
                "negotiate, or deal. In the full clause the verb does not "
                "assert that fear actually bargains. It characterizes the "
                "absent appointed hour as something fear has no hold on. "
                "That is a stylistic co-predicate of the attested absence "
                "'no set time', not a new negotiation event, causal link, "
                "example, or completed reference."
            ),
            "alternative_considered": {
                "classification": PLAUSIBLE,
                "why_rejected_as_primary": (
                    "Treating bargain as a distinct agency claim would "
                    "convert a lexical gap into a new fact. The contract "
                    "already forbids keyword matching as the final judgment "
                    "and allows paraphrase of attested meaning."
                ),
            },
        },
        "relation": {
            "classification": ENTAILED,
            "rationale": (
                "Fear is personified as the would-be calculator/bargainer "
                "of an hour that is not appointed. The architectural rule "
                "is high stylistic freedom and low semantic freedom. The "
                "personification does not introduce a new cause or example."
            ),
        },
        "full_clause": {
            "text_user": DISPUTED_CLAUSE,
            "text_in_paragraph": "that fear can calculate or bargain with,",
            "classification": ENTAILED,
            "offsets_in_terra_claim": {"s": 65, "e": 105},
            "recovered_if_offsets_applied": paragraph[65:105] if len(paragraph) >= 105 else "",
        },
    }
    return {
        "phase": PHASE,
        "clause": DISPUTED_CLAUSE,
        "paragraph_context": paragraph,
        "supplied_evidence_texts": {
            "IDEA224": idea_text,
            **src_texts,
        },
        "lexical_scan": {
            "bargain_or_negotiate_or_deal_in_supplied_text": bargain_present,
            "calculate_in_supplied_text": calculate_present,
            "no_set_time_in_IDEA224": no_set_time,
            "lexical_absence_is_not_invention": True,
            "thematic_proximity_is_not_proof": True,
        },
        "bargain_with_senses_in_this_sentence": {
            "negotiate_with": "possible dictionary sense; not an attested event",
            "seek_an_arrangement_with": "possible dictionary sense; not an attested event",
            "haggle_with": "possible dictionary sense; not an attested event",
            "relevant_in_clause": (
                "The clause says there is no appointed hour available to "
                "fear's management. The verbs name modes of management that "
                "have no object because the hour is not set."
            ),
        },
        "components": components,
        "neighboring_SRC006186_not_in_request": {
            "id": "SRC006186",
            "text": "There is no time set.",
            "used_to_justify_terra_or_complete_evidence": False,
            "note": (
                "Canonical neighbor of SRC006183/SRC006187. Terra did not "
                "receive it. IDEA224.summary already carries 'no set time', "
                "so the no-set-time claim is inside the supplied evidence."
            ),
        },
        "external_knowledge_used": False,
        "finding_code": SEMANTIC_FINDING_CODE,
        "finding": SEMANTIC_FINDING,
        "secrets_included": False,
    }


def review_human_label(
    inventory: Mapping[str, Any] | None = None,
    clause: Mapping[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    inventory = inventory or build_canonical_evidence_inventory(root=root)
    clause = clause or analyze_disputed_clause(inventory, root=root)
    paragraph = str(((inventory.get("paragraph") or {}).get("exact_text")) or "")
    independent = {
        "Do not ever be afraid of death.": {
            "class": EXPLICIT,
            "evidence": ["SRC006149", "IDEA224"],
        },
        "There is no fixed hour appointed": {
            "class": ENTAILED,
            "evidence": ["IDEA224"],
            "note": "Paraphrase of 'there is no set time'.",
        },
        DISPUTED_CLAUSE: {
            "class": ENTAILED,
            "evidence": ["IDEA224"],
        },
        "and so fear itself is out of place": {
            "class": ENTAILED,
            "evidence": ["IDEA224", "SRC006149", "SRC006182"],
            "note": (
                "Consequence of the prohibition and of fear being not normal. "
                "Not a new causal mechanism."
            ),
        },
        "If somebody has gone to heaven,": {
            "class": EXPLICIT,
            "evidence": ["SRC006187"],
        },
        "that should not produce dread in us": {
            "class": ENTAILED,
            "evidence": ["IDEA224"],
        },
        "It should be our joy.": {
            "class": EXPLICIT,
            "evidence": ["SRC006183", "IDEA224"],
        },
    }
    return {
        "phase": PHASE,
        "historical_verdict": SELECTED_CASE_HUMAN_LABEL,
        "historical_verdict_unmodified": True,
        "benchmark_unmodified": True,
        "terra_verdict_is_not_ground_truth": True,
        "independent_evidence_result": "PARAGRAPH_SUPPORTED_BY_CANONICAL_EVIDENCE",
        "uncertainty": (
            "bargain is not lexically present. Support is entailment of the "
            "attested absence of a set time, not a quoted verb."
        ),
        "HUMAN_LABEL_REVIEW_RECOMMENDED": False,
        "why_not_recommended": (
            "The assigned IDEA224 summary and SRC set support the paragraph. "
            "The disputed clause does not invent an example, add a causal "
            "mechanism, or complete a partial reference."
        ),
        "clause_analysis_finding": clause.get("finding"),
        "paragraph": paragraph,
        "sentence_review": independent,
        "human_4b22_notes_preserved": [
            "Direct written transformation of IDEA224 and its SRC set.",
            "No-set-time claim is in the IDEA summary; remaining clauses match SRC006149/183/187.",
        ],
        "secrets_included": False,
    }


def review_src006180(
    inventory: Mapping[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    inventory = inventory or build_canonical_evidence_inventory(root=root)
    row = next(
        item for item in inventory.get("src") or [] if item.get("id") == "SRC006180"
    )
    terra = load_saved_terra_payload(root=root)
    cited: list[str] = []
    for para in terra.get("pr") or []:
        cited.extend(str(item) for item in (para.get("ev") or []) if item)
        for claim in para.get("c") or []:
            cited.extend(str(item) for item in (claim.get("ev") or []) if item)
    cited_set = sorted(set(cited))
    return {
        "phase": PHASE,
        "id": "SRC006180",
        "exact_text": row.get("exact_text"),
        "gate_request_text": row.get("gate_request_text"),
        "present_in_request": True,
        "cited_by_terra": "SRC006180" in cited_set,
        "terra_cited_handles": cited_set,
        "relevance_to_IDEA224": {
            "in_idea_source_refs": True,
            "role": (
                "Observes that fear is visible. IDEA224 says believers should "
                "not fear death. The SRC is contrast/setup, not the no-set-time "
                "wording."
            ),
        },
        "relevance_to_calculate": {
            "supports": False,
            "note": "No calculation wording.",
        },
        "relevance_to_bargain_with": {
            "supports": False,
            "decisive": False,
            "note": "No bargain/negotiate wording. Non-citation does not change the clause analysis.",
        },
        "relations_with_other_src": {
            "SRC006181": {
                "text": "in the eyes of some people.",
                "in_gate_request": False,
                "note": "Immediate continuation in the transcript. Not supplied to Terra.",
            },
            "SRC006182": {
                "text": "It's not normal.",
                "in_gate_request": True,
                "note": "Follows the fear observation.",
            },
        },
        "absence_from_citations": {
            "proves_non_reading": False,
            "available": True,
            "cited": False,
            "necessary_for_disputed_clause": False,
            "potentially_decisive_for_bargain": False,
            "contract_requires_exhaustive_citation": False,
            "contract_requires": (
                "Evidence handles actually used as support. Unused supplied "
                "handles need not be listed."
            ),
        },
        "local_context": row.get("local_context"),
        "secrets_included": False,
    }


def terra_response_forensics(
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    context = paragraph_context(root=root)
    text = str((context.get("paragraph_texts") or {}).get(SELECTED_CASE_HANDLE) or "")
    parsed = load_saved_terra_payload(root=root)
    para = next(
        item
        for item in parsed.get("pr") or []
        if str(item.get("h") or "") == SELECTED_CASE_HANDLE
    )
    claims = []
    for claim in para.get("c") or []:
        start = int(claim.get("s") or 0)
        end = int(claim.get("e") or 0)
        claims.append(
            {
                "i": claim.get("i"),
                "s": start,
                "e": end,
                "k": claim.get("k"),
                "ev": list(claim.get("ev") or []),
                "r": list(claim.get("r") or []),
                "n": claim.get("n") or "",
                "recovered_text": recover_claim_text(text, start, end),
                "reason_codes_valid": all(
                    code in REASON_CODES for code in (claim.get("r") or [])
                ),
            }
        )
    disputed = next(item for item in claims if item.get("i") == DISPUTED_CLAIM_INDEX)
    validation = validate_compact_payload(
        parsed,
        paragraph_texts=context["paragraph_texts"],
        required_handles=[SELECTED_CASE_HANDLE],
        paragraph_kinds=context["paragraph_kinds"],
    )
    spans = analyze_terra_h01_gaps(text, list(para.get("c") or []))
    return {
        "phase": PHASE,
        "immutable_saved_response": True,
        "chapter_verdict": parsed.get("v"),
        "paragraph_verdict": para.get("v"),
        "human_label_audit_only": SELECTED_CASE_HUMAN_LABEL,
        "claims": claims,
        "disputed_claim": disputed,
        "reservation": disputed.get("n"),
        "reason_codes_on_disputed_claim": disputed.get("r"),
        "reason_codes_missing_on_questionable": (
            disputed.get("k") == "QUESTIONABLE" and not disputed.get("r")
        ),
        "cited_evidence": list(para.get("ev") or []),
        "src006180_cited": "SRC006180" in set(para.get("ev") or []),
        "visible_justification_only": True,
        "no_hidden_chain_of_thought_attributed": True,
        "assessment": {
            "excessive_lexical_match": True,
            "requires_explicit_verb_where_paraphrase_allowed": True,
            "detects_real_addition": False,
            "misses_multi_evidence_relation": False,
            "SRC006180_would_not_have_supplied_bargain": True,
            "confidence_field_absent_as_designed": True,
            "reservation_is_undecidable_from_visible_text": False,
            "reservation_visible": "Calculation is implied, but bargaining is not supplied.",
        },
        "compact_1_1_already_said": [
            "Paraphrase is allowed. Judge semantic entailment, not lexical equality.",
            "Do not rely on keyword matching as the final judgment.",
        ],
        "frozen_1_1_validation": {
            "status": validation.get("status"),
            "coverage_errors": validation.get("coverage_errors"),
            "span_errors": validation.get("span_errors"),
        },
        "span_analysis_ref": spans["finding"],
        "case_id_audit_only": SELECTED_CASE_ID,
        "secrets_included": False,
    }


def paraphrase_boundary_matrix() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "architectural_principle": "high stylistic freedom, low semantic freedom",
        "categories": {
            "A_legitimate_reformulation": {
                "criterion": (
                    "Different wording preserves attested meaning. Lexical "
                    "substitution, personification, or doublet that restates "
                    "an absence, prohibition, or unavailability."
                ),
                "evidence_needed": "The attested meaning in supplied IDEA/SRC/REF text.",
                "expected_decision": "SUPPORTED",
                "false_rejection_risk": "High if the validator requires the same verb.",
                "false_support_risk": "Low if new relations are still blocked.",
                "h01_bargain_fits": True,
            },
            "B_legitimate_synthesis": {
                "criterion": (
                    "Combine multiple supplied items without a new conclusion "
                    "beyond their joint support."
                ),
                "evidence_needed": "Each combined element present in supplied evidence.",
                "expected_decision": "SUPPORTED",
                "false_rejection_risk": "Medium if items are judged in isolation.",
                "false_support_risk": "Medium if synthesis smuggles a new inference.",
            },
            "C_new_implication": {
                "criterion": "A consequence that does not follow from the evidence.",
                "evidence_needed": "The implication itself must be attested or entailed.",
                "expected_decision": "QUESTIONABLE or UNSUPPORTED with NEW_IMPLICATION.",
                "false_rejection_risk": "Medium on close paraphrases.",
                "false_support_risk": "High if 'plausible' is treated as supported.",
                "protected_case": "CONNECTIVE / P3-adjacent implications",
            },
            "D_new_causality": {
                "criterion": "because/therefore/as a result without canonical basis.",
                "evidence_needed": "The causal relation, not merely the two facts.",
                "expected_decision": "QUESTIONABLE or UNSUPPORTED with NEW_CAUSAL_LINK.",
                "false_rejection_risk": "Low if markers are inspected without keyword worship.",
                "false_support_risk": "High if facts-in-isolation are accepted as cause.",
                "protected_case": "P3",
            },
            "E_invented_example": {
                "criterion": "Illustration, scene, or anecdote not in EX/SRC/IDEA.",
                "evidence_needed": "The example itself in canonical evidence.",
                "expected_decision": "UNSUPPORTED with INVENTED_EXAMPLE.",
                "false_rejection_risk": "Low.",
                "false_support_risk": "High if stylistic color is confused with examples.",
                "protected_case": "FUNERAL",
            },
            "F_external_completion": {
                "criterion": "Partial reference completed from model memory.",
                "evidence_needed": "Only the supplied REF/SRC remainder.",
                "expected_decision": "QUESTIONABLE or UNSUPPORTED with REFERENCE_COMPLETION.",
                "false_rejection_risk": "Low.",
                "false_support_risk": "High if identity of the reference licenses a remembered quote.",
                "protected_case": "P8",
            },
        },
        "must_not_relax": ["E_invented_example", "D_new_causality", "F_external_completion", "C_new_implication"],
        "must_not_use_rule": "Accept every plausible paraphrase.",
        "acceptable_paraphrase": "semantically grounded in supplied evidence",
        "secrets_included": False,
    }


__all__ = [
    "analyze_disputed_clause",
    "paraphrase_boundary_matrix",
    "review_human_label",
    "review_src006180",
    "terra_response_forensics",
]
