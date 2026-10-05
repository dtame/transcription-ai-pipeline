"""Map prompt 1.1, JSON transport, and validator fields. No invented names."""

from __future__ import annotations

from typing import Any

from app.book_generation.coverage import coverage_policy_dict
from app.book_generation.schema import build_book_generation_transport_schema
from app.book_generation.validator import validator_contract_dict
from app.book_scale_up_preparation_4b220.constants import (
    CONTRACT_MATRIX_VERSION,
    PHASE,
    TRANSPORT_VERSION,
    VALIDATOR_VERSION,
)
from app.book_scale_up_preparation_4b220.prompt_readiness import (
    generator_prompt_11_readiness,
)


def _paragraph_schema() -> dict[str, Any]:
    schema = build_book_generation_transport_schema()
    return dict((schema.get("$defs") or {}).get("paragraph") or {})


def _section_schema() -> dict[str, Any]:
    schema = build_book_generation_transport_schema()
    return dict((schema.get("$defs") or {}).get("section") or {})


def generation_contract_matrix() -> dict[str, Any]:
    prompt = generator_prompt_11_readiness()
    paragraph = _paragraph_schema()
    section = _section_schema()
    schema = build_book_generation_transport_schema()
    validator = validator_contract_dict()
    coverage = coverage_policy_dict()
    paragraph_required = list(paragraph.get("required") or [])
    section_required = list(section.get("required") or [])
    top_required = list(schema.get("required") or [])
    paragraph_fields = sorted((paragraph.get("properties") or {}).keys())
    rows = [
        {
            "requirement": "Couverture IDEA",
            "prompt_1_1": True,
            "prompt_notes": (
                "Content must appear in prose; justified IDEA handles go in paras[].e. "
                "These obligations are distinct."
            ),
            "json_contract_field": "paras[].e",
            "json_required": "e" in paragraph_required,
            "validator_control": (
                "idea_ids_from_paragraphs(evidence_handles/idea_refs); "
                "missing planned IDEAs = FAIL; unknown/unassigned IDEAs = FAIL"
            ),
            "status": "Compatible",
            "detects_4b217_empty_paragraph_handles": True,
        },
        {
            "requirement": "Provenance SRC",
            "prompt_1_1": True,
            "prompt_notes": "Substantive paragraphs must cite supplied evidence handles.",
            "json_contract_field": "paras[].e",
            "json_required": "e" in paragraph_required,
            "validator_control": (
                "resolve_src_for_handles; substantive paragraph without SRC = FAIL; "
                "unknown handle = FAIL"
            ),
            "status": "Compatible",
            "detects_4b217_empty_paragraph_handles": True,
        },
        {
            "requirement": "Sections",
            "prompt_1_1": True,
            "prompt_notes": "Exact supplied section order. No add/remove/merge/split.",
            "json_contract_field": "sections[].sid",
            "json_required": "sid" in section_required and "sections" in top_required,
            "validator_control": (
                "got_ids != planned_ids → missing/extra/wrong-order = FAIL"
            ),
            "status": "Compatible",
            "detects_4b217_empty_paragraph_handles": False,
        },
        {
            "requirement": "Voix narrative",
            "prompt_1_1": True,
            "prompt_notes": (
                "First person for established author testimony; second person for "
                "address; third person for other people; prudence if uncertain."
            ),
            "json_contract_field": None,
            "json_required": False,
            "validator_control": (
                "No structural voice field. Editorial/human review only. "
                "Not a semantic-equivalence proof."
            ),
            "status": "Compatible_with_editorial_gap",
            "detects_4b217_empty_paragraph_handles": False,
        },
        {
            "requirement": "Références",
            "prompt_1_1": True,
            "prompt_notes": (
                "Keep references as the source gave them. Do not complete from memory."
            ),
            "json_contract_field": "paras[].e",
            "json_required": "e" in paragraph_required,
            "validator_control": (
                "REF handles must be known and allowed. Content correctness is "
                "not semantically certified by the structural validator."
            ),
            "status": "Compatible",
            "detects_4b217_empty_paragraph_handles": False,
        },
    ]
    schema_e_optional = "e" not in paragraph_required
    return {
        "phase": PHASE,
        "matrix_version": CONTRACT_MATRIX_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "prompt_version": prompt["version"],
        "json_fields": {
            "top_level_required": top_required,
            "top_level_properties": sorted((schema.get("properties") or {}).keys()),
            "section_required": section_required,
            "section_properties": sorted((section.get("properties") or {}).keys()),
            "paragraph_required": paragraph_required,
            "paragraph_properties": paragraph_fields,
            "paragraph_kind_field": "k",
            "paragraph_text_field": "t",
            "paragraph_handle_field": "h",
            "paragraph_evidence_field": "e",
            "paragraph_uncertainty_field": "u",
            "chapter_id_assigned_locally": True,
            "section_id_field": "sid",
            "paragraph_id_assigned_at_assembly": True,
            "handle_kinds": ["SRC", "IDEA", "EX", "REF", "UNC"],
        },
        "schema_notes": {
            "paras_e_optional_in_schema": schema_e_optional,
            "paras_e_required_by_prompt_for_substantive": True,
            "paras_e_required_by_validator_for_substantive": True,
            "voice_has_no_json_field": True,
        },
        "validator_contract": validator,
        "idea_accountability": coverage,
        "rows": rows,
        "compatible": all(
            str(row["status"]).startswith("Compatible") for row in rows
        ),
        "blocking_incompatibilities": [],
        "historical_4b217_problem": (
            "11 IDEA in section metadata, zero IDEA handles in paragraph evidence."
        ),
        "historical_4b217_detection": (
            "validate_chapter_candidate reports missing planned IDEAs when "
            "paras[].e contains no IDEA handles. This is a hard stop after the "
            "first real remaining-chapter call."
        ),
        "must_not_backfill_paras_e": True,
        "structural_check_is_not_semantic_equivalence": True,
        "secrets_included": False,
    }


__all__ = ["generation_contract_matrix"]
