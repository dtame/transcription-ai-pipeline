"""P3 historical identity. Read-only. Labels stay in the local evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b24.identity import (
    benchmark_identity,
    load_frozen_benchmark,
    scored_cases,
)
from app.book_semantic_gate_4b261.complexity import extract_gate_input, extract_gate_paragraphs
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b272.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    EXPECTED_BENCHMARK_DATASET_SHA256,
    EXPECTED_BENCHMARK_FILE_SHA256,
    P3_EVIDENCE_HANDLES,
    PHASE,
    SELECTED_CASE_ACCEPTED_CLASSES,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_REASON_CODES_AUDIT_ONLY,
    SELECTED_CASE_ROLE,
)


def load_p3_benchmark_case(*, root: Path | None = None) -> dict[str, Any]:
    benchmark = load_frozen_benchmark(root=root)
    for item in scored_cases(benchmark):
        if str(item.get("case_id") or "") == SELECTED_CASE_ID:
            return dict(item)
    raise ValueError(f"Historical case {SELECTED_CASE_ID} is missing from the frozen benchmark.")


def load_p3_gate_paragraph(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    payload = dict(bundle.get("payload") or {})
    for item in extract_gate_paragraphs(payload):
        if str(item.get("handle") or "") == SELECTED_CASE_HANDLE:
            return dict(item)
    raise ValueError(f"Handle {SELECTED_CASE_HANDLE} is missing from the 4B.2.6 gate input.")


def clause_offsets(text: str, clause: str = DISPUTED_CAUSAL_CLAUSE) -> dict[str, Any]:
    start = text.find(clause)
    if start < 0:
        return {
            "found": False,
            "start": None,
            "end": None,
            "recovered": "",
            "exact_match": False,
        }
    end = start + len(clause)
    recovered = text[start:end]
    return {
        "found": True,
        "start": start,
        "end": end,
        "recovered": recovered,
        "exact_match": recovered == clause,
        "interval": "half_open",
        "python_slice": f"text[{start}:{end}]",
        "preceding": text[max(0, start - 40) : start],
        "following": text[end : min(len(text), end + 8)],
    }


def p3_benchmark_identity(*, root: Path | None = None) -> dict[str, Any]:
    bench = benchmark_identity(root=root)
    historical = load_p3_benchmark_case(root=root)
    paragraph = load_p3_gate_paragraph(root=root)
    text = str(historical.get("text") or "")
    gate_text = str(paragraph.get("text") or "")
    offsets = clause_offsets(text)
    problem = None
    if str(historical.get("role") or "") != SELECTED_CASE_ROLE:
        problem = "role_mismatch"
    if str(historical.get("expected_class") or "") != SELECTED_CASE_HUMAN_LABEL:
        problem = "label_mismatch"
    if not offsets.get("exact_match"):
        problem = "clause_not_found"
    if text != gate_text:
        problem = "gate_text_mismatch"
    declared = [str(item) for item in (historical.get("evidence_handles") or []) if item]
    if tuple(declared) != P3_EVIDENCE_HANDLES:
        problem = "evidence_handle_mismatch"
    return {
        "phase": PHASE,
        "case_id": SELECTED_CASE_ID,
        "benchmark_id": SELECTED_CASE_ID,
        "opaque_handle": SELECTED_CASE_HANDLE,
        "historical_paragraph_handle": historical.get("paragraph_handle"),
        "role_audit_only": historical.get("role"),
        "human_label_audit_only": {
            "expected_class": historical.get("expected_class"),
            "accepted_classes": list(
                historical.get("accepted_classes") or list(SELECTED_CASE_ACCEPTED_CLASSES)
            ),
            "expected_reason_codes": list(
                historical.get("expected_reason_codes")
                or list(SELECTED_CASE_REASON_CODES_AUDIT_ONLY)
            ),
            "present_in_provider_request": False,
            "authority": "frozen human benchmark label",
            "human_label_authority": historical.get("human_label_authority"),
        },
        "paragraph_text": text,
        "paragraph_chars": len(text),
        "unicode_codepoints": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "disputed_causal_clause": DISPUTED_CAUSAL_CLAUSE,
        "clause_position": offsets,
        "section": historical.get("section"),
        "kind": historical.get("kind"),
        "source_phase": historical.get("source"),
        "candidate_sha256": historical.get("candidate_sha256"),
        "evidence_handles": declared,
        "evidence_source": "frozen 4B.2.3 historical benchmark / 4B.2.6 gate slice",
        "notes": list(historical.get("notes") or []),
        "benchmark": {
            "file_sha256": bench.get("sha256"),
            "dataset_sha256": bench.get("dataset_sha256"),
            "bytes": bench.get("bytes"),
            "identity_match": bench.get("identity_match"),
            "expected_file_sha256": EXPECTED_BENCHMARK_FILE_SHA256,
            "expected_dataset_sha256": EXPECTED_BENCHMARK_DATASET_SHA256,
            "terra_called_in_artifact": bench.get("terra_called_in_artifact"),
            "original_candidates_modified": bench.get("original_candidates_modified"),
            "human_labels_are_ground_truth": bench.get("human_labels_are_ground_truth"),
        },
        "gate_text_matches_benchmark": text == gate_text,
        "benchmark_unmodified": True,
        "problem": problem,
        "identified": problem is None and bool(bench.get("identity_match")),
        "secrets_included": False,
    }


def p3_gate_slice_source(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    return extract_gate_input(dict(bundle.get("payload") or {}))


__all__ = [
    "clause_offsets",
    "load_p3_benchmark_case",
    "load_p3_gate_paragraph",
    "p3_benchmark_identity",
    "p3_gate_slice_source",
]
