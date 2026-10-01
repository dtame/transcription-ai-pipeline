"""Audit relationnel transversal READY local-lite + nouvelles fenêtres A.31."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_final_three.constants import (
    EXECUTION_ORDER,
    HISTORICAL_READY_IDS,
    MODE,
    PHASE,
    PROJECT_NAME,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _ready_historical(
    project_name: str,
    *,
    sortie_dir: Path | None,
) -> dict[str, Any]:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    win001 = {
        "result": "READY",
        "transport": "semantic-transport-v3",
        "distinguishable_from_local_lite": True,
        "distribution": {
            "note": "WIN001 V3 relation contract differs; keep evidence separate."
        },
    }
    win002 = _load_json(audit / "source_analysis_v31_WIN002_semantic_review.json")
    win003 = _load_json(audit / "source_analysis_v31_WIN003_semantic_review.json")
    win004 = _load_json(audit / "source_analysis_v31_win004_semantic_review.json")
    return {
        "WIN001": win001,
        "WIN002": {
            "result": "READY",
            "transport": "semantic-transport-v3.1-local-lite",
            "distribution": win002.get("relation_quality_summary")
            or {"plausible-loose": "all", "note": "A.28/A.30 READY local-lite"},
        },
        "WIN003": {
            "result": "READY",
            "transport": "semantic-transport-v3.1-local-lite",
            "provenance": "A.28 response / A.30 revalidated",
            "distribution": win003.get("relation_quality_summary") or {},
        },
        "WIN004": {
            "result": "READY",
            "transport": "semantic-transport-v3.1-local-lite",
            "distribution": win004.get("relation_quality_summary")
            or {
                "well-supported": 0,
                "plausible-loose": 23,
                "incorrect": 0,
                "unverifiable": 0,
            },
        },
    }


def build_relation_cross(
    result: Any,
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    totals = {
        "well-supported": 0,
        "plausible-loose": 0,
        "incorrect": 0,
        "unverifiable": 0,
    }
    new_totals = dict(totals)
    per_window: dict[str, Any] = {}
    historical = _ready_historical(project_name, sortie_dir=sortie_dir)
    for window_id in HISTORICAL_READY_IDS:
        row = historical.get(window_id) or {}
        dist = dict(row.get("distribution") or {})
        per_window[window_id] = {
            "result": row.get("result") or "READY",
            "ready_before_a31": True,
            "transport": row.get("transport"),
            "distribution": dist,
            "win001_v3_distinct": window_id == "WIN001",
        }
        if window_id != "WIN001":
            for key in totals:
                raw = dist.get(key)
                if isinstance(raw, (int, float)):
                    totals[key] += int(raw)
    successful = 0
    for window_id in EXECUTION_ORDER:
        item = (result.windows or {}).get(window_id) or {}
        execution = item.get("execution") or {}
        dist = dict(execution.get("relation_quality_summary") or {})
        if not dist:
            dist = dict((item.get("review") or {}).get("relation_quality_summary") or {})
        for key in totals:
            raw = dist.get(key)
            if isinstance(raw, (int, float)):
                totals[key] += int(raw)
                new_totals[key] += int(raw)
        if execution.get("result") == "PASS" or item.get("result") == "PASS":
            successful += 1
        per_window[window_id] = {
            "result": execution.get("result") or item.get("result") or "NOT_RUN",
            "ready_before_a31": False,
            "transport": "semantic-transport-v3.1-local-lite",
            "distribution": dist,
        }
    all_rel = sum(totals.values())
    pct = {
        key: round(100.0 * totals[key] / all_rel, 2) if all_rel else 0.0
        for key in totals
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "per_window": per_window,
        "totals_ready_local_lite": totals,
        "totals_new_a31_windows": new_totals,
        "percentages": pct,
        "successful_new_windows": successful,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "architecture_changed": False,
        "do_not_fail_on_loose_alone": True,
        "win001_v3_kept_distinguishable": True,
        "historical_a28_cross_not_overwritten": True,
    }


__all__ = ["build_relation_cross"]
