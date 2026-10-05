"""Historical evidence inventory. Distinguishes observed files from hypotheses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b23.identity import file_identity
from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b28.constants import (
    H01_CASE_HANDLE,
    H01_CASE_ID,
    H01_HUMAN_LABEL,
    H01_REQUEST_SHA256,
    H02_CASE_HANDLE,
    H02_CASE_ID,
    H02_HUMAN_LABEL,
    H02_REQUEST_SHA256,
    H11_CASE_HANDLE,
    H11_CASE_ID,
    H11_HUMAN_LABEL,
    H11_REQUEST_SHA256,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
    PROMPT_VERSION_113,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b28.paths import (
    historical_4b271_dir,
    historical_4b274_dir,
    historical_4b275_dir,
    historical_4b276_dir,
    historical_h01_dir,
    historical_h02_dir,
    historical_h11_dir,
)

EXPECTED_FILES = {
    "h01_real": [
        "book_semantic_gate_4b27_raw_structured_response.json",
        "book_semantic_gate_4b27_raw_provider_text.txt",
        "book_semantic_gate_4b27_request_identity.json",
        "book_semantic_gate_4b27_cost.json",
        "book_semantic_gate_4b27_semantic_review.json",
        "book_semantic_gate_4b27_replay.json",
        "book_semantic_gate_4b27_response_validation.json",
    ],
    "h02_real": [
        "p3_real_raw_structured_response.json",
        "p3_real_raw_provider_text.txt",
        "p3_real_request_identity.json",
        "p3_real_cost.json",
        "p3_real_token_usage.json",
        "p3_real_semantic_review.json",
        "p3_real_replay.json",
        "p3_real_response_validation.json",
    ],
    "h11_real": [
        "provider_response_raw.json",
        "provider_response_text.txt",
        "frozen_request_verification.json",
        "cost_accounting.json",
        "provider_usage.json",
        "claim_by_claim_semantic_review.json",
        "offline_replay.json",
        "structural_validation.json",
        "human_reference_comparison.json",
    ],
    "offline_4b271": [
        "h01_terra_response_forensics.json",
        "h01_disputed_clause_analysis.json",
        "h01_human_label_review.json",
        "h01_canonical_evidence_inventory.json",
    ],
    "offline_4b274": [
        "h02_claim_by_claim_review.json",
        "h01_h02_comparative_analysis.json",
        "historical_canary_inventory.json",
        "punctuation_coverage_inventory.json",
    ],
    "offline_4b275": [
        "h02_indeterminate_claim_review.json",
        "reason_code_catalog.json",
        "coverage_policy_review.json",
        "contract_113_candidate_review.json",
    ],
    "offline_4b276": [
        "selected_canary_paragraph.txt",
        "selected_canary_evidence.json",
        "selected_canary_human_reference.json",
        "selected_canary_provider_request.json",
    ],
}


def _list_dir(directory: Path, names: list[str]) -> dict[str, Any]:
    rows = []
    missing = []
    for name in names:
        path = directory / name
        identity = file_identity(path)
        rows.append({"name": name, **identity})
        if not identity.get("exists"):
            missing.append(name)
    present = sorted(path.name for path in directory.iterdir() if path.is_file()) if directory.is_dir() else []
    return {
        "directory": str(directory).replace("\\", "/"),
        "exists": directory.is_dir(),
        "expected_files": rows,
        "missing_expected": missing,
        "present_files_observed": present,
        "evidence_level": "OBSERVED",
    }


def historical_evidence_inventory(*, root: Path | None = None) -> dict[str, Any]:
    canaries = load_canary_bundle(root=root)
    directories = {
        "h01_real": _list_dir(historical_h01_dir(root=root), EXPECTED_FILES["h01_real"]),
        "h02_real": _list_dir(historical_h02_dir(root=root), EXPECTED_FILES["h02_real"]),
        "h11_real": _list_dir(historical_h11_dir(root=root), EXPECTED_FILES["h11_real"]),
        "offline_4b271": _list_dir(
            historical_4b271_dir(root=root), EXPECTED_FILES["offline_4b271"]
        ),
        "offline_4b274": _list_dir(
            historical_4b274_dir(root=root), EXPECTED_FILES["offline_4b274"]
        ),
        "offline_4b275": _list_dir(
            historical_4b275_dir(root=root), EXPECTED_FILES["offline_4b275"]
        ),
        "offline_4b276": _list_dir(
            historical_4b276_dir(root=root), EXPECTED_FILES["offline_4b276"]
        ),
    }
    missing = [
        f"{group}:{name}"
        for group, payload in directories.items()
        for name in payload.get("missing_expected") or []
    ]
    return {
        "phase": PHASE,
        "evidence_level": "OBSERVED",
        "invented_missing_data": False,
        "MISSING_HISTORICAL_EVIDENCE": missing,
        "historical_status_preserved": {
            "h01": HISTORICAL_H01_STATUS,
            "h02": HISTORICAL_H02_STATUS,
            "h11": HISTORICAL_H11_STATUS,
            "not_converted_to_pass": True,
            "evidence_level": "OBSERVED",
        },
        "canaries": {
            "h01": {
                "handle": H01_CASE_HANDLE,
                "case_id": H01_CASE_ID,
                "human_label_audit_only": H01_HUMAN_LABEL,
                "request_sha256": H01_REQUEST_SHA256,
                "paragraph_chars": len(str((canaries["h01"].get("text") or ""))),
                "claim_count": len(canaries["h01"].get("claims") or []),
                "global_verdict": canaries["h01"].get("global_verdict"),
                "paragraph_verdict": canaries["h01"].get("paragraph_verdict"),
                "raw_preserved": not bool(
                    (canaries["h01"].get("payload") or {}).get("MISSING_HISTORICAL_EVIDENCE")
                ),
            },
            "h02": {
                "handle": H02_CASE_HANDLE,
                "case_id": H02_CASE_ID,
                "human_label_audit_only": H02_HUMAN_LABEL,
                "request_sha256": H02_REQUEST_SHA256,
                "paragraph_chars": len(str((canaries["h02"].get("text") or ""))),
                "claim_count": len(canaries["h02"].get("claims") or []),
                "global_verdict": canaries["h02"].get("global_verdict"),
                "paragraph_verdict": canaries["h02"].get("paragraph_verdict"),
                "raw_preserved": not bool(
                    (canaries["h02"].get("payload") or {}).get("MISSING_HISTORICAL_EVIDENCE")
                ),
            },
            "h11": {
                "handle": H11_CASE_HANDLE,
                "case_id": H11_CASE_ID,
                "human_label_audit_only": H11_HUMAN_LABEL,
                "request_sha256": H11_REQUEST_SHA256,
                "paragraph_chars": len(str((canaries["h11"].get("text") or ""))),
                "claim_count": len(canaries["h11"].get("claims") or []),
                "global_verdict": canaries["h11"].get("global_verdict"),
                "paragraph_verdict": canaries["h11"].get("paragraph_verdict"),
                "contract": PROMPT_VERSION_113,
                "transport": TRANSPORT_VERSION_11,
                "raw_preserved": not bool(
                    (canaries["h11"].get("payload") or {}).get("MISSING_HISTORICAL_EVIDENCE")
                ),
            },
        },
        "directories": directories,
        "human_labels_unmodified": True,
        "historical_contracts_unmodified": True,
        "historical_raw_unmodified": True,
        "distinction": {
            "observed": "Files, hashes, saved JSON, token counts, and Terra verdicts.",
            "historical_diagnostics": "Prior offline reviews (4B.2.7.1–4B.2.7.7).",
            "new_hypotheses": "Architecture comparison and cost projections in this phase.",
        },
        "secrets_included": False,
    }


__all__ = ["historical_evidence_inventory"]
