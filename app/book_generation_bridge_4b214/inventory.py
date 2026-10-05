"""Read-only technical inventory of real Book Generator, Gate, and 4B.2.13 paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_generation.cache import ChapterCache, GenerationState
from app.book_generation.pipeline import assemble_book, materialize_chapter, remember_chapter
from app.book_generation_bridge_4b214.constants import (
    CODE_VERSION,
    PHASE,
    PROMPT_VERSION_202_CANDIDATE,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_generation_bridge_4b214.paths import repo_root
from app.book_generation_integration_4b213.orchestrator import orchestrate_chapter
from app.book_semantic_gate_4b29.integration import SemanticGate20IntegrationCandidate
from app.book_semantic_gate_4b212.validator import validate_response_202


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def technical_inventory(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    app = base / "app"
    tests = sorted(path.name for path in (app / "tests").glob("test_book_*.py"))
    gate_packages = sorted(
        path.name
        for path in app.glob("book_semantic_gate_*")
        if path.is_dir() and not path.name.endswith("__pycache__")
    )
    return {
        "phase": PHASE,
        "examined_reports": {
            "4b213": _exists(
                base,
                "audit/PHASE_4B213_BOOK_GENERATOR_SEMANTIC_GATE_20_CONTROLLED_INTEGRATION_PREFLIGHT_REPORT.md",
            ),
            "4b212": _exists(
                base,
                "audit/PHASE_4B212_SEMANTIC_GATE_20_CONSOLIDATION_AND_INTEGRATION_DECISION_REPORT.md",
            ),
            "4b211": _exists(
                base,
                "audit/PHASE_4B211_ONE_REAL_TERRA_SEMANTIC_GATE_20_H01_REPORT.md",
            ),
        },
        "book_generator": {
            "package": "app/book_generation",
            "pipeline": "app.book_generation.pipeline",
            "materialize_chapter": f"{materialize_chapter.__module__}.{materialize_chapter.__name__}",
            "assemble_book": f"{assemble_book.__module__}.{assemble_book.__name__}",
            "remember_chapter": f"{remember_chapter.__module__}.{remember_chapter.__name__}",
            "models": "app.book_generation.models ChapterCandidate BookChapter BookSection BookParagraph BookIdentity",
            "structural_validator": "app.book_generation.validator.validate_chapter_candidate",
            "cache": f"{ChapterCache.__module__}.{ChapterCache.__name__}",
            "resume": f"{GenerationState.__module__}.{GenerationState.__name__}",
            "evidence": "app.book_generation.evidence.build_chapter_evidence",
            "hydrate": "app.book_generation.hydrate.hydrate_src_ids",
            "budget": "app.book_generation.budget.measure_request_budget",
            "costing": "app.book_generation.costing.estimate_production_cost",
            "runner": "app.book_generation.runner",
            "generation_unit": "one_chapter_per_call (STRATEGY_CHAPTER)",
            "exists": _exists(base, "app/book_generation/pipeline.py"),
        },
        "semantic_gate_20": {
            "candidate_package": "app/book_semantic_gate_4b29",
            "contract_202": "app.book_semantic_gate_4b212.contract.semantic_contract_202_candidate",
            "validator_202": f"{validate_response_202.__module__}.{validate_response_202.__name__}",
            "policy_202": "app.book_semantic_gate_4b212.policy.apply_acceptance_policy_202",
            "preparation": "app.book_semantic_gate_4b29.preparation.prepare_paragraph_units",
            "coverage": "app.book_semantic_gate_4b29.coverage.validate_prepared_coverage",
            "request_builder": "app.book_semantic_gate_4b29.request.build_model_request",
            "transport": TRANSPORT_VERSION_20_CANDIDATE,
            "contract": PROMPT_VERSION_202_CANDIDATE,
            "disconnected_hook": (
                f"{SemanticGate20IntegrationCandidate.__module__}."
                "SemanticGate20IntegrationCandidate.enabled=False"
            ),
            "packages": gate_packages,
        },
        "isolated_integration_4b213": {
            "package": "app/book_generation_integration_4b213",
            "orchestrate_chapter": (
                f"{orchestrate_chapter.__module__}.{orchestrate_chapter.__name__}"
            ),
            "contract": "book-generator-semantic-gate-integration-4b213-candidate",
            "isolated": True,
            "connected_to_production_pipeline": False,
        },
        "this_phase": {
            "module": CODE_VERSION,
            "isolated": True,
            "enabled_by_default": False,
            "connected_to_production_pipeline": False,
        },
        "existing_tests": tests,
        "does_not_invent_function_names": True,
        "secrets_included": False,
    }


__all__ = ["technical_inventory"]
