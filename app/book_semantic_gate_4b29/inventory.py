"""Technical inventory of the existing semantic-gate stack. Read-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b23.identity import file_identity
from app.book_semantic_gate_4b29.constants import (
    PHASE,
    PROMPT_VERSION_11,
    PROMPT_VERSION_112,
    PROMPT_VERSION_113,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_20_PROPOSAL,
    PROMPT_VERSION_HISTORICAL,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_20_CANDIDATE,
    TRANSPORT_VERSION_20_PROPOSAL,
    TRANSPORT_VERSION_HISTORICAL,
)
from app.book_semantic_gate_4b29.paths import repo_root


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def technical_inventory(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    app = base / "app"
    packages = sorted(
        path.name
        for path in app.glob("book_semantic_gate_*")
        if path.is_dir() and not path.name.endswith("__pycache__")
    )
    tests = sorted(
        path.name
        for path in (app / "tests").glob("test_book_semantic_gate_*.py")
    )
    return {
        "phase": PHASE,
        "project_structure": {
            "semantic_gate_packages": packages,
            "latest_production_like_gate": "app/book_semantic_gate_4b23",
            "prototype_4b28": "app/book_semantic_gate_4b28",
            "candidate_4b29": "app/book_semantic_gate_4b29",
            "book_generator": "app/book_generation",
        },
        "existing_semantic_gate": {
            "independent_gate": "app/book_semantic_gate_4b23",
            "production_helpers": "app/book_generation/semantic_review.py",
            "not_replaced": True,
        },
        "contracts": {
            "1.0": PROMPT_VERSION_HISTORICAL,
            "1.1": PROMPT_VERSION_11,
            "1.1.2": PROMPT_VERSION_112,
            "1.1.3": PROMPT_VERSION_113,
            "2.0_proposal": PROMPT_VERSION_20_PROPOSAL,
            "2.0_candidate": PROMPT_VERSION_20_CANDIDATE,
            "historical_unmodified": True,
        },
        "transports": {
            "1.0": TRANSPORT_VERSION_HISTORICAL,
            "1.1": TRANSPORT_VERSION_11,
            "2.0_proposal": TRANSPORT_VERSION_20_PROPOSAL,
            "2.0_candidate": TRANSPORT_VERSION_20_CANDIDATE,
            "historical_unmodified": True,
        },
        "local_validators": [
            "app/book_semantic_gate_4b23/transport.py",
            "app/book_semantic_gate_4b23/accept.py",
            "app/book_semantic_gate_4b262/contract.py",
            "app/book_semantic_gate_4b274/coverage.py",
            "app/book_semantic_gate_4b29/validator.py",
            "app/book_semantic_gate_4b29/coverage.py",
            "app/book_semantic_gate_4b29/policy.py",
        ],
        "cache": {
            "module": "app/book_generation/cache.py",
            "production_rules_unmodified": True,
            "4b29_does_not_write_cache": True,
        },
        "tests": tests,
        "prototype_4b28": {
            "present": _exists(base, "app/book_semantic_gate_4b28/segmentation.py"),
            "reused": True,
        },
        "historical_audits": {
            "h01": str(file_identity(base / "audit" / "real" / "book_semantic_gate_4b27" / "book_semantic_gate_4b27_raw_structured_response.json")["path"]),
            "h02": str(file_identity(base / "audit" / "real" / "book_semantic_gate_4b273" / "p3_real_raw_structured_response.json")["exists"]),
            "h11": str(file_identity(base / "audit" / "real" / "book_semantic_gate_4b277" / "provider_response_raw.json")["exists"]),
        },
        "versioning_conventions": {
            "phases": "4B.2.N packages as app/book_semantic_gate_4b2N",
            "contracts": "book-semantic-validator-X.Y[-candidate]",
            "transports": "book-semantic-validation-transport-X.Y[-candidate]",
            "audits": "audit/book_semantic_gate_4b2N plus PHASE_4B2N_*.md",
        },
        "reuse": [
            "4b28 prepare_semantic_validation_units",
            "4b23 reason catalog and classifications",
            "4b28 historical canary loaders",
            "4b24 frozen ten-case benchmark",
        ],
        "secrets_included": False,
    }


__all__ = ["technical_inventory"]
