"""Technical inventory of the Semantic Gate 2.0 stack for 4B.2.12. Read-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b23.identity import file_identity
from app.book_semantic_gate_4b210.constants import PROMPT_VERSION_201_CANDIDATE
from app.book_semantic_gate_4b212.constants import (
    PHASE,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_202_CANDIDATE,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b212.paths import (
    historical_4b211_dir,
    historical_h01_dir,
    historical_h02_dir,
    historical_h11_dir,
    historical_raw_response_path,
    repo_root,
)


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def technical_inventory(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    app = base / "app"
    audit = base / "audit"
    packages = sorted(
        path.name
        for path in app.glob("book_semantic_gate_*")
        if path.is_dir() and not path.name.endswith("__pycache__")
    )
    tests = sorted(
        path.name
        for path in (app / "tests").glob("test_book_semantic_gate_*.py")
    )
    reports = {
        "4b29": _exists(base, "audit/PHASE_4B29_SEMANTIC_GATE_20_OFFLINE_IMPLEMENTATION_REPORT.md"),
        "4b210": _exists(base, "audit/PHASE_4B210_SEMANTIC_GATE_20_OFFLINE_CONTRACT_HARDENING_REPORT.md"),
        "4b211": _exists(base, "audit/PHASE_4B211_ONE_REAL_TERRA_SEMANTIC_GATE_20_H01_REPORT.md"),
    }
    h01 = historical_h01_dir(root=root) / "book_semantic_gate_4b27_raw_structured_response.json"
    h02 = historical_h02_dir(root=root) / "p3_real_raw_structured_response.json"
    h11 = historical_h11_dir(root=root) / "provider_response_raw.json"
    raw_4b211 = historical_raw_response_path(root=root)
    contract_201 = historical_4b211_dir(root=root) / "contract_validation.json"
    return {
        "phase": PHASE,
        "examined_reports": reports,
        "examined_packages": {
            "app/book_semantic_gate_4b29": _exists(base, "app/book_semantic_gate_4b29"),
            "app/book_semantic_gate_4b210": _exists(base, "app/book_semantic_gate_4b210"),
            "app/book_semantic_gate_4b211": _exists(base, "app/book_semantic_gate_4b211"),
            "audit/book_semantic_gate_4b29": (audit / "book_semantic_gate_4b29").is_dir(),
            "audit/book_semantic_gate_4b210": (audit / "book_semantic_gate_4b210").is_dir(),
            "audit/real/book_semantic_gate_4b211": historical_4b211_dir(root=root).is_dir(),
        },
        "project_structure": {
            "semantic_gate_packages": packages,
            "candidate_4b29": "app/book_semantic_gate_4b29",
            "hardening_4b210": "app/book_semantic_gate_4b210",
            "real_canary_4b211": "app/book_semantic_gate_4b211",
            "consolidation_4b212": "app/book_semantic_gate_4b212",
            "book_generator": "app/book_generation",
        },
        "contracts": {
            "2.0_candidate": PROMPT_VERSION_20_CANDIDATE,
            "2.0.1_candidate": PROMPT_VERSION_201_CANDIDATE,
            "2.0.2_candidate": PROMPT_VERSION_202_CANDIDATE,
            "exact_contract_used_in_4b211": PROMPT_VERSION_201_CANDIDATE,
            "historical_unmodified": True,
            "2_0_candidate_unmodified": True,
            "2_0_1_candidate_unmodified": True,
            "does_not_overwrite_historical_contracts": True,
        },
        "schema": {
            "transport_20_candidate": "app/book_semantic_gate_4b29/transport.py",
            "transport_version": TRANSPORT_VERSION_20_CANDIDATE,
            "production_structured_output": "json_object",
            "strict_json_schema": "not_activated",
        },
        "validator": {
            "historical_20": "app/book_semantic_gate_4b29/validator.py",
            "used_in_4b211": "app/book_semantic_gate_4b211/validation.py -> validate_response_20",
            "consolidated_202": "app/book_semantic_gate_4b212/validator.py",
            "silent_normalization": False,
        },
        "transport": {
            "version": TRANSPORT_VERSION_20_CANDIDATE,
            "activated": False,
            "production_endpoint": "chat.completions",
        },
        "real_4b211_response": {
            "path": str(raw_4b211).replace("\\", "/"),
            "exists": raw_4b211.is_file(),
            "identity": file_identity(raw_4b211),
            "contract_validation_artifact": file_identity(contract_201),
            "not_modified": True,
        },
        "existing_tests": tests,
        "acceptance_policy": {
            "historical": "app/book_semantic_gate_4b29/policy.py",
            "4b211": "app/book_semantic_gate_4b211/validation.py apply_policy",
            "consolidated_202": "app/book_semantic_gate_4b212/policy.py",
            "fail_closed": True,
        },
        "historical_responses": {
            "h01": file_identity(h01),
            "h02": file_identity(h02),
            "h11": file_identity(h11),
            "4b211": file_identity(raw_4b211),
            "not_modified": True,
        },
        "production": {
            "pipeline_hook": False,
            "cache_acceptance": False,
            "semantic_gate_20_enabled": False,
        },
        "secrets_included": False,
    }


__all__ = ["technical_inventory"]
