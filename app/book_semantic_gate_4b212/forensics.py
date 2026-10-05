"""Read-only forensics of the 4B.2.11 Terra response. The file is never rewritten."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.book_semantic_gate_4b23.identity import file_identity
from app.book_semantic_gate_4b29.transport import build_transport_20_schema
from app.book_semantic_gate_4b29.validator import validate_response_20
from app.book_semantic_gate_4b210.contract import semantic_contract_201_candidate
from app.book_semantic_gate_4b211.request import paragraph_context
from app.book_semantic_gate_4b212.constants import (
    CLASSIFICATIONS,
    EXPECTED_4B211_RAW_TEXT_SHA256,
    FORBIDDEN_MODEL_FIELDS,
    H01_EVIDENCE_HANDLES,
    PHASE,
    PROMPT_VERSION_201_CANDIDATE,
    REQUIRED_UNIT_IDS,
    SELECTED_CASE_HANDLE,
    TARGET_UNIT_ID,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b212.paths import historical_raw_response_path
from app.file_utils import content_hash


def load_historical_raw(*, root: Path | None = None) -> dict[str, Any]:
    path = historical_raw_response_path(root=root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload


def real_response_forensics(*, root: Path | None = None) -> dict[str, Any]:
    path = historical_raw_response_path(root=root)
    saved = load_historical_raw(root=root)
    identity = file_identity(path)
    text = str(saved.get("text") or "")
    parsed = saved.get("parsed") if isinstance(saved.get("parsed"), Mapping) else {}
    text_sha = content_hash(text) if text else ""
    units = []
    for para in parsed.get("pr") or []:
        for row in para.get("u") or []:
            units.append(
                {
                    "id": row.get("id"),
                    "k_received": row.get("k"),
                    "ev_received": list(row.get("ev") or []),
                    "r_received": list(row.get("r") or []),
                    "n_received": row.get("n") if "n" in row else None,
                    "n_omitted": "n" not in row,
                }
            )
    fields_received = sorted(parsed.keys()) if isinstance(parsed, Mapping) else []
    paragraph = (parsed.get("pr") or [{}])[0] if isinstance(parsed, Mapping) else {}
    return {
        "phase": PHASE,
        "source_file": identity,
        "immutable": True,
        "manually_edited": False,
        "repaired": False,
        "text_sha256": text_sha,
        "expected_text_sha256": EXPECTED_4B211_RAW_TEXT_SHA256,
        "text_sha256_match": text_sha == EXPECTED_4B211_RAW_TEXT_SHA256,
        "finish_reason": saved.get("finish_reason"),
        "truncated": saved.get("truncated"),
        "returned_model": saved.get("returned_model"),
        "fields_received": fields_received,
        "fields_expected_by_201": ["ch", "v", "pr", "sc", "uh", "rr"],
        "values_received": {
            "ch": parsed.get("ch"),
            "v": parsed.get("v"),
            "pr[0].h": paragraph.get("h"),
            "pr[0].v": paragraph.get("v"),
            "sc": parsed.get("sc"),
            "uh": parsed.get("uh"),
            "rr": parsed.get("rr"),
            "units": units,
        },
        "values_expected_by_201": {
            "ch": "CH016",
            "v": "PASS | REVIEW | FAIL",
            "pr[0].h": SELECTED_CASE_HANDLE,
            "pr[0].v": "SUPPORTED | QUESTIONABLE | UNSUPPORTED | NON_SUBSTANTIVE",
            "sc_keys": ["supported", "questionable", "unsupported", "non_substantive"],
            "unit.k": list(CLASSIFICATIONS),
            "unit.id": list(REQUIRED_UNIT_IDS),
        },
        "units_concerned": list(REQUIRED_UNIT_IDS),
        "target_unit": TARGET_UNIT_ID,
        "semantic_elements_correct": {
            "all_five_units_present": [row.get("id") for row in units] == list(REQUIRED_UNIT_IDS),
            "all_k_supported": all(row.get("k_received") == "SUPPORTED" for row in units),
            "target_paraphrase_supported": any(
                row.get("id") == TARGET_UNIT_ID and row.get("k_received") == "SUPPORTED"
                for row in units
            ),
            "evidence_handles_from_supplied_set": all(
                handle in H01_EVIDENCE_HANDLES
                for row in units
                for handle in row.get("ev_received") or []
            ),
            "reason_codes_empty_for_supported": all(row.get("r_received") == [] for row in units),
        },
        "contract_violations": [
            {
                "id": "anomaly_a_sc_uppercase_keys",
                "path": "sc",
                "received": list((parsed.get("sc") or {}).keys()),
                "expected": ["supported", "questionable", "unsupported", "non_substantive"],
            },
            {
                "id": "anomaly_b_paragraph_v_pass",
                "path": "pr[0].v",
                "received": paragraph.get("v"),
                "expected": list(CLASSIFICATIONS),
            },
        ],
        "indeterminate": [
            "Whether Terra would emit lowercase sc keys if an example JSON were supplied.",
            "Whether Terra would classify h02/h11 correctly. Those cases were not replayed remotely.",
            "Whether json_schema strict mode would have prevented the two anomalies. Remote compatibility is UNVERIFIED.",
        ],
        "historical_canary_not_declared_pass": True,
        "secrets_included": False,
    }


def schema_mismatch_analysis(*, root: Path | None = None) -> dict[str, Any]:
    saved = load_historical_raw(root=root)
    parsed = saved.get("parsed") if isinstance(saved.get("parsed"), Mapping) else {}
    contract = semantic_contract_201_candidate()
    instructions = str(contract.get("instructions_candidate") or "")
    system = str(contract.get("system_candidate") or "")
    schema = build_transport_20_schema()
    sc_schema = ((schema.get("$defs") or {}).get("counts") or {}).get("properties") or {}
    paragraph_v = (
        ((schema.get("$defs") or {}).get("paragraph") or {})
        .get("properties", {})
        .get("v", {})
    )
    context = paragraph_context(root=root)
    prepared = dict(context.get("prepared") or {})
    validation = validate_response_20(
        parsed,
        prepared,
        allowed_evidence=list(H01_EVIDENCE_HANDLES),
        expected_chapter="CH016",
    )
    sc_keys_in_instructions = "supported" in instructions and "sc = counts of k values" in instructions
    example_json_in_prompt = "\"sc\"" in instructions and "\"supported\":" in instructions
    paragraph_v_defined_as_classification = (
        "paragraph" in instructions.lower()
        and "SUPPORTED | QUESTIONABLE | UNSUPPORTED | NON_SUBSTANTIVE" in instructions
        and "pr[] = paragraph results with h, v" in instructions
    )
    return {
        "phase": PHASE,
        "contract_analyzed": PROMPT_VERSION_201_CANDIDATE,
        "transport_analyzed": TRANSPORT_VERSION_20_CANDIDATE,
        "historical_response_unmodified": True,
        "validator_unmodified_for_this_analysis": True,
        "anomaly_a": {
            "id": "sc_uppercase_keys",
            "sc_is_count_dictionary": True,
            "expected_keys_are_lowercase_count_labels": True,
            "expected_keys_are_not_the_k_verdicts": True,
            "k_verdicts_are_uppercase": list(CLASSIFICATIONS),
            "contract_states_sc_case_explicitly": False,
            "instructions_text": "sc = counts of k values",
            "schema_keys": sorted(sc_schema.keys()),
            "schema_requires_lowercase": sorted(sc_schema.keys())
            == ["non_substantive", "questionable", "supported", "unsupported"],
            "example_json_in_prompt": example_json_in_prompt,
            "example_coherent_with_schema": False,
            "validator_rejects_uppercase_as_unexpected_fields": True,
            "validator_imposes_undocumented_case": True,
            "root_cause": (
                "The 2.0.1 instructions tell the model to emit counts of k values. "
                "k values are uppercase classifications. The JSON schema and "
                "validator require lowercase keys supported/questionable/"
                "unsupported/non_substantive, but neither the system prompt nor "
                "the instructions state that case, and no example JSON is given. "
                "Terra used the classification names as keys. This is a contract "
                "ambiguity, not a silent-validator bug and not a semantic error."
            ),
            "silent_normalization_applied": False,
        },
        "anomaly_b": {
            "id": "paragraph_v_pass",
            "received": (parsed.get("pr") or [{}])[0].get("v"),
            "unit_k_documented": "SUPPORTED | QUESTIONABLE | UNSUPPORTED | NON_SUBSTANTIVE",
            "top_level_v_documented": "PASS, REVIEW, or FAIL",
            "paragraph_v_documented_as_classification": paragraph_v_defined_as_classification,
            "paragraph_v_schema_enum": paragraph_v.get("enum"),
            "paragraph_v_schema_description": paragraph_v.get("description"),
            "example_uses_pass_at_paragraph": False,
            "instructions_mix_semantic_and_operational": True,
            "field_documentation_insufficient": True,
            "root_cause": (
                "Instructions define unit k as a semantic classification and "
                "top-level v as PASS/REVIEW/FAIL. Paragraph results are described "
                "only as 'pr[] = paragraph results with h, v, and unit rows u[]'. "
                "The schema expects paragraph v to be a classification. Terra "
                "copied the operational top-level PASS onto pr[0].v. This is "
                "instruction/schema mixing, not a semantic misclassification of u01."
            ),
            "silent_pass_to_supported_applied": False,
        },
        "historical_validation_errors": validation.get("errors") or [],
        "historical_contract_ok": bool(validation.get("ok")),
        "forbidden_model_fields_in_202": list(FORBIDDEN_MODEL_FIELDS),
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "sc_keys_named_lowercase_in_instructions": sc_keys_in_instructions,
        "secrets_included": False,
    }


__all__ = [
    "load_historical_raw",
    "real_response_forensics",
    "schema_mismatch_analysis",
]
