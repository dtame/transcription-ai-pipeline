"""Replay A.46 immuable + contre-factuel limite/scanner. 0 provider. 0 réparation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
    A46_STATUS_PRESERVED,
    HISTORICAL_INTENT_LIMIT,
    PROJECT_NAME,
    SELECTED_INTENT_LIMIT,
)
from app.source_analysis_v31_global_a47_contract_forensics.contract import (
    corrected_text_limits,
    historical_text_limits,
)
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    derived_a46_transport,
    read_a46_candidate,
    read_a46_raw,
    verify_a46_identity,
)
from app.source_analysis_v31_global_a47_contract_forensics.paths import a46_execution_path
from app.source_analysis_v31_global_a47_contract_forensics.scanner import classify_a46_editorial
from app.source_analysis_v31_global_v30_exact_preflight.fakeai import production_inventory
from app.source_analysis_v31_global_v30_exact_preflight.inventory import load_exact_windows
from app.source_analysis_v31_global_v30_real_canary.semantic import review_semantics
from app.source_analysis_v31_global_v30_real_canary.validate import (
    interpret_production_response,
    technical_pass,
)
from app.source_analysis_v31_global_reuse_output.validate import validate_global_transport_v30


def load_a46_inventory(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    windows = load_exact_windows(project_name, sortie_dir=sortie_dir)
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    return production_inventory(windows["normalized"], transcript)


def _public_validation(validation: dict[str, Any]) -> dict[str, Any]:
    skip = {"transport", "source_map", "reconstruction"}
    public = {key: value for key, value in validation.items() if key not in skip}
    reconstruction = validation.get("reconstruction") or {}
    public["reconstruction"] = {
        key: reconstruction.get(key)
        for key in (
            "ok",
            "canonical_json",
            "ensure_valid_source_map",
            "errors",
            "source_map_published",
            "reuse_text_exact",
            "empty_relations_valid",
        )
    }
    public["errors"] = list(validation.get("errors") or [])[:12]
    return public


def replay_a46_frozen(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    identity = verify_a46_identity(project_name, sortie_dir=sortie_dir)
    transport = derived_a46_transport(project_name, sortie_dir=sortie_dir)
    inventory = load_a46_inventory(project_name, sortie_dir=sortie_dir)
    raw = read_a46_raw(project_name, sortie_dir=sortie_dir)
    interpreted = interpret_production_response(
        transport,
        inventory=inventory,
        raw_text=str(raw.get("raw_text") or ""),
        signature="a47-replay-a46-frozen",
        text_limits=historical_text_limits(),
    )
    candidate = read_a46_candidate(project_name, sortie_dir=sortie_dir)
    execution_path = a46_execution_path(project_name, sortie_dir=sortie_dir)
    historical = {}
    if execution_path.is_file():
        historical = json.loads(execution_path.read_text(encoding="utf-8")).get("execution") or {}
    structural = classify_a46_editorial(transport, candidate)
    return {
        "identity": identity,
        "historical_status": A46_STATUS_PRESERVED,
        "historical_global_validator": historical.get("global_validator") or "FAIL",
        "historical_editorial": historical.get("no_editorial_structure") or "FAIL",
        "historical_semantic": historical.get("semantic_review") or "FAIL",
        "global_validator": interpreted.get("global_validator"),
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "canonical_validation": interpreted.get("canonical_validation"),
        "deterministic_replay": interpreted.get("deterministic_replay"),
        "structured_parse": interpreted.get("structured_parse"),
        "decoder": interpreted.get("decoder"),
        "handle_validation": interpreted.get("handle_validation"),
        "idea_accountability": interpreted.get("idea_accountability"),
        "keep_count": interpreted.get("keep_count"),
        "merge_equivalent_count": interpreted.get("merge_equivalent_count"),
        "drop_count": interpreted.get("drop_count"),
        "technical_pass": technical_pass(interpreted),
        "structural_replay": structural.get("classification"),
        "structural_ok": (structural.get("structural") or {}).get("ok"),
        "validator_errors": list((interpreted.get("validator") or {}).get("errors") or []),
        "interpreted": _public_validation(interpreted),
        "raw_unchanged": True,
        "text_limits": HISTORICAL_INTENT_LIMIT,
    }


def replay_a46_counterfactual(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    transport = derived_a46_transport(project_name, sortie_dir=sortie_dir)
    inventory = load_a46_inventory(project_name, sortie_dir=sortie_dir)
    raw = read_a46_raw(project_name, sortie_dir=sortie_dir)
    limits = corrected_text_limits()
    interpreted = interpret_production_response(
        transport,
        inventory=inventory,
        raw_text=str(raw.get("raw_text") or ""),
        signature="a47-replay-a46-counterfactual",
        text_limits=limits,
    )
    reconstruction = interpreted.get("reconstruction") or {}
    candidate = reconstruction.get("payload")
    semantic = review_semantics(
        interpreted.get("transport"),
        inventory,
        accountability=str(interpreted.get("idea_accountability") or ""),
        missing=int(interpreted.get("missing_members") or 0),
        candidate_payload=candidate if isinstance(candidate, dict) else None,
    )
    editorial = classify_a46_editorial(
        interpreted.get("transport") or transport,
        candidate if isinstance(candidate, dict) else read_a46_candidate(
            project_name, sortie_dir=sortie_dir
        ),
    )
    gm = (interpreted.get("transport") or transport).get("gm") or {}
    at_290 = validate_global_transport_v30(
        transport,
        idea_input_ids=list(inventory.get("idea_input_ids") or []),
        allowed_input_ids=set(inventory.get("allowed_input_ids") or []),
        local_kind_by_input=inventory.get("kind_by_input") or {},
        text_limits={**limits, "intent": 290},
    )
    return {
        "historical_a46_status": A46_STATUS_PRESERVED,
        "raw_unchanged": True,
        "truncated": False,
        "rewritten": False,
        "published": False,
        "text_limits": limits,
        "selected_intent_limit": SELECTED_INTENT_LIMIT,
        "gm_in_length": len(str(gm.get("in") or "")),
        "global_validator": interpreted.get("global_validator"),
        "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
        "canonical_validation": interpreted.get("canonical_validation"),
        "deterministic_replay": interpreted.get("deterministic_replay"),
        "technical_pass": technical_pass(interpreted),
        "semantic_status": semantic.get("status"),
        "editorial_status": (semantic.get("editorial") or {}).get("status"),
        "structural_scan": editorial.get("classification"),
        "limit_290_also_accepts": bool(at_290.get("ok")),
        "counterfactual": (
            "PASS"
            if interpreted.get("global_validator") == "PASS"
            and interpreted.get("canonical_reconstruction") == "PASS"
            and interpreted.get("canonical_validation") == "PASS"
            and (semantic.get("editorial") or {}).get("status") == "PASS"
            else "FAIL"
        ),
        "interpreted": _public_validation(interpreted),
        "semantic_public": {
            "status": semantic.get("status"),
            "reuse": _summary(semantic.get("reuse")),
            "merges": _summary(semantic.get("merges")),
            "drops": _summary(semantic.get("drops")),
            "topics": _summary(semantic.get("topics")),
            "metadata": semantic.get("metadata"),
            "completeness": semantic.get("completeness"),
            "editorial": semantic.get("editorial"),
            "uncertainty": semantic.get("uncertainty"),
            "publication_semantic_ok": semantic.get("publication_semantic_ok"),
        },
    }


def _summary(block: Any) -> dict[str, Any]:
    if not isinstance(block, dict):
        return {}
    return {
        key: block.get(key)
        for key in (
            "status",
            "count",
            "failures",
            "all_supported",
            "editorial_count",
            "unsupported_count",
            "review_count",
            "classifications",
        )
        if key in block
    }


__all__ = [
    "load_a46_inventory",
    "replay_a46_counterfactual",
    "replay_a46_frozen",
]
