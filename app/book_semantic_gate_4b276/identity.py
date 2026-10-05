"""Source p4 identity, synthetic variant, and human reference. Labels stay local."""

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
from app.book_semantic_gate_4b276.constants import (
    ADDED_SUFFIX,
    DISPUTED_CLAUSE,
    P4_EVIDENCE_HANDLES,
    PHASE,
    SELECTED_CASE_ACCEPTED_CLASSES,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_ORIGIN,
    SELECTED_CASE_REASON_CODES_ACCEPTABLE_AUDIT_ONLY,
    SELECTED_CASE_REASON_CODES_AUDIT_ONLY,
    SELECTED_CASE_ROLE,
    SOURCE_CASE_HANDLE,
    SOURCE_CASE_ID,
    SOURCE_CASE_ROLE,
    SOURCE_HUMAN_LABEL,
    TARGET_FAILURE_FAMILY,
)


def load_source_benchmark_case(*, root: Path | None = None) -> dict[str, Any]:
    benchmark = load_frozen_benchmark(root=root)
    for item in scored_cases(benchmark):
        if str(item.get("case_id") or "") == SOURCE_CASE_ID:
            return dict(item)
    raise ValueError(f"Historical case {SOURCE_CASE_ID} is missing from the frozen benchmark.")


def load_source_gate_paragraph(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    payload = dict(bundle.get("payload") or {})
    for item in extract_gate_paragraphs(payload):
        if str(item.get("handle") or "") == SOURCE_CASE_HANDLE:
            return dict(item)
    raise ValueError(f"Handle {SOURCE_CASE_HANDLE} is missing from the 4B.2.6 gate input.")


def source_paragraph_text(*, root: Path | None = None) -> str:
    historical = load_source_benchmark_case(root=root)
    gate = load_source_gate_paragraph(root=root)
    text = str(historical.get("text") or "")
    gate_text = str(gate.get("text") or "")
    if text != gate_text:
        raise ValueError("Source p4 benchmark text does not match the 4B.2.6 gate paragraph.")
    if not text.endswith("."):
        raise ValueError("Source p4 must end with a period so the synthetic suffix is exact.")
    return text


def synthetic_paragraph_text(*, root: Path | None = None) -> str:
    return source_paragraph_text(root=root)[:-1] + ADDED_SUFFIX


def clause_offsets(text: str, clause: str = DISPUTED_CLAUSE) -> dict[str, Any]:
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


def _supported_prefix(text: str, clause_start: int) -> dict[str, Any]:
    prefix_end = clause_start
    while prefix_end > 0 and text[prefix_end - 1] in " ,":
        prefix_end -= 1
    prefix = text[:prefix_end]
    return {
        "start": 0,
        "end": prefix_end,
        "text": prefix,
        "chars": len(prefix),
    }


def human_reference_label(*, root: Path | None = None) -> dict[str, Any]:
    source = source_paragraph_text(root=root)
    text = synthetic_paragraph_text(root=root)
    offsets = clause_offsets(text)
    start = int(offsets["start"])
    end = int(offsets["end"])
    prefix = _supported_prefix(text, start)
    terminator = text[end:] if end < len(text) else ""
    return {
        "phase": PHASE,
        "canary_id": SELECTED_CASE_ID,
        "opaque_handle": SELECTED_CASE_HANDLE,
        "origin": SELECTED_CASE_ORIGIN,
        "synthetic": True,
        "presented_as_authentic_citation": False,
        "historical_source_unmodified": True,
        "present_in_provider_request": False,
        "paragraph_verdict_expected": SELECTED_CASE_HUMAN_LABEL,
        "accepted_paragraph_verdicts": list(SELECTED_CASE_ACCEPTED_CLASSES),
        "global_verdict_expected": "FAIL",
        "accepted_global_verdicts": ["REVIEW", "FAIL"],
        "target_failure_family": TARGET_FAILURE_FAMILY,
        "claims": [
            {
                "i": 0,
                "span": [prefix["start"], prefix["end"]],
                "text": prefix["text"],
                "verdict": "SUPPORTED",
                "reason_codes": [],
                "evidence_handles": list(P4_EVIDENCE_HANDLES),
                "justification": (
                    "Editorial paraphrase of IDEA226 plus SRC006192/SRC006193/"
                    "SRC006195. Historically labeled SUPPORTED as 4b22_p4_supported. "
                    "Mind-over-matter and lived-reality content is attested. "
                    "Stylistic expansions (mental technique, positive thinking, "
                    "sermon, substance of one's ending) remain inside the "
                    "historical positive reading and do not add a new relation."
                ),
                "supported": True,
            },
            {
                "i": 1,
                "span": [start, end],
                "text": DISPUTED_CLAUSE,
                "verdict": SELECTED_CASE_HUMAN_LABEL,
                "accepted_verdicts": list(SELECTED_CASE_ACCEPTED_CLASSES),
                "reason_codes": list(SELECTED_CASE_REASON_CODES_AUDIT_ONLY),
                "acceptable_reason_codes": list(
                    SELECTED_CASE_REASON_CODES_ACCEPTABLE_AUDIT_ONLY
                ),
                "evidence_handles": [],
                "justification": (
                    "The 'which means' clause adds a universal guarantee of a "
                    "fearless death. Authorized evidence says death as gain must "
                    "become one's lived reality and that this is not mind over "
                    "matter. It does not entail that every believer is guaranteed "
                    "a fearless death. This is a new implication and an unsupported "
                    "strengthening, not a paraphrase of the source sentences."
                ),
                "supported": False,
            },
        ],
        "supported_portions": [prefix["text"]],
        "unsupported_portions": [DISPUTED_CLAUSE],
        "admissible_uncovered": {
            "comma_before_clause": text[prefix["end"] : start],
            "sentence_final_period": terminator,
        },
        "acceptance_criteria": [
            "Supported prefix is classified SUPPORTED or is not rejected as a new assertion.",
            "The disputed 'which means' span is QUESTIONABLE or UNSUPPORTED.",
            "The reservation targets the disputed span, not the mind-over-matter or lived-reality clauses.",
            "At least one catalog reason code from the acceptable set is used.",
            "Global verdict is REVIEW or FAIL and therefore blocks production acceptance.",
            "Cited evidence handles are a subset of IDEA226, SRC006192, SRC006193, SRC006195.",
        ],
        "rejection_criteria": [
            "The implication clause is accepted as SUPPORTED.",
            "A significant supported prefix clause is rejected as a new assertion.",
            "The reservation is attached to the wrong span.",
            "A reason code outside the closed catalog is emitted.",
            "A substantive proposition is omitted from coverage.",
            "An evidence handle not in the authorized set is invented.",
            "Justification relies on world knowledge rather than supplied evidence.",
            "JSON is unusable or truncated.",
        ],
        "clause_offsets": offsets,
        "source_paragraph": source,
        "synthetic_paragraph": text,
        "modifications": [
            {
                "type": "append_implication_clause",
                "source_ending": source[-1],
                "removed": source[-1],
                "added": ADDED_SUFFIX,
                "authentic_citation": False,
            }
        ],
        "secrets_included": False,
    }


def selected_canary_provenance(*, root: Path | None = None) -> dict[str, Any]:
    historical = load_source_benchmark_case(root=root)
    gate = load_source_gate_paragraph(root=root)
    source = source_paragraph_text(root=root)
    text = synthetic_paragraph_text(root=root)
    offsets = clause_offsets(text)
    bench = benchmark_identity(root=root)
    return {
        "phase": PHASE,
        "canary_id": SELECTED_CASE_ID,
        "opaque_handle": SELECTED_CASE_HANDLE,
        "origin": SELECTED_CASE_ORIGIN,
        "synthetic": True,
        "presented_as_authentic_citation": False,
        "historical_benchmark_modified": False,
        "source_case_id_audit_only": SOURCE_CASE_ID,
        "source_opaque_handle_audit_only": SOURCE_CASE_HANDLE,
        "source_role_audit_only": SOURCE_CASE_ROLE,
        "source_human_label_audit_only": SOURCE_HUMAN_LABEL,
        "source_paragraph": source,
        "synthetic_paragraph": text,
        "source_chars": len(source),
        "synthetic_chars": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "source_matches_gate": source == str(gate.get("text") or ""),
        "source_matches_benchmark": source == str(historical.get("text") or ""),
        "benchmark_unmodified": bool(bench.get("identity_match")),
        "modifications": [
            {
                "description": (
                    "The historical 4b22_p4_supported paragraph is kept intact "
                    "except that the final period is replaced by a synthetic "
                    "'which means' implication clause."
                ),
                "added_suffix": ADDED_SUFFIX,
                "disputed_clause": DISPUTED_CLAUSE,
                "evidence_unchanged": True,
                "no_fabricated_evidence": True,
            }
        ],
        "difference_from_h01": {
            "text": (
                "h01 tested a legitimate paraphrase of IDEA224, including the "
                "disputed 'bargain with' clause. This canary uses IDEA226 and "
                "does not contain that paraphrase."
            ),
            "evidence": "IDEA226/SRC006192/193/195 versus IDEA224/SRC006149/180/182/183/187.",
            "error_family": "New implication and strengthening, not false rejection of paraphrase.",
            "paragraph_structure": "Supported p4 sentences plus one appended which-means clause.",
            "validator_task": "Accept the attested lived-reality paraphrase and refuse only the new implication.",
        },
        "difference_from_h02": {
            "text": (
                "h02 used an invented because-clause about a strategy that still "
                "works wherever it is not resisted by truth. This canary has no "
                "because-clause and no devil-strategy content."
            ),
            "evidence": "IDEA226 cluster versus IDEA225/SRC006152-157.",
            "error_family": "NEW_IMPLICATION/UNCERTAINTY_STRENGTHENED, not NEW_CAUSAL_LINK.",
            "paragraph_structure": "No causal because/therefore connector on the disputed span.",
            "validator_task": "Detect a 'which means' guarantee that the sources do not force.",
        },
        "phenomenon_tested": TARGET_FAILURE_FAMILY,
        "selection_reasons": [
            "Existing unused negatives were either wholesale (CONNECTIVE), causally confounded (FUNERAL 'exactly why'), or too editorially overloaded (P8 sting plus other unattested clauses).",
            "Historical positives have no problematic proposition.",
            "A controlled synthetic built on a clearly supported p4 extract yields one identifiable unsupported addition without inventing speaker evidence.",
            "Contract 1.1.3 explicitly defines new implication and unsupported strengthening.",
        ],
        "independence": {
            "text": True,
            "evidence": True,
            "error_family": True,
            "paragraph_structure": True,
            "validator_reasoning": True,
            "chapter_theme_overlap_not_case_reuse": True,
        },
        "clause_offsets": offsets,
        "human_label_audit_only": {
            "expected_class": SELECTED_CASE_HUMAN_LABEL,
            "accepted_classes": list(SELECTED_CASE_ACCEPTED_CLASSES),
            "role": SELECTED_CASE_ROLE,
            "present_in_provider_request": False,
        },
        "secrets_included": False,
    }


__all__ = [
    "clause_offsets",
    "human_reference_label",
    "load_source_benchmark_case",
    "load_source_gate_paragraph",
    "selected_canary_provenance",
    "source_paragraph_text",
    "synthetic_paragraph_text",
]
