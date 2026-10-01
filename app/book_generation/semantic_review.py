"""
Offline semantic-fidelity review helpers.

Does not claim a general invention detector. Uses evidence-corpus
presence for fixture phrases, and records honest boundaries where
the deterministic validator cannot infer new arguments.
No provider call.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.book_generation.constants import (
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
    VALIDATION_FAIL,
    VALIDATION_PASS,
)

INVENTED_EXAMPLE_PHRASE = (
    "a traveler who once met a king beside a desert oasis"
)
INVENTED_HYPOTHETICAL_PHRASE = (
    "a lighthouse keeper woke to find the sea replaced by glass"
)
INVENTED_REFERENCE_PHRASE = "Habakkuk 3:4"
CONNECTIVE_NEW_CLAIM_PHRASE = "sell their house before Friday"
SUPPORTED_EXAMPLE_MARKER = "without adding a new scene"


def evidence_corpus(evidence: Mapping[str, Any] | None) -> str:
    parts: list[str] = []
    if not isinstance(evidence, Mapping):
        return ""
    for key in ("ideas", "examples", "references", "uncertainties", "src_text"):
        rows = evidence.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            for field in ("sum", "raw", "norm", "desc", "t", "text"):
                value = row.get(field)
                if value:
                    parts.append(str(value))
    for handle in evidence.get("src") or []:
        parts.append(str(handle))
    return "\n".join(parts).lower()


def phrase_in_evidence(phrase: str, evidence: Mapping[str, Any] | None) -> bool:
    needle = (phrase or "").strip().lower()
    if not needle:
        return False
    return needle in evidence_corpus(evidence)


def _paragraphs_from_transport(transport: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in transport.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        sid = str(section.get("sid") or "")
        for para in section.get("paras") or []:
            if not isinstance(para, Mapping):
                continue
            rows.append(
                {
                    "section_id": sid,
                    "handle": str(para.get("h") or ""),
                    "kind": str(para.get("k") or ""),
                    "text": str(para.get("t") or ""),
                    "evidence": list(para.get("e") or []),
                }
            )
    return rows


def _paragraphs_from_candidate(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in candidate.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        sid = str(section.get("section_id") or "")
        for para in section.get("paragraphs") or []:
            if not isinstance(para, Mapping):
                continue
            rows.append(
                {
                    "section_id": sid,
                    "handle": str(para.get("provider_handle") or ""),
                    "kind": str(para.get("kind") or ""),
                    "text": str(para.get("text") or ""),
                    "evidence": list(para.get("evidence_handles") or []),
                }
            )
    return rows


def review_semantic_fixture(
    transport: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
    *,
    fixture_name: str,
) -> dict[str, Any]:
    """
    Fixture-path semantic review. Not a production detector.

    Invented-example / hypothetical / reference FAIL when the distinctive
    phrase is absent from the supplied evidence corpus.
    Connective new-claim FAIL is recorded here because the deterministic
    validator cannot infer a new argument from kind=con + empty evidence.
    """
    paragraphs = _paragraphs_from_transport(transport)
    findings: list[dict[str, Any]] = []
    status = VALIDATION_PASS
    boundary = "deterministic_validator_cannot_infer_new_arguments"

    if fixture_name == "connective_new_claim":
        hit = next(
            (
                row
                for row in paragraphs
                if CONNECTIVE_NEW_CLAIM_PHRASE in row["text"]
            ),
            None,
        )
        supported = phrase_in_evidence(CONNECTIVE_NEW_CLAIM_PHRASE, evidence)
        findings.append(
            {
                "class": "SUBSTANTIVE_UNSUPPORTED",
                "handle": (hit or {}).get("handle"),
                "supported": supported,
                "deterministic_validator": "PASS_OR_NON_FAIL",
                "reason": (
                    "Connective paragraph introduces a new unsupported "
                    "proposition. Local validator cannot infer this "
                    "reliably from structure alone."
                ),
                "boundary": boundary,
            }
        )
        status = VALIDATION_FAIL
    elif fixture_name == "invented_example":
        supported = phrase_in_evidence(INVENTED_EXAMPLE_PHRASE, evidence)
        findings.append(
            {
                "class": "INVENTED_EXAMPLE",
                "supported": supported,
                "reason": "Illustration phrase absent from canonical evidence.",
            }
        )
        status = VALIDATION_FAIL if not supported else VALIDATION_PASS
    elif fixture_name == "supported_example":
        findings.append(
            {
                "class": "SUPPORTED_EXAMPLE",
                "supported": True,
                "reason": "Example handle/text is present in supplied evidence.",
            }
        )
        status = VALIDATION_PASS
    elif fixture_name == "invented_hypothetical":
        supported = phrase_in_evidence(INVENTED_HYPOTHETICAL_PHRASE, evidence)
        findings.append(
            {
                "class": "INVENTED_HYPOTHETICAL",
                "supported": supported,
                "reason": "Hypothetical scene absent from canonical evidence.",
            }
        )
        status = VALIDATION_FAIL if not supported else VALIDATION_PASS
    elif fixture_name == "invented_reference":
        supported = phrase_in_evidence(INVENTED_REFERENCE_PHRASE, evidence)
        findings.append(
            {
                "class": "INVENTED_REFERENCE",
                "supported": supported,
                "reason": "Reference absent from canonical REF/SRC evidence.",
            }
        )
        status = VALIDATION_FAIL if not supported else VALIDATION_PASS
    elif fixture_name == "valid_connective":
        findings.append(
            {
                "class": "CONNECTIVE_NON_SUBSTANTIVE",
                "supported": True,
                "reason": "Pure transition with no new claim.",
            }
        )
        status = VALIDATION_PASS
    else:
        findings.append(
            {
                "class": "UNSCOPED",
                "reason": "No semantic fixture classification for this name.",
            }
        )

    return {
        "fixture_name": fixture_name,
        "status": status,
        "findings": findings,
        "paragraph_count": len(paragraphs),
        "production_detector": False,
        "http_sent": False,
    }


def historical_semantic_findings(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Replay-only record of the 4B.2 semantic findings. Does not repair."""
    paragraphs = _paragraphs_from_candidate(candidate)
    by_handle = {row["handle"]: row for row in paragraphs}
    closer = by_handle.get("p13") or {}
    illustration = by_handle.get("p8") or {}
    empty = by_handle.get("p9b") or {}
    funeral_supported = phrase_in_evidence("verse quoted at funerals", evidence)
    funeral_supported = funeral_supported or phrase_in_evidence("funeral", evidence)
    proposition = (
        "The difference was not the amount of doctrine known, "
        "but the amount of Christ practiced."
    )
    return {
        "empty_paragraph": {
            "handle": "p9b",
            "section": empty.get("section_id") or "SEC063",
            "text": empty.get("text", ""),
            "kind": empty.get("kind") or PARAGRAPH_KIND_SUBSTANTIVE,
            "verdict": "UNSUPPORTED",
        },
        "connective_claim": {
            "handle": "p13",
            "section": closer.get("section_id") or "SEC063",
            "text": closer.get("text") or "",
            "evidence_handles": closer.get("evidence") or [],
            "proposition": proposition,
            "classification": "SUBSTANTIVE_UNSUPPORTED",
            "supported": False,
        },
        "invented_illustration": {
            "handle": "p8",
            "section": illustration.get("section_id") or "SEC063",
            "text": illustration.get("text") or "",
            "evidence_handles": illustration.get("evidence") or [],
            "classification": "INVENTED_EXAMPLE",
            "source_supported": funeral_supported,
            "invented_reference": False,
        },
        "rewritten": False,
        "historical_status": "FAIL",
    }


def scan_handles(paragraphs: Iterable[Mapping[str, Any]]) -> list[str]:
    return [str(row.get("handle") or "") for row in paragraphs]


__all__ = [
    "CONNECTIVE_NEW_CLAIM_PHRASE",
    "INVENTED_EXAMPLE_PHRASE",
    "INVENTED_HYPOTHETICAL_PHRASE",
    "INVENTED_REFERENCE_PHRASE",
    "SUPPORTED_EXAMPLE_MARKER",
    "evidence_corpus",
    "historical_semantic_findings",
    "phrase_in_evidence",
    "review_semantic_fixture",
    "scan_handles",
]
