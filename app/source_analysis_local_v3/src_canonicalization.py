"""Canonicalisation étroite d'identifiants SRC. Copie dérivée uniquement.

Placement :
  1. octets provider bruts (immuables)
  2. parse structuré (objet JSON tel qu'émis)
  3. canonicalisation SRC (copie dérivée)  ← ici
  4. décodeur v3/v3.1 (exige ^SRC[0-9]{6}$)
  5. registry / résolution de handles
  6. validateur local / politique de longueur

Le décodeur et collect_v3_source_refs restent stricts. Aucun jeton déjà
canonique n'est réécrit. Aucune mutation de chiffres. Fail-closed.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping

from app.source_analysis_local_v3.constants import (
    SRC_REFERENCE_POLICY_VERSION_10_STRICT,
    SRC_REFERENCE_POLICY_VERSION_11_NARROW_CANONICALIZATION,
)
from app.source_analysis_local_v3.source_refs import (
    SRC_PREFIX,
    SRC_WIDTH,
    is_canonical_src,
)
from app.source_analysis_local_v3.src_policy import (
    CORRECTION_REASON,
    ELIGIBLE_MALFORMED_PREFIX_CASEFOLD,
    PIPELINE_POSITION,
)

_LETTER_DIGIT = re.compile(r"^([A-Za-z]+)([0-9]+)$")

REASON_ALREADY_CANONICAL = "ALREADY_CANONICAL"
REASON_NOT_LETTER_DIGIT = "NOT_LETTER_DIGIT_TOKEN"
REASON_PREFIX_NOT_ELIGIBLE = "PREFIX_NOT_ELIGIBLE"
REASON_DIGIT_PAYLOAD_NOT_SIX = "DIGIT_PAYLOAD_NOT_SIX"
REASON_OUT_OF_WINDOW = "OUT_OF_WINDOW"
REASON_UNKNOWN_SRC = "UNKNOWN_SRC"
REASON_AMBIGUOUS = "AMBIGUOUS_CANDIDATE"
REASON_NON_STRING = "NON_STRING_OR_EMPTY"
REASON_STRICT_POLICY = "STRICT_POLICY_NO_REWRITE"


def split_prefix_digits(token: str) -> tuple[str, str] | None:
    if not isinstance(token, str) or not token:
        return None
    match = _LETTER_DIGIT.fullmatch(token)
    if match is None:
        return None
    return match.group(1), match.group(2)


def prefix_is_eligible(prefix: str) -> bool:
    return prefix.casefold() in ELIGIBLE_MALFORMED_PREFIX_CASEFOLD


def classify_malformed_token(token: Any) -> dict[str, Any]:
    if not isinstance(token, str) or not token:
        return {
            "eligible": False,
            "reason": REASON_NON_STRING,
            "prefix": None,
            "digits": None,
            "candidate": None,
        }
    if is_canonical_src(token):
        return {
            "eligible": False,
            "reason": REASON_ALREADY_CANONICAL,
            "prefix": SRC_PREFIX,
            "digits": token[len(SRC_PREFIX) :],
            "candidate": token,
            "already_canonical": True,
        }
    split = split_prefix_digits(token)
    if split is None:
        return {
            "eligible": False,
            "reason": REASON_NOT_LETTER_DIGIT,
            "prefix": None,
            "digits": None,
            "candidate": None,
        }
    prefix, digits = split
    if len(digits) != SRC_WIDTH:
        return {
            "eligible": False,
            "reason": REASON_DIGIT_PAYLOAD_NOT_SIX,
            "prefix": prefix,
            "digits": digits,
            "candidate": None,
        }
    if not prefix_is_eligible(prefix):
        return {
            "eligible": False,
            "reason": REASON_PREFIX_NOT_ELIGIBLE,
            "prefix": prefix,
            "digits": digits,
            "candidate": None,
        }
    return {
        "eligible": True,
        "reason": CORRECTION_REASON,
        "prefix": prefix,
        "digits": digits,
        "candidate": SRC_PREFIX + digits,
        "already_canonical": False,
    }


def canonicalize_src_token(
    token: Any,
    *,
    owned: set[str],
    existing: set[str],
    policy_version: str = SRC_REFERENCE_POLICY_VERSION_11_NARROW_CANONICALIZATION,
) -> dict[str, Any]:
    """Décide pour UN jeton. Ne mute pas le jeton d'entrée."""
    classified = classify_malformed_token(token)
    raw = token if isinstance(token, str) else None
    if classified.get("already_canonical"):
        return {
            "action": "unchanged",
            "raw_source_ref": raw,
            "canonical_source_ref": raw,
            "reason": REASON_ALREADY_CANONICAL,
            "prefix": classified["prefix"],
            "digits": classified["digits"],
            "numeric_preserved": True,
            "rewritten": False,
        }
    if policy_version == SRC_REFERENCE_POLICY_VERSION_10_STRICT:
        return {
            "action": "rejected",
            "raw_source_ref": raw,
            "canonical_source_ref": None,
            "reason": REASON_STRICT_POLICY,
            "prefix": classified.get("prefix"),
            "digits": classified.get("digits"),
            "numeric_preserved": classified.get("digits") is not None
            and len(str(classified.get("digits") or "")) == SRC_WIDTH,
            "rewritten": False,
        }
    if not classified["eligible"]:
        return {
            "action": "rejected",
            "raw_source_ref": raw,
            "canonical_source_ref": None,
            "reason": classified["reason"],
            "prefix": classified.get("prefix"),
            "digits": classified.get("digits"),
            "numeric_preserved": False,
            "rewritten": False,
        }
    candidate = classified["candidate"]
    assert isinstance(candidate, str)
    resolved: list[str] = []
    if candidate in owned and candidate in existing:
        resolved.append(candidate)
    if len(resolved) != 1:
        if candidate not in owned:
            reason = REASON_OUT_OF_WINDOW
        elif candidate not in existing:
            reason = REASON_UNKNOWN_SRC
        else:
            reason = REASON_AMBIGUOUS
        return {
            "action": "rejected",
            "raw_source_ref": raw,
            "canonical_source_ref": None,
            "reason": reason,
            "prefix": classified["prefix"],
            "digits": classified["digits"],
            "candidate": candidate,
            "numeric_preserved": True,
            "rewritten": False,
        }
    return {
        "action": "canonicalized",
        "raw_source_ref": raw,
        "canonical_source_ref": resolved[0],
        "reason": CORRECTION_REASON,
        "prefix": classified["prefix"],
        "digits": classified["digits"],
        "numeric_preserved": True,
        "rewritten": True,
    }


