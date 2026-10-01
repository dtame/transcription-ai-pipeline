"""Fail-closed A.3.4 guards: 0 provider calls, no publication, no repair."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_forensics_4a34.constants import (
    FORBIDDEN_TECHNICAL_TOKENS,
    FORBIDDEN_WINDOW_IDS,
    MAX_ANTHROPIC_POST,
    MAX_ENGINE_GENERATE,
    REAL_PROVIDER_CALLS,
)
from app.editorial_planning.guard import (
    assert_analyzer_untouched,
    assert_no_book_generator as _assert_no_book_generator_planner,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})


class PlannerOmissionForensicsError(RuntimeError):
    """Local A.3.4 failure. Never a provider error."""


def assert_zero_provider_imports() -> None:
    hits: list[str] = []
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                bad = names & _FORBIDDEN_CLIENTS
                if bad:
                    hits.append(f"{path.name}:import {sorted(bad)}")
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in _FORBIDDEN_CLIENTS:
                    hits.append(f"{path.name}:from {root}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _FORBIDDEN_ATTR_CALLS:
                    hits.append(f"{path.name}:{node.func.attr}")
    if hits:
        raise PlannerOmissionForensicsError(
            "A.3.4 must not import or invoke a provider: " + ", ".join(hits)
        )


def assert_offline_package() -> None:
    if REAL_PROVIDER_CALLS != 0:
        raise PlannerOmissionForensicsError("REAL_PROVIDER_CALLS must be 0")
    if MAX_ENGINE_GENERATE != 0:
        raise PlannerOmissionForensicsError("MAX_ENGINE_GENERATE must be 0")
    if MAX_ANTHROPIC_POST != 0:
        raise PlannerOmissionForensicsError("MAX_ANTHROPIC_POST must be 0")
    assert_zero_provider_imports()


def assert_no_book_generator() -> None:
    _assert_no_book_generator_planner(_PACKAGE_DIR)
    _assert_no_book_generator_planner()


def assert_phase3b_untouched() -> None:
    assert_analyzer_untouched()


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise PlannerOmissionForensicsError(
            f"Production editorial_plan.json already present at {path}. "
            "A.3.4 must not publish."
        )


def scan_technical_chunks(text: str) -> list[str]:
    blob = str(text or "")
    lowered = blob.lower()
    hits: list[str] = []
    for token in FORBIDDEN_TECHNICAL_TOKENS:
        if token.lower() in lowered:
            hits.append(token)
    for window_id in FORBIDDEN_WINDOW_IDS:
        if window_id.lower() in lowered:
            hits.append(window_id)
    return sorted(set(hits))


def redact_secrets(payload: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    for key in ("x-api-key", "api_key", "authorization", "Authorization"):
        cleaned.pop(key, None)
    return cleaned


__all__ = [
    "PlannerOmissionForensicsError",
    "assert_no_book_generator",
    "assert_no_publication",
    "assert_offline_package",
    "assert_phase3b_untouched",
    "assert_zero_provider_imports",
    "redact_secrets",
    "scan_technical_chunks",
]
