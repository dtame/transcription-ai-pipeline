"""Three independent forensic streams. No historical repair."""

from __future__ import annotations

from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    _STRIPPED_KEYWORDS,
    _UNSUPPORTED_KEYWORDS,
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.book_generation.schema import build_book_generation_transport_schema
from app.book_generation.semantic_review import evidence_corpus, phrase_in_evidence
from app.book_generator_forensics_4b21.constants import (
    CONNECTIVE_CLAIM_HANDLE,
    EMPTY_PARAGRAPH_HANDLE,
    INVENTED_ILLUSTRATION_HANDLE,
    TARGET_SECTION_ID,
)


def _paras(raw_parsed: Mapping[str, Any]) -> list[dict[str, Any]]:
    sections = list((raw_parsed or {}).get("sections") or [])
    if not sections:
        return []
    return [dict(row) for row in (sections[0].get("paras") or []) if isinstance(row, dict)]


def _by_handle(raw_parsed: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("h") or ""): row for row in _paras(raw_parsed)}


def _neighbors(raw_parsed: Mapping[str, Any], handle: str) -> dict[str, Any]:
    rows = _paras(raw_parsed)
    handles = [str(row.get("h") or "") for row in rows]
    try:
        index = handles.index(handle)
    except ValueError:
        return {"previous": None, "next": None}
    previous = rows[index - 1] if index > 0 else None
    following = rows[index + 1] if index + 1 < len(rows) else None
    return {
        "previous": previous,
        "next": following,
        "index": index,
        "count": len(rows),
    }


def classify_empty_text(value: Any) -> str:
    if value is None:
        return "null"
    if not isinstance(value, str):
        return f"other:{type(value).__name__}"
    if value == "":
        return '""'
    if value.strip() == "":
        return "whitespace_only"
    return "non_empty"


def classify_evidence(value: Any) -> str:
    if value is None:
        return "null"
    if "e" not in {"e"}:
        return "missing"
    if isinstance(value, list) and value == []:
        return "[]"
    if isinstance(value, list):
        return f"list:{len(value)}"
    return f"other:{type(value).__name__}"


def empty_paragraph_forensics(
    raw_parsed: Mapping[str, Any],
    candidate: Mapping[str, Any],
    validator: Mapping[str, Any],
) -> dict[str, Any]:
    rows = _by_handle(raw_parsed)
    raw = rows.get(EMPTY_PARAGRAPH_HANDLE) or {}
    text_present = "t" in raw
    evidence_present = "e" in raw
    text_case = classify_empty_text(raw.get("t") if text_present else None)
    if not text_present:
        text_case = "missing_text_field"
    evidence_case = classify_evidence(raw.get("e")) if evidence_present else "missing"
    schema = build_book_generation_transport_schema()
    adapted = prepare_anthropic_json_schema(schema)
    audit = audit_unsupported_features(adapted)
    minlength_stripped = "minLength" in _STRIPPED_KEYWORDS
    minlength_unsupported = "minLength" in _UNSUPPORTED_KEYWORDS
    errors = list((validator or {}).get("errors") or [])
    rejected = any("empty text" in item for item in errors)
    return {
        "stream": "A_EMPTY_PARAGRAPH",
        "provider_handle": EMPTY_PARAGRAPH_HANDLE,
        "section": TARGET_SECTION_ID,
        "raw_object": raw,
        "object_shape": sorted(raw.keys()),
        "raw_text_value": raw.get("t") if text_present else None,
        "raw_evidence_handles": raw.get("e") if evidence_present else None,
        "empty_text_case": text_case,
        "empty_evidence_case": evidence_case,
        "kind": raw.get("k"),
        "neighbors": _neighbors(raw_parsed, EMPTY_PARAGRAPH_HANDLE),
        "schema_accepted_because": [
            "canonical paragraph.t is type=string with no minLength",
            "empty string is a valid JSON Schema string",
            "canonical paragraph.e is an optional array with no minItems>0",
            "required fields are only k and t, both present",
        ],
        "minlength_limitation": {
            "anthropic_structured_output_permits_minLength": False,
            "adapter_strips_minLength": minlength_stripped,
            "adapter_lists_minLength_unsupported": minlength_unsupported,
            "do_not_add_unsupported_schema_keyword": True,
            "evidence": (
                "app/ai/providers/_anthropic_schema.py "
                "_STRIPPED_KEYWORDS and _UNSUPPORTED_KEYWORDS"
            ),
        },
        "local_validator": {
            "rejected": rejected,
            "errors": errors,
            "validator_defect": "NO",
        },
        "empty_paragraph_policy": "FAIL_never_silently_drop",
        "why_not_drop": (
            "Dropping empty paragraphs would convert malformed provider "
            "output into apparently valid output and hide the contract violation."
        ),
        "candidate_text_preserved": (
            next(
                (
                    para.get("text")
                    for section in candidate.get("sections") or []
                    for para in section.get("paragraphs") or []
                    if para.get("provider_handle") == EMPTY_PARAGRAPH_HANDLE
                ),
                None,
            )
        ),
        "historical_repaired": False,
        "root_cause": [
            "SCHEMA_EXPRESSIVENESS_LIMIT",
            "PROVIDER_COMPLIANCE_FAILURE",
        ],
        "contributing": ["PROMPT_CONTRACT_WEAKNESS"],
        "not_root_cause": [
            "NORMALIZER_DEFECT",
            "VALIDATOR_DEFECT",
        ],
        "anthropic_audit_on_adapted": {
            key: list(value) for key, value in audit.items()
        },
    }


