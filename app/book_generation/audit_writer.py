"""Write Phase 4B.1 audit artifacts. Never writes book.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generation.constants import (
    AUDIT_ARCHITECTURE,
    AUDIT_BUDGET,
    AUDIT_COST,
    AUDIT_DISTRIBUTION,
    AUDIT_EVIDENCE,
    AUDIT_FAKEAI,
    AUDIT_GENERATION,
    AUDIT_HYDRATION,
    AUDIT_INPUT_CONTRACT,
    AUDIT_OUTPUT_CONTRACT,
    AUDIT_PREFLIGHT,
    AUDIT_PROMPT,
    AUDIT_READINESS,
    AUDIT_SCHEMA,
    AUDIT_TRACEABILITY,
    AUDIT_TRANSPORT,
    BOOK_SCHEMA_VERSION,
    PHASE,
)
from app.book_generation.paths import phase_audit_dir, readiness_path, report_path
from app.book_generation.report import render_report
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def _with_header(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    data.setdefault("schema_version", BOOK_SCHEMA_VERSION)
    data.setdefault("phase", PHASE)
    return data


def write_audit_bundle(
    bundle: Mapping[str, Any],
    *,
    root: Path | None = None,
    tests: str = "offline Phase 4B.1",
) -> dict[str, Path]:
    directory = phase_audit_dir(root=root)
    directory.mkdir(parents=True, exist_ok=True)
    written = {
        "architecture": write_bytes_atomic(
            directory / AUDIT_ARCHITECTURE, _with_header(bundle.get("architecture"))
        ),
        "input_contract": write_bytes_atomic(
            directory / AUDIT_INPUT_CONTRACT, _with_header(bundle.get("input_contract"))
        ),
        "output_contract": write_bytes_atomic(
            directory / AUDIT_OUTPUT_CONTRACT, _with_header(bundle.get("output_contract"))
        ),
        "traceability": write_bytes_atomic(
            directory / AUDIT_TRACEABILITY,
            _with_header(bundle.get("traceability_contract")),
        ),
        "evidence": write_bytes_atomic(
            directory / AUDIT_EVIDENCE, _with_header(bundle.get("evidence_strategy"))
        ),
        "hydration": write_bytes_atomic(
            directory / AUDIT_HYDRATION, _with_header(bundle.get("hydration"))
        ),
        "generation": write_bytes_atomic(
            directory / AUDIT_GENERATION,
            _with_header(bundle.get("generation_strategy")),
        ),
        "schema": write_bytes_atomic(
            directory / AUDIT_SCHEMA, _with_header(bundle.get("schema_identity"))
        ),
        "prompt": write_bytes_atomic(
            directory / AUDIT_PROMPT, _with_header(bundle.get("prompt"))
        ),
        "transport": write_bytes_atomic(
            directory / AUDIT_TRANSPORT, _with_header(bundle.get("transport_identity"))
        ),
        "budget": write_bytes_atomic(
            directory / AUDIT_BUDGET, _with_header(bundle.get("real_corpus_budget"))
        ),
        "distribution": write_bytes_atomic(
            directory / AUDIT_DISTRIBUTION,
            _with_header(bundle.get("chapter_distribution")),
        ),
        "cost": write_bytes_atomic(
            directory / AUDIT_COST, _with_header(bundle.get("cost_estimate"))
        ),
        "fakeai": write_bytes_atomic(
            directory / AUDIT_FAKEAI, _with_header(bundle.get("fakeai"))
        ),
        "preflight": write_bytes_atomic(
            directory / AUDIT_PREFLIGHT, _with_header(bundle.get("preflight"))
        ),
        "readiness": write_bytes_atomic(
            readiness_path(root=root), _with_header(bundle.get("readiness"))
        ),
        "report": write_bytes_atomic(
            report_path(root=root), render_report(bundle, tests=tests)
        ),
    }
    # readiness also copied into the phase directory for the named artifact.
    written["readiness_phase"] = write_bytes_atomic(
        directory / AUDIT_READINESS, _with_header(bundle.get("readiness"))
    )
    return written