def _empty_audit(policy_version: str, original_id: int, derived_id: int) -> dict[str, Any]:
    return {
        "policy_version": policy_version,
        "pipeline_position": PIPELINE_POSITION,
        "derived_only": True,
        "raw_object_id": original_id,
        "derived_object_id": derived_id,
        "raw_object_is_derived": original_id == derived_id,
        "raw_malformed_src_count": 0,
        "canonicalized_src_count": 0,
        "rejected_malformed_src_count": 0,
        "already_canonical_src_count": 0,
        "corrections": [],
        "rejections": [],
        "strict_raw_validity": "PASS",
        "derived_canonical_validity": "PASS",
    }


def apply_src_reference_policy(
    payload: Mapping[str, Any] | None,
    *,
    owned: set[str],
    existing: set[str],
    policy_version: str = SRC_REFERENCE_POLICY_VERSION_11_NARROW_CANONICALIZATION,
) -> dict[str, Any]:
    """
    Retourne une copie dérivée et un audit. Le payload d'entrée n'est pas muté.
    """
    original_id = id(payload)
    if not isinstance(payload, Mapping):
        derived: dict[str, Any] = {}
        audit = _empty_audit(policy_version, original_id, id(derived))
        audit["strict_raw_validity"] = "FAIL"
        audit["derived_canonical_validity"] = "FAIL"
        return {"derived": derived, "audit": audit, "original": payload}

    derived_payload = copy.deepcopy(dict(payload))
    audit = _empty_audit(policy_version, original_id, id(derived_payload))
    records = derived_payload.get("records")
    original_records = payload.get("records") if isinstance(payload.get("records"), list) else []
    if not isinstance(records, list):
        audit["strict_raw_validity"] = "FAIL"
        audit["derived_canonical_validity"] = "FAIL"
        return {"derived": derived_payload, "audit": audit, "original": payload}

    for index, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        refs = item.get("s")
        if not isinstance(refs, list):
            continue
        original_item = (
            original_records[index]
            if index < len(original_records) and isinstance(original_records[index], dict)
            else {}
        )
        original_refs = original_item.get("s") if isinstance(original_item.get("s"), list) else []
        for position, token in enumerate(list(refs)):
            original_token = original_refs[position] if position < len(original_refs) else token
            if is_canonical_src(original_token):
                audit["already_canonical_src_count"] += 1
                continue
            audit["raw_malformed_src_count"] += 1
            decision = canonicalize_src_token(
                token,
                owned=owned,
                existing=existing,
                policy_version=policy_version,
            )
            row = {
                "record_index": index,
                "position": position,
                "kind": str(item.get("k") or ""),
                "handle": item.get("h"),
                **decision,
            }
            if decision["action"] == "canonicalized":
                refs[position] = decision["canonical_source_ref"]
                audit["canonicalized_src_count"] += 1
                audit["corrections"].append(row)
            else:
                audit["rejected_malformed_src_count"] += 1
                audit["rejections"].append(row)

    audit["strict_raw_validity"] = (
        "PASS" if audit["raw_malformed_src_count"] == 0 else "FAIL"
    )
    if policy_version == SRC_REFERENCE_POLICY_VERSION_10_STRICT:
        audit["derived_canonical_validity"] = audit["strict_raw_validity"]
    else:
        audit["derived_canonical_validity"] = (
            "PASS" if audit["rejected_malformed_src_count"] == 0 else "FAIL"
        )
    audit["raw_object_is_derived"] = original_id == id(derived_payload)
    return {"derived": derived_payload, "audit": audit, "original": payload}


def clean_transcript_src_ids(transcript: Any) -> set[str]:
    segments = getattr(transcript, "segments", None) or ()
    found: set[str] = set()
    for segment in segments:
        src_id = getattr(segment, "src_id", None)
        if isinstance(src_id, str) and src_id:
            found.add(src_id)
    return found


__all__ = [
    "REASON_ALREADY_CANONICAL",
    "REASON_AMBIGUOUS",
    "REASON_DIGIT_PAYLOAD_NOT_SIX",
    "REASON_NON_STRING",
    "REASON_NOT_LETTER_DIGIT",
    "REASON_OUT_OF_WINDOW",
    "REASON_PREFIX_NOT_ELIGIBLE",
    "REASON_STRICT_POLICY",
    "REASON_UNKNOWN_SRC",
    "apply_src_reference_policy",
    "canonicalize_src_token",
    "classify_malformed_token",
    "clean_transcript_src_ids",
    "prefix_is_eligible",
    "split_prefix_digits",
]
