"""Replay exact A.35 sous contrat 1.0 + contre-factuel DROP-only. Aucune réparation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.structured import parse_structured_output
from app.source_analysis_v31_global_canary_forensics.constants import (
    A35_DROP_FIELD_REASON,
    A35_DROP_INPUT_ID,
    A35_DROP_PROSE,
    CANONICAL_DROP_TOKEN,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_canary_forensics.evidence import (
    extract_a35_text_and_json,
    verify_a35_identity,
)
from app.source_analysis_v31_global_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v31_global_grammar_canary.validate import interpret_canary_response
from app.source_analysis_v31_global_preflight.transport import (
    build_global_consolidation_schema,
)


def parse_a35_transport(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    text, raw_json, raw = extract_a35_text_and_json(
        project_name, sortie_dir=sortie_dir
    )
    schema = build_global_consolidation_schema()
    parsed = parse_structured_output(text, schema)
    if not isinstance(parsed, dict):
        raise ValueError("A.35 structured parse did not return an object")
    return {
        "text": text,
        "raw_json": raw_json,
        "raw": raw,
        "transport": parsed,
        "schema_version": "global-consolidation-transport-1.0",
        "repaired": False,
    }


def replay_a35_under_v10_contract(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    identity = verify_a35_identity(project_name, sortie_dir=sortie_dir)
    parsed = parse_a35_transport(project_name, sortie_dir=sortie_dir)
    fixture = build_synthetic_fixture()
    interpreted = interpret_canary_response(
        parsed["transport"],
        fixture=fixture,
        raw_text=parsed["text"],
        signature=str(identity.get("analysis_signature") or "a35-replay"),
    )
    drop_row = None
    for row in (interpreted.get("transport") or {}).get("d") or []:
        if isinstance(row, dict) and row.get("i") == A35_DROP_INPUT_ID:
            drop_row = row
            break
    validator_errors = list(
        (interpreted.get("validator") or {}).get("errors") or interpreted.get("errors") or []
    )
    root = [
        error
        for error in validator_errors
        if "drop reason not in allowed set" in error or "forbidden drop reason" in error
    ]
    cascade = [error for error in validator_errors if error not in root]
    reproduced = (
        interpreted.get("structured_parse") == "PASS"
        and interpreted.get("decoder") == "PASS"
        and interpreted.get("handle_validation") == "PASS"
        and float(interpreted.get("idea_disposition_coverage") or 0) == 100.0
        and int(interpreted.get("silent_drops") or 0) == 0
        and interpreted.get("traceability") == "PASS"
        and interpreted.get("global_validator") == "FAIL"
        and interpreted.get("canonical_reconstruction") == "PASS"
        and (interpreted.get("semantic_review") or {}).get("status") == "FAIL"
        and drop_row is not None
        and drop_row.get("w") == A35_DROP_PROSE
        and identity.get("ok") is True
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "identity": identity,
        "structured_parse": interpreted.get("structured_parse"),
        "decoder": interpreted.get("decoder"),
        "handle_validation": interpreted.get("handle_validation"),
        "idea_disposition_coverage": interpreted.get("idea_disposition_coverage"),
        "silent_drops": interpreted.get("silent_drops"),
        "traceability": interpreted.get("traceability"),
        "global_validator": interpreted.get("global_validator"),
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "canonical_validation": interpreted.get("canonical_validation"),
        "semantic_review": (interpreted.get("semantic_review") or {}).get("status"),
        "semantic_detail": interpreted.get("semantic_review"),
        "validator_errors": validator_errors,
        "root_validator_violations": root,
        "cascade_validator_violations": cascade,
        "drop_row": drop_row,
        "inventory": interpreted.get("inventory"),
        "dispositions": interpreted.get("dispositions"),
        "transport": interpreted.get("transport"),
        "repaired": False,
        "historical_status_unchanged": "FAIL",
        "reproduced_a35_failure": reproduced,
        "interpreted": {
            key: value
            for key, value in interpreted.items()
            if key not in {"transport", "reconstruction", "replay"}
        },
    }


def drop_only_counterfactual_transport(transport: Mapping[str, Any]) -> dict[str, Any]:
    cloned = copy.deepcopy(dict(transport))
    changed = 0
    for row in cloned.get("d") or []:
        if isinstance(row, dict) and row.get("i") == A35_DROP_INPUT_ID:
            row[A35_DROP_FIELD_REASON] = CANONICAL_DROP_TOKEN
            changed += 1
    if changed != 1:
        raise ValueError(f"expected one DROP-only rewrite, got {changed}")
    return cloned


def replay_drop_only_counterfactual(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    parsed = parse_a35_transport(project_name, sortie_dir=sortie_dir)
    original = parsed["transport"]
    original_json = json.dumps(original, ensure_ascii=False, sort_keys=True)
    counterfactual = drop_only_counterfactual_transport(original)
    assert json.dumps(original, ensure_ascii=False, sort_keys=True) == original_json
    fixture = build_synthetic_fixture()
    interpreted = interpret_canary_response(
        counterfactual,
        fixture=fixture,
        signature="a35-drop-only-counterfactual",
    )
    original_replay = replay_a35_under_v10_contract(
        project_name, sortie_dir=sortie_dir
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "A35_DROP_ONLY_COUNTERFACTUAL",
        "original_immutable": original_replay.get("drop_row", {}).get("w") == A35_DROP_PROSE,
        "original_a35_status": "FAIL",
        "counterfactual_is_production_evidence": False,
        "only_field_changed": f"d[].{A35_DROP_FIELD_REASON} for {A35_DROP_INPUT_ID}",
        "replacement_token": CANONICAL_DROP_TOKEN,
        "structured_parse": interpreted.get("structured_parse"),
        "decoder": interpreted.get("decoder"),
        "handle_validation": interpreted.get("handle_validation"),
        "idea_disposition_coverage": interpreted.get("idea_disposition_coverage"),
        "silent_drops": interpreted.get("silent_drops"),
        "traceability": interpreted.get("traceability"),
        "global_validator": interpreted.get("global_validator"),
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "semantic_review": (interpreted.get("semantic_review") or {}).get("status"),
        "validator_errors": (interpreted.get("validator") or {}).get("errors")
        or interpreted.get("errors")
        or [],
        "drop_was_sole_technical_validator_root": (
            interpreted.get("global_validator") == "PASS"
            and original_replay.get("global_validator") == "FAIL"
            and original_replay.get("root_validator_violations")
            and not original_replay.get("cascade_validator_violations")
        ),
        "keep_not_rewritten_to_link_related": True,
        "repetition_not_invented": True,
        "semantic_pass_is_not_historical_pass": True,
        "result": "PASS" if interpreted.get("global_validator") == "PASS" else "FAIL",
        "transport": counterfactual,
        "original_drop_prose": A35_DROP_PROSE,
    }


__all__ = [
    "drop_only_counterfactual_transport",
    "parse_a35_transport",
    "replay_a35_under_v10_contract",
    "replay_drop_only_counterfactual",
]
