"""Inventaire SRC des réponses provider réelles sauvegardées. 0 appel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.source_analysis_local_v3.source_refs import (
    classify_src_token,
    is_canonical_src,
    walk_src_like_fields,
)
from app.source_analysis_v31_src_typo_forensics.classify import forensic_token_class
from app.source_analysis_v31_src_typo_forensics.constants import (
    A19_MALFORMED,
    HISTORICAL_RESPONSES,
    MALFORMED_TOKEN,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_src_typo_forensics.evidence import (
    extract_text_from_raw,
    historical_raw_path,
)


def _payload_from_raw(raw: bytes) -> dict[str, Any] | None:
    text, _envelope = extract_text_from_raw(raw)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def inventory_response_src(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "available": False,
            "total": 0,
            "exact_valid": 0,
            "malformed": 0,
            "malformed_forms": [],
            "class_counts": {},
        }
    hits = [
        hit
        for hit in walk_src_like_fields(payload)
        if ".s[" in hit["path"] or hit["path"].endswith(".s")
    ]
    class_counts: dict[str, int] = {}
    malformed_forms: list[str] = []
    exact = 0
    for hit in hits:
        token = hit["token"]
        lexical = classify_src_token(token)
        klass = (
            "VALID_EXACT"
            if lexical == "canonical" and is_canonical_src(token)
            else forensic_token_class(
                token, allowed=set(), owned=set(), seen_in_record=set()
            )
        )
        if klass == "VALID_EXACT" or (lexical == "canonical" and is_canonical_src(token)):
            exact += 1
            class_counts["VALID_EXACT"] = class_counts.get("VALID_EXACT", 0) + 1
        else:
            if klass == "OUT_OF_WINDOW" and lexical == "canonical":
                # Unscoped historical inventory treats well-formed SRC as exact.
                exact += 1
                class_counts["VALID_EXACT"] = class_counts.get("VALID_EXACT", 0) + 1
                continue
            class_counts[klass] = class_counts.get(klass, 0) + 1
            malformed_forms.append(token)
    return {
        "available": True,
        "total": len(hits),
        "exact_valid": exact,
        "malformed": len(hits) - exact,
        "malformed_forms": malformed_forms,
        "class_counts": class_counts,
    }


def build_src_history(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total = exact = malformed = 0
    responses_with_malformed = 0
    forms: list[str] = []
    by_generation: dict[str, dict[str, int]] = {}
    for spec in HISTORICAL_RESPONSES:
        path = historical_raw_path(spec["relative"], project_name, sortie_dir=sortie_dir)
        inventory = {
            "available": False,
            "total": 0,
            "exact_valid": 0,
            "malformed": 0,
            "malformed_forms": [],
            "class_counts": {},
        }
        if path.is_file():
            inventory = inventory_response_src(_payload_from_raw(path.read_bytes()))
        generation = spec["generation"]
        bucket = by_generation.setdefault(
            generation, {"responses": 0, "total": 0, "exact_valid": 0, "malformed": 0}
        )
        bucket["responses"] += 1
        bucket["total"] += inventory["total"]
        bucket["exact_valid"] += inventory["exact_valid"]
        bucket["malformed"] += inventory["malformed"]
        total += inventory["total"]
        exact += inventory["exact_valid"]
        malformed += inventory["malformed"]
        if inventory["malformed"]:
            responses_with_malformed += 1
            forms.extend(inventory["malformed_forms"])
        rows.append(
            {
                **spec,
                "raw_present": path.is_file(),
                **inventory,
            }
        )
    rates = {}
    for key, bucket in by_generation.items():
        denom = bucket["total"] or 1
        rates[key] = {
            **bucket,
            "malformed_rate": round(bucket["malformed"] / denom, 6),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "normalized": False,
        "repaired": False,
        "responses": rows,
        "total_real_src_occurrences_inspected": total,
        "exact_valid": exact,
        "malformed": malformed,
        "malformed_rate": round(malformed / total, 6) if total else 0.0,
        "responses_with_ge1_malformed": responses_with_malformed,
        "malformed_forms_observed": sorted(set(forms)),
        "known_malformed_forms": [A19_MALFORMED, MALFORMED_TOKEN],
        "by_generation": rates,
        "incompatible_contracts_not_blindly_mixed": True,
        "a15_is_v2_transport": True,
        "a19_is_v3_pre_or_at_hardening": True,
    }


__all__ = ["build_src_history", "inventory_response_src"]
