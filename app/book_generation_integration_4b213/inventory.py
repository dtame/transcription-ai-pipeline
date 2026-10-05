"""Read-only technical inventory of real Book Generator and Semantic Gate paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_generation_integration_4b213.constants import (
    CODE_VERSION,
    PHASE,
    PROMPT_VERSION_202_CANDIDATE,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_generation_integration_4b213.paths import repo_root


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def technical_inventory(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    app = base / "app"
    tests = sorted(
        path.name
        for path in (app / "tests").glob("test_book_*.py")
    )
    gate_packages = sorted(
        path.name
        for path in app.glob("book_semantic_gate_*")
        if path.is_dir() and not path.name.endswith("__pycache__")
    )
    return {
        "phase": PHASE,
        "examined_reports": {
            "4b212": _exists(
                base,
                "audit/PHASE_4B212_SEMANTIC_GATE_20_CONSOLIDATION_AND_INTEGRATION_DECISION_REPORT.md",
            ),
            "4b211": _exists(
                base,
                "audit/PHASE_4B211_ONE_REAL_TERRA_SEMANTIC_GATE_20_H01_REPORT.md",
            ),
            "4b29": _exists(
                base,
                "audit/PHASE_4B29_SEMANTIC_GATE_20_OFFLINE_IMPLEMENTATION_REPORT.md",
            ),
        },
        "book_generator": {
            "package": "app/book_generation",
            "entry": "app/book_generation/__main__.py",
            "runner": "app/book_generation/runner.py",
            "chapter_orchestration": "app/book_generation/pipeline.py materialize_chapter",
            "generation_unit": "one_chapter_per_call (STRATEGY_CHAPTER)",
            "models": "app/book_generation/models.py ChapterCandidate BookChapter BookSection BookParagraph",
            "structural_validator": "app/book_generation/validator.py validate_chapter_candidate",
            "cache": "app/book_generation/cache.py ChapterCache GenerationState",
            "resume": "app/book_generation/cache.py GenerationState.reusable",
            "errors": "app/book_generation/errors.py",
            "final_document": "app/book_generation/writer.py write_book (blocked); book.json unpublished",
            "fakeai": "app/book_generation/fakeai.py",
            "costing": "app/book_generation/costing.py",
            "semantic_helpers": "app/book_generation/semantic_review.py (deterministic phrases, not Gate 2.0)",
            "exists": _exists(base, "app/book_generation/pipeline.py"),
        },
        "semantic_gate_20": {
            "candidate_package": "app/book_semantic_gate_4b29",
            "contract_202": "app/book_semantic_gate_4b212/contract.py",
            "validator_202": "app/book_semantic_gate_4b212/validator.py",
            "policy_202": "app/book_semantic_gate_4b212/policy.py",
            "preparation": "app/book_semantic_gate_4b29/preparation.py -> app/book_semantic_gate_4b28/segmentation.py",
            "coverage": "app/book_semantic_gate_4b29/coverage.py",
            "transport": TRANSPORT_VERSION_20_CANDIDATE,
            "contract": PROMPT_VERSION_202_CANDIDATE,
            "disconnected_hook": "app/book_semantic_gate_4b29/integration.py SemanticGate20IntegrationCandidate.enabled=False",
            "packages": gate_packages,
        },
        "this_phase": {
            "module": CODE_VERSION,
            "isolated": True,
            "connected_to_production_pipeline": False,
        },
        "existing_tests": tests,
        "does_not_invent_function_names": True,
        "secrets_included": False,
    }


__all__ = ["technical_inventory"]
