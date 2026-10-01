"""Assemble le dossier A.30. 0 provider. 0 exécution WIN005-007."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.schema import (
    measure_v31_local_lite_schema_pair,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v31_kind_specific_limits.constants import (
    A18_PROOF_STILL_APPLIES,
    A28_HISTORICAL_STATUS,
    A29_STATUS,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    MODE,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    READY_AFTER_COUNT_IF_PROMOTED,
    READY_BEFORE,
    READY_BEFORE_COUNT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_VERSION,
    SOURCE_MAP_STATUS,
    TOTAL_WINDOWS,
    WIN003_PROMOTION_LABEL,
)
from app.source_analysis_v31_kind_specific_limits.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_kind_specific_limits.policy import build_policy
from app.source_analysis_v31_kind_specific_limits.preflight import (
    future_windows_preflight,
    inspect_win002_compatibility,
)
from app.source_analysis_v31_kind_specific_limits.promote import (
    build_provenance,
    persist_win003_candidate,
)
from app.source_analysis_v31_kind_specific_limits.replay import replay_saved_win003
from app.source_analysis_v31_kind_specific_limits.semantic import (
    confirm_semantic_identity,
    load_a29_semantic_evidence,
)
from app.source_analysis_v31_remaining_windows.paths import production_source_map_present


def _jsonable_replay(replay: dict[str, Any]) -> dict[str, Any]:
    skip = {"window", "transcript", "transport", "validation", "review", "canonical"}
    return {key: value for key, value in replay.items() if key not in skip}


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.30",
    persist_candidate: bool = True,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    policy = build_policy()
    measured = measure_v31_local_lite_schema_pair()
    schema_hash = semantic_transport_v31_local_lite_fingerprint()
    schema_unchanged = (
        measured.get("raw_bytes") == EXPECTED_RAW_SCHEMA_BYTES
        and measured.get("adapted_bytes") == EXPECTED_ADAPTED_SCHEMA_BYTES
        and schema_hash == EXPECTED_SCHEMA_HASH
    )
    schema = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "raw_bytes": measured.get("raw_bytes"),
        "adapted_bytes": measured.get("adapted_bytes"),
        "hash": schema_hash,
        "expected_raw": EXPECTED_RAW_SCHEMA_BYTES,
        "expected_adapted": EXPECTED_ADAPTED_SCHEMA_BYTES,
        "expected_hash": EXPECTED_SCHEMA_HASH,
        "identity": "UNCHANGED" if schema_unchanged else "CHANGED",
        "a18_grammar_proof": "APPLIES"
        if schema_unchanged and A18_PROOF_STILL_APPLIES
        else "DOES_NOT_APPLY",
    }
    replay = replay_saved_win003(project_name, sortie_dir=sortie_dir)
    a29_semantic = load_a29_semantic_evidence(project_name, sortie_dir=sortie_dir)
    semantic = confirm_semantic_identity(
        replay["identity"], a29_semantic, replay.get("review")
    )
    win002 = inspect_win002_compatibility(project_name, sortie_dir=sortie_dir)
    mixed = replay.get("mixed_compatibility")
    mixed_ok = mixed == "PASS" and win002.get("readable_as_local_lite") is True
    canonical_ok = replay.get("canonical_reconstruction") == "PASS"
    technical_ok = bool(replay.get("technical_ok"))
    semantic_ok = bool(semantic.get("reusable_as_semantic_evidence"))
    values_ok = bool(replay.get("values_unchanged"))
    identity_ok = bool(replay["identity"].get("same_paid_response"))
    historical_ok = bool(replay.get("historical_a28_reproduced"))
    contamination = int(replay.get("importance_to_kind_contamination") or 0)
    kinds_empty = bool(replay.get("all_kinds_empty"))
    promote = (
        schema_unchanged
        and identity_ok
        and values_ok
        and historical_ok
        and technical_ok
        and semantic_ok
        and canonical_ok
        and mixed_ok
        and contamination == 0
        and kinds_empty
        and replay.get("capacity") == "absent"
        and replay.get("provider_calls") == 0
    )
    stored: dict[str, str] = {}
    if promote and persist_candidate and isinstance(replay.get("transport"), dict):
        stored = persist_win003_candidate(
            project_name,
            replay["transport"],
            semantic_quality=replay.get("semantic_quality"),
            sortie_dir=sortie_dir,
        )
    provenance = build_provenance(
        promoted=promote,
        stored=stored,
        semantic_quality=replay.get("semantic_quality"),
    )
    preflight = future_windows_preflight(project_name, sortie_dir=sortie_dir)
    relations = {
        "WIN002": {"plausible-loose": "all", "note": "all relations plausible-loose"},
        "WIN003": replay.get("relation_quality_summary"),
        "WIN004": {
            "well-supported": 0,
            "plausible-loose": 23,
            "incorrect": 0,
            "unverifiable": 0,
        },
        "observation": (
            "Three READY local-lite windows show 0 well-supported and "
            "overwhelmingly plausible-loose relations."
        ),
        "RELATION_QUALITY_TECHNICAL_DEBT": "YES" if promote else "NO",
        "architecture_changed": False,
    }
    ready_after_count = READY_AFTER_COUNT_IF_PROMOTED if promote else READY_BEFORE_COUNT
    ready = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "ready_before": READY_BEFORE,
        "ready_after": f"{ready_after_count} / {TOTAL_WINDOWS}",
        "ready_after_count": ready_after_count,
        "windows": {
            "WIN001": "READY",
            "WIN002": "READY",
            "WIN003": "READY" if promote else "NOT READY",
            "WIN004": "READY",
            "WIN005": "NOT RUN",
            "WIN006": "NOT RUN",
            "WIN007": "NOT RUN",
        },
        "win003_promoted": promote,
        "win003_label": WIN003_PROMOTION_LABEL if promote else None,
        "a28_historical_status": A28_HISTORICAL_STATUS,
        "a29_status": A29_STATUS,
        "win005_007_executed": False,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "relation_quality_technical_debt": relations["RELATION_QUALITY_TECHNICAL_DEBT"],
    }
    gates = {
        "schema_unchanged": schema_unchanged,
        "identity_ok": identity_ok,
        "values_ok": values_ok,
        "historical_a28_fail_reproduced": historical_ok,
        "technical_ok": technical_ok,
        "semantic_ok": semantic_ok,
        "canonical_ok": canonical_ok,
        "mixed_ok": mixed_ok,
        "win002_compatible": win002.get("readable_as_local_lite"),
        "contamination_zero": contamination == 0,
        "kinds_empty": kinds_empty,
        "capacity_absent": replay.get("capacity") == "absent",
        "provider_calls_zero": replay.get("provider_calls") == 0,
        "source_map_absent": not source_map_path(
            project_name, sortie_dir=sortie_dir
        ).is_file()
        and not production_source_map_present(project_name, sortie_dir=sortie_dir),
    }
    result = "PASS" if promote and all(gates.values()) else "FAIL"
    if not promote and technical_ok is False and identity_ok:
        result = "PARTIAL" if schema_unchanged else "FAIL"
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a28_historical_status": A28_HISTORICAL_STATUS,
        "a29_status": A29_STATUS,
        "win003_promoted": promote,
        "ready_before": READY_BEFORE,
        "ready_after": ready["ready_after"],
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": "HUMAN REVIEW",
    }
    return {
        "header": header,
        "policy": policy,
        "schema": schema,
        "replay": replay,
        "replay_public": _jsonable_replay(replay),
        "a29_semantic": a29_semantic,
        "semantic": semantic,
        "win002": win002,
        "canonical": replay.get("canonical") or {},
        "provenance": provenance,
        "preflight": preflight,
        "relations": relations,
        "ready": ready,
        "gates": gates,
    }


__all__ = ["build_bundle"]
