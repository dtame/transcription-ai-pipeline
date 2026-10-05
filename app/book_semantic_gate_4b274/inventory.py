"""Historical h01/h02 evidence inventory. Read-only. No reconstruction of raw JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b23.identity import file_identity, verify_canonical_inputs
from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b271.evidence import load_saved_terra_payload as load_h01_payload
from app.book_semantic_gate_4b272.identity import load_p3_gate_paragraph
from app.book_semantic_gate_4b274.claims import load_saved_h02_payload
from app.book_semantic_gate_4b274.constants import (
    H01_CASE_HANDLE,
    H01_CASE_ID,
    H01_CONTRACT,
    H01_COST_USD,
    H01_HUMAN_LABEL,
    H01_MODEL,
    H01_REQUEST_SHA256,
    H02_CASE_HANDLE,
    H02_CASE_ID,
    H02_CONTRACT,
    H02_COST_USD,
    H02_HUMAN_LABEL,
    H02_MODEL,
    H02_REQUEST_SHA256,
    PHASE,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b274.paths import (
    historical_4b271_dir,
    historical_4b272_dir,
    historical_h01_dir,
    historical_h02_dir,
)
from app.file_utils import content_hash


def _file_row(path: Path) -> dict[str, Any]:
    meta = file_identity(path)
    meta["required"] = True
    if not meta["exists"]:
        meta["MISSING_HISTORICAL_EVIDENCE"] = True
    return meta


def _json_identity(path: Path) -> dict[str, Any]:
    row = _file_row(path)
    if not row["exists"]:
        return row
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        row["MISSING_HISTORICAL_EVIDENCE"] = "invalid_json"
        return row
    row["canonical_sha256"] = content_hash(
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    return row


def _dir_inventory(directory: Path, names: tuple[str, ...]) -> dict[str, Any]:
    files = {name: _json_identity(directory / name) for name in names if name.endswith(".json")}
    for name in names:
        if not name.endswith(".json"):
            files[name] = _file_row(directory / name)
    missing = [
        name
        for name, row in files.items()
        if not row.get("exists") or row.get("MISSING_HISTORICAL_EVIDENCE")
    ]
    return {
        "directory": str(directory).replace("\\", "/"),
        "files": files,
        "missing": missing,
        "complete": not missing,
    }


def historical_canary_inventory(*, root: Path | None = None) -> dict[str, Any]:
    identities = verify_canonical_inputs(root=root)
    h01_dir = historical_h01_dir(root=root)
    h02_dir = historical_h02_dir(root=root)
    h01_files = (
        "book_semantic_gate_4b27_raw_structured_response.json",
        "book_semantic_gate_4b27_raw_provider_text.txt",
        "book_semantic_gate_4b27_request_identity.json",
        "book_semantic_gate_4b27_response_validation.json",
        "book_semantic_gate_4b27_semantic_review.json",
        "book_semantic_gate_4b27_replay.json",
        "book_semantic_gate_4b27_cost.json",
        "book_semantic_gate_4b27_token_usage.json",
        "book_semantic_gate_4b27_provider_evidence.json",
        "book_semantic_gate_4b27_precall.json",
    )
    h02_files = (
        "p3_real_raw_structured_response.json",
        "p3_real_raw_provider_text.txt",
        "p3_real_request_identity.json",
        "p3_real_response_validation.json",
        "p3_real_semantic_review.json",
        "p3_real_replay.json",
        "p3_real_cost.json",
        "p3_real_token_usage.json",
        "p3_real_provider_evidence.json",
        "p3_real_precall.json",
    )
    h01_payload = load_h01_payload(root=root)
    h02_payload = load_saved_h02_payload(root=root)
    reconstructed = False
    missing: list[str] = []
    if not isinstance(h01_payload, dict) or "pr" not in h01_payload:
        missing.append("h01_parsed_response")
    if h02_payload.get("MISSING_HISTORICAL_EVIDENCE"):
        missing.append(str(h02_payload["MISSING_HISTORICAL_EVIDENCE"]))
    h01_context = paragraph_context(root=root)
    h01_text = str((h01_context.get("paragraph_texts") or {}).get(H01_CASE_HANDLE) or "")
    h02_para = load_p3_gate_paragraph(root=root)
    h02_text = str(h02_para.get("text") or "")
    h01_request = _json_identity(h01_dir / "book_semantic_gate_4b27_request_identity.json")
    h02_request = _json_identity(h02_dir / "p3_real_request_identity.json")
    h01_req_hash = None
    h02_req_hash = None
    if h01_request.get("exists"):
        h01_req_obj = json.loads(
            (h01_dir / "book_semantic_gate_4b27_request_identity.json").read_text(encoding="utf-8")
        )
        h01_req_hash = h01_req_obj.get("request_sha256") or h01_req_obj.get("sha256")
    if h02_request.get("exists"):
        h02_req_obj = json.loads(
            (h02_dir / "p3_real_request_identity.json").read_text(encoding="utf-8")
        )
        h02_req_hash = h02_req_obj.get("request_sha256") or h02_req_obj.get("sha256")
    h01_bundle = _dir_inventory(h01_dir, h01_files)
    h02_bundle = _dir_inventory(h02_dir, h02_files)
    h271 = historical_4b271_dir(root=root)
    h272 = historical_4b272_dir(root=root)
    return {
        "phase": PHASE,
        "canonical_inputs": {
            "source_map": identities["source_map"]["sha256"],
            "editorial_plan": identities["editorial_plan"]["sha256"],
            "clean_transcript": identities["clean_transcript"]["sha256"],
        },
        "h01": {
            "handle": H01_CASE_HANDLE,
            "case_id_audit_only": H01_CASE_ID,
            "model": H01_MODEL,
            "contract": H01_CONTRACT,
            "transport": TRANSPORT_VERSION_11,
            "request_sha256_expected": H01_REQUEST_SHA256,
            "request_sha256_recorded": h01_req_hash,
            "request_sha256_match": h01_req_hash == H01_REQUEST_SHA256,
            "human_label_audit_only": H01_HUMAN_LABEL,
            "historical_status": "PARTIAL",
            "cost_usd": H01_COST_USD,
            "paragraph_chars": len(h01_text),
            "raw_response_present": bool(h01_payload.get("pr")),
            "raw_response_reconstructed": reconstructed,
            "files": h01_bundle,
        },
        "h02": {
            "handle": H02_CASE_HANDLE,
            "case_id_audit_only": H02_CASE_ID,
            "model": H02_MODEL,
            "contract": H02_CONTRACT,
            "transport": TRANSPORT_VERSION_11,
            "request_sha256_expected": H02_REQUEST_SHA256,
            "request_sha256_recorded": h02_req_hash,
            "request_sha256_match": h02_req_hash == H02_REQUEST_SHA256,
            "human_label_audit_only": H02_HUMAN_LABEL,
            "historical_status": "PARTIAL",
            "not_considered_pass": True,
            "cost_usd": H02_COST_USD,
            "paragraph_chars": len(h02_text),
            "raw_response_present": "pr" in h02_payload,
            "raw_response_reconstructed": reconstructed,
            "files": h02_bundle,
        },
        "supporting_audits": {
            "4b271": {
                "directory": str(h271).replace("\\", "/"),
                "exists": h271.is_dir(),
            },
            "4b272": {
                "directory": str(h272).replace("\\", "/"),
                "exists": h272.is_dir(),
            },
        },
        "missing": missing + h01_bundle["missing"] + h02_bundle["missing"],
        "MISSING_HISTORICAL_EVIDENCE": bool(missing or h01_bundle["missing"] or h02_bundle["missing"]),
        "invented_missing_data": False,
        "raw_responses_not_reconstructed_from_summaries": True,
        "historical_labels_unmodified": True,
        "historical_raw_responses_unmodified": True,
        "secrets_included": False,
    }


def comparative_analysis(
    *,
    h01_payload: dict[str, Any],
    h02_payload: dict[str, Any],
    h01_text: str,
    h02_text: str,
) -> dict[str, Any]:
    def _stats(payload: dict[str, Any], handle: str, text: str) -> dict[str, Any]:
        para = next(item for item in payload.get("pr") or [] if item.get("h") == handle)
        claims = list(para.get("c") or [])
        return {
            "chapter_verdict": payload.get("v"),
            "paragraph_verdict": para.get("v"),
            "claim_count": len(claims),
            "reservation_count": sum(
                1
                for item in claims
                if item.get("k") in {"QUESTIONABLE", "UNSUPPORTED"}
            ),
            "reason_codes": sorted(
                {str(code) for item in claims for code in (item.get("r") or [])}
            ),
            "paragraph_chars": len(text),
            "spans": [[item.get("s"), item.get("e")] for item in claims],
        }

    return {
        "phase": PHASE,
        "h01": {
            "status": "PARTIAL",
            "human_label_audit_only": H01_HUMAN_LABEL,
            "finding_4b271": "FALSE_REJECTION_SUPPORTED_BY_EVIDENCE",
            "disputed": "that fear can calculate or bargain with",
            **_stats(h01_payload, H01_CASE_HANDLE, h01_text),
        },
        "h02": {
            "status": "PARTIAL",
            "not_pass": True,
            "human_label_audit_only": H02_HUMAN_LABEL,
            "causal_clause_correctly_blocked": True,
            "contract_failed": True,
            "coverage_failed_historically": True,
            **_stats(h02_payload, H02_CASE_HANDLE, h02_text),
        },
        "shared": {
            "model": H01_MODEL,
            "transport": TRANSPORT_VERSION_11,
            "historical_labels_unmodified": True,
            "historical_raw_unmodified": True,
        },
        "lessons": [
            "Supported paraphrase must not be rejected for missing source verbs or intensifiers.",
            "New causality must still be isolated and blocked.",
            "Reason codes must come from the closed catalog.",
            "Coverage must require words and connectives, not every separator glyph.",
        ],
        "secrets_included": False,
    }


__all__ = ["comparative_analysis", "historical_canary_inventory"]