def connective_claim_forensics(
    raw_parsed: Mapping[str, Any],
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    raw = (_by_handle(raw_parsed) or {}).get(CONNECTIVE_CLAIM_HANDLE) or {}
    candidate_para = next(
        (
            para
            for section in candidate.get("sections") or []
            for para in section.get("paragraphs") or []
            if para.get("provider_handle") == CONNECTIVE_CLAIM_HANDLE
        ),
        {},
    )
    text = str(raw.get("t") or candidate_para.get("text") or "")
    declared = list(raw.get("e") or candidate_para.get("evidence_handles") or [])
    evidence_status = (
        "none" if not declared else "declared"
    )
    if not declared and "e" not in raw:
        evidence_status = "none_field_absent"
    proposition = (
        "The difference between fearful and peaceful death was not the "
        "amount of doctrine known, but the amount of Christ practiced."
    )
    corpus = evidence_corpus(evidence)
    tokens = [
        "the difference was not the amount of doctrine known",
        "amount of doctrine known",
        "amount of christ practiced",
    ]
    token_hits = {token: token in corpus for token in tokens}
    supported = any(token_hits.values()) and phrase_in_evidence(
        "the difference was not the amount of doctrine known", evidence
    )
    prompt_too_broad = True
    return {
        "stream": "B_UNSUPPORTED_CONNECTIVE_CLAIM",
        "provider_handle": CONNECTIVE_CLAIM_HANDLE,
        "section": TARGET_SECTION_ID,
        "raw_object": raw,
        "kind_label": raw.get("k"),
        "provider_self_classified_connective": raw.get("k") == "con",
        "self_classification_trusted": False,
        "exact_text": text,
        "declared_evidence_handles": declared,
        "evidence_adequacy": "none" if not declared else "apparently_valid_but_semantically_inadequate",
        "evidence_field_status": evidence_status,
        "proposition": proposition,
        "support_search_scope": [
            "IDEA summaries",
            "EX",
            "REF",
            "UNC",
            "hydrated SRC text",
        ],
        "support_token_hits": token_hits,
        "supported": bool(supported),
        "external_knowledge_used": False,
        "classification": "SUBSTANTIVE_UNSUPPORTED",
        "prompt_1_0_permits_broad_connective": prompt_too_broad,
        "prompt_1_0_already_said": (
            "kind=con need not cite evidence. They must not introduce new "
            "substantive assertions."
        ),
        "contract_problem": (
            "book-generator-1.0 named the boundary but did not constrain "
            "closers, bridges, introductions, or transitions tightly enough, "
            "and the provider treated a summarizing argument as connective."
        ),
        "applies_to": [
            "section closers",
            "chapter closers",
            "bridges",
            "introductions",
            "transitions",
        ],
        "local_semantic_validation_authoritative": True,
        "rewritten": False,
        "root_cause": [
            "PROMPT_SEMANTIC_BOUNDARY_TOO_WEAK",
            "PROVIDER_COMPLIANCE_FAILURE",
        ],
    }


def invented_illustration_forensics(
    raw_parsed: Mapping[str, Any],
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    raw = (_by_handle(raw_parsed) or {}).get(INVENTED_ILLUSTRATION_HANDLE) or {}
    candidate_para = next(
        (
            para
            for section in candidate.get("sections") or []
            for para in section.get("paragraphs") or []
            if para.get("provider_handle") == INVENTED_ILLUSTRATION_HANDLE
        ),
        {},
    )
    text = str(raw.get("t") or candidate_para.get("text") or "")
    declared = list(raw.get("e") or candidate_para.get("evidence_handles") or [])
    searches = {
        "funeral": phrase_in_evidence("funeral", evidence),
        "funerals": phrase_in_evidence("funerals", evidence),
        "verse quoted at funerals": phrase_in_evidence(
            "verse quoted at funerals", evidence
        ),
        "quoted at funerals": phrase_in_evidence("quoted at funerals", evidence),
    }
    source_supported = any(searches.values())
    return {
        "stream": "C_INVENTED_ILLUSTRATION",
        "provider_handle": INVENTED_ILLUSTRATION_HANDLE,
        "section": TARGET_SECTION_ID,
        "raw_object": raw,
        "exact_text": text,
        "declared_evidence_handles": declared,
        "illustration_phrase": "not a verse quoted at funerals",
        "search_scope": ["IDEA", "EX", "REF", "UNC", "hydrated SRC"],
        "search_hits": searches,
        "source_supported": source_supported,
        "classification": "INVENTED_EXAMPLE",
        "invented_reference": False,
        "reference_distinction": (
            "Invented illustrative scenario, not an invented scripture/reference. "
            "4B.2 recorded invented_references=0."
        ),
        "prompt_1_0_already_said": (
            "Do not invent arguments, facts, examples, anecdotes, quotations, "
            "Bible references..."
        ),
        "contract_problem": (
            "The example/illustration prohibition existed but did not explicitly "
            "forbid helpful literary illustrations added for clarity or flow."
        ),
        "stylistic_expansion_allowed": True,
        "semantic_expansion_allowed": False,
        "rewritten": False,
        "root_cause": [
            "PROMPT_SEMANTIC_BOUNDARY_TOO_WEAK",
            "PROVIDER_COMPLIANCE_FAILURE",
        ],
    }


__all__ = [
    "connective_claim_forensics",
    "empty_paragraph_forensics",
    "invented_illustration_forensics",
]
