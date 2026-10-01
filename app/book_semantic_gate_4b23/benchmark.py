"""Frozen historical semantic-gate benchmark. Does not modify candidates."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
    HISTORICAL_4B2_CANDIDATE_SHA256,
)
from app.book_semantic_gate_4b23.evidence import compact_candidate
from app.book_semantic_gate_4b23.identity import canonical_json_sha256
from app.book_semantic_gate_4b23.reasons import HISTORICAL_REASON_EXPECTATIONS


def _paragraph_by_handle(candidate: Mapping[str, Any], handle: str) -> dict[str, Any]:
    for section in candidate.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        for para in section.get("paragraphs") or []:
            if not isinstance(para, Mapping):
                continue
            if str(para.get("provider_handle") or "") == handle:
                return {
                    "handle": handle,
                    "section": str(section.get("section_id") or ""),
                    "kind": str(para.get("kind") or ""),
                    "text": str(para.get("text") or ""),
                    "evidence_handles": list(para.get("evidence_handles") or []),
                    "idea_refs": list(para.get("idea_refs") or []),
                    "reference_refs": list(para.get("reference_refs") or []),
                    "source_refs": list(para.get("source_refs") or []),
                }
    raise KeyError(handle)


def _case(
    *,
    case_id: str,
    source: str,
    candidate_sha256: str,
    paragraph: Mapping[str, Any],
    expected_class: str,
    accepted_classes: tuple[str, ...],
    reason_codes: tuple[str, ...],
    role: str,
    notes: list[str],
    clause: str | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "source": source,
        "role": role,
        "candidate_sha256": candidate_sha256,
        "paragraph_handle": paragraph["handle"],
        "section": paragraph["section"],
        "kind": paragraph["kind"],
        "text": paragraph["text"],
        "evidence_handles": paragraph["evidence_handles"],
        "expected_class": expected_class,
        "accepted_classes": list(accepted_classes),
        "expected_reason_codes": list(reason_codes),
        "clause": clause,
        "human_label_authority": True,
        "notes": notes,
    }


def build_historical_benchmark(
    *,
    candidate_4b2: Mapping[str, Any],
    candidate_4b22: Mapping[str, Any],
    raw_4b2: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    p2_22 = _paragraph_by_handle(candidate_4b22, "p2")
    p3_22 = _paragraph_by_handle(candidate_4b22, "p3")
    p4_22 = _paragraph_by_handle(candidate_4b22, "p4")
    p5_22 = _paragraph_by_handle(candidate_4b22, "p5")
    p6_22 = _paragraph_by_handle(candidate_4b22, "p6")
    p7_22 = _paragraph_by_handle(candidate_4b22, "p7")
    p8_22 = _paragraph_by_handle(candidate_4b22, "p8")
    p1_22 = _paragraph_by_handle(candidate_4b22, "p1")
    p2_2 = _paragraph_by_handle(candidate_4b2, "p2")
    p8_2 = _paragraph_by_handle(candidate_4b2, "p8")
    p13_2 = _paragraph_by_handle(candidate_4b2, "p13")
    exp = HISTORICAL_REASON_EXPECTATIONS
    cases = [
        _case(
            case_id="4b22_p1_connective",
            source="4B.2.2",
            candidate_sha256=HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
            paragraph=p1_22,
            expected_class=CLASS_NON_SUBSTANTIVE,
            accepted_classes=(CLASS_NON_SUBSTANTIVE, CLASS_SUPPORTED),
            reason_codes=(),
            role="positive_or_non_substantive",
            notes=["Human: CONNECTIVE_NON_SUBSTANTIVE orientation question."],
        ),
        _case(
            case_id="4b22_p2_supported",
            source="4B.2.2",
            candidate_sha256=HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
            paragraph=p2_22,
            expected_class=CLASS_SUPPORTED,
            accepted_classes=(CLASS_SUPPORTED,),
            reason_codes=(),
            role="positive",
            notes=["IDEA224 supported paraphrase."],
        ),
        _case(
            case_id="4b22_p4_supported",
            source="4B.2.2",
            candidate_sha256=HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
            paragraph=p4_22,
            expected_class=CLASS_SUPPORTED,
            accepted_classes=(CLASS_SUPPORTED,),
            reason_codes=(),
            role="positive",
            notes=["IDEA226 lived-reality vs intellectual idea."],
        ),
        _case(
            case_id="4b22_p5_supported",
            source="4B.2.2",
            candidate_sha256=HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
            paragraph=p5_22,
            expected_class=CLASS_SUPPORTED,
            accepted_classes=(CLASS_SUPPORTED,),
            reason_codes=(),
            role="positive",
            notes=["IDEA250 pastoral observation. Not an invented example."],
        ),
        _case(
            case_id="4b22_p6_supported",
            source="4B.2.2",
            candidate_sha256=HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
            paragraph=p6_22,
            expected_class=CLASS_SUPPORTED,
            accepted_classes=(CLASS_SUPPORTED,),
            reason_codes=(),
            role="positive",
            notes=["IDEA251 + complete REF051/REF056."],
        ),
        _case(
            case_id="4b22_p7_supported",
            source="4B.2.2",
            candidate_sha256=HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
            paragraph=p7_22,
            expected_class=CLASS_SUPPORTED,
            accepted_classes=(CLASS_SUPPORTED,),
            reason_codes=(),
            role="positive",
            notes=["IDEA252 source-supported testimony. Not invented."],
        ),
        _case(
            case_id="4b2_p2_supported",
            source="4B.2",
            candidate_sha256=HISTORICAL_4B2_CANDIDATE_SHA256,
            paragraph=p2_2,
            expected_class=CLASS_SUPPORTED,
            accepted_classes=(CLASS_SUPPORTED,),
            reason_codes=(),
            role="positive",
            notes=["Historical 4B.2 IDEA224 supported paragraph."],
        ),
        _case(
            case_id="4b22_p3_new_causal",
            source="4B.2.2",
            candidate_sha256=HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
            paragraph=p3_22,
            expected_class=exp["4b22_p3"]["classification"],
            accepted_classes=exp["4b22_p3"]["accepted_classifications"],
            reason_codes=exp["4b22_p3"]["reason_codes"],
            role="negative",
            clause=exp["4b22_p3"]["clause"],
            notes=["Core IDEA225 supported; causal clause unsupported."],
        ),
        _case(
            case_id="4b22_p8_reference_completion",
            source="4B.2.2",
            candidate_sha256=HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
            paragraph=p8_22,
            expected_class=exp["4b22_p8"]["classification"],
            accepted_classes=exp["4b22_p8"]["accepted_classifications"],
            reason_codes=exp["4b22_p8"]["reason_codes"],
            role="negative",
            clause=exp["4b22_p8"]["clause"],
            notes=["1 Corinthians 15 supplied; sting wording completes REF050."],
        ),
        _case(
            case_id="4b2_p8_invented_funeral",
            source="4B.2",
            candidate_sha256=HISTORICAL_4B2_CANDIDATE_SHA256,
            paragraph=p8_2,
            expected_class=CLASS_UNSUPPORTED,
            accepted_classes=(CLASS_UNSUPPORTED,),
            reason_codes=("INVENTED_EXAMPLE",),
            role="negative",
            clause=exp["4b2_p8_funeral"]["clause"],
            notes=["Invented funeral illustration. Not an invented Bible reference."],
        ),
        _case(
            case_id="4b2_p13_unsupported_connective",
            source="4B.2",
            candidate_sha256=HISTORICAL_4B2_CANDIDATE_SHA256,
            paragraph=p13_2,
            expected_class=CLASS_UNSUPPORTED,
            accepted_classes=(CLASS_UNSUPPORTED,),
            reason_codes=exp["4b2_p13_connective"]["reason_codes"],
            role="negative",
            clause=exp["4b2_p13_connective"]["clause"],
            notes=["Provider kind=con is not authoritative."],
        ),
    ]
    empty_raw = _empty_p9b(raw_4b2)
    return {
        "purpose": (
            "Later Terra canary must distinguish supported paraphrase from "
            "unsupported semantic extension."
        ),
        "terra_called": False,
        "human_labels_are_ground_truth": True,
        "original_candidates_modified": False,
        "candidate_4b2_sha256": HISTORICAL_4B2_CANDIDATE_SHA256,
        "candidate_4b22_sha256": HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
        "cases": cases,
        "positive_cases": [
            item["case_id"] for item in cases if item["role"] == "positive"
        ],
        "negative_cases": [
            item["case_id"] for item in cases if item["role"] == "negative"
        ],
        "non_substantive_cases": [
            item["case_id"]
            for item in cases
            if item["role"] == "positive_or_non_substantive"
        ],
        "structural_empty_p9b": empty_raw,
        "dataset_sha256": canonical_json_sha256(
            {"cases": cases, "structural_empty_p9b": empty_raw}
        ),
        "compact_4b22": compact_candidate(candidate_4b22),
        "failure_types_represented": [
            "INVENTED_EXAMPLE",
            "NEW_ARGUMENT",
            "NEW_CAUSAL_LINK",
            "REFERENCE_COMPLETION",
        ],
    }


def _empty_p9b(raw_4b2: Mapping[str, Any] | None) -> dict[str, Any]:
    parsed = (raw_4b2 or {}).get("parsed") or {}
    found = None
    for section in parsed.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        for para in section.get("paras") or []:
            if isinstance(para, Mapping) and str(para.get("h") or "") == "p9b":
                found = para
                break
    return {
        "handle": "p9b",
        "semantic_benchmark_case": False,
        "reason": (
            "Empty paragraph is deterministic BookGenerationValidator "
            "territory. It is blocked before the semantic gate and is not a "
            "semantic PASS/FAIL label."
        ),
        "raw_present": found is not None,
        "raw_text": (found or {}).get("t", ""),
    }


def benchmark_manifest(benchmark: Mapping[str, Any]) -> dict[str, Any]:
    cases = list(benchmark.get("cases") or [])
    return {
        "case_count": len(cases),
        "positive_count": len(benchmark.get("positive_cases") or []),
        "negative_count": len(benchmark.get("negative_cases") or []),
        "non_substantive_count": len(benchmark.get("non_substantive_cases") or []),
        "case_ids": [item.get("case_id") for item in cases],
        "dataset_sha256": benchmark.get("dataset_sha256"),
        "sources": ["4B.2 candidate", "4B.2.2 candidate"],
        "originals_modified": False,
        "terra_called": False,
        "p9b_included_as_semantic_pass_fail": False,
        "four_known_failure_types": list(
            benchmark.get("failure_types_represented") or []
        ),
        "human_label_authority": True,
    }


__all__ = ["benchmark_manifest", "build_historical_benchmark"]
