"""Gardes 4A.2 : 0 provider, 0 generate Anthropic, 0 publication."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_preflight_4a2.constants import (
    FORBIDDEN_TECHNICAL_TOKENS,
    FORBIDDEN_WINDOW_IDS,
    MAX_ANTHROPIC_POST,
    MAX_ENGINE_GENERATE,
    REAL_PROVIDER_CALLS_THIS_PHASE,
)
from app.editorial_planning.guard import (
    assert_analyzer_untouched,
    assert_no_book_generator as _assert_no_book_generator_planner,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})
_ALLOWED_GENERATE_FILES = frozenset({"stress.py"})


class PlannerPreflightError(RuntimeError):
    """Échec local 4A.2. Aucun réseau."""


def package_imports_network_clients() -> list[str]:
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
    return hits


def package_invokes_provider() -> list[str]:
    hits: list[str] = []
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        if path.name in _ALLOWED_GENERATE_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _FORBIDDEN_ATTR_CALLS:
                    hits.append(f"{path.name}:{node.func.attr}")
    return hits


def assert_offline_package() -> None:
    if REAL_PROVIDER_CALLS_THIS_PHASE != 0:
        raise PlannerPreflightError("REAL_PROVIDER_CALLS_THIS_PHASE must be 0")
    if MAX_ENGINE_GENERATE != 0:
        raise PlannerPreflightError("MAX_ENGINE_GENERATE must be 0 for A.2")
    if MAX_ANTHROPIC_POST != 0:
        raise PlannerPreflightError("MAX_ANTHROPIC_POST must be 0 for A.2")
    imported = package_imports_network_clients()
    if imported:
        raise PlannerPreflightError(
            "4A.2 ne doit pas importer de client réseau : " + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise PlannerPreflightError(
            "4A.2 ne doit pas appeler generate/post/_invoke hors FakeAI stress : "
            + ", ".join(calls)
        )


def assert_no_book_generator() -> None:
    _assert_no_book_generator_planner(_PACKAGE_DIR)
    _assert_no_book_generator_planner()


def assert_phase3b_untouched() -> None:
    assert_analyzer_untouched()


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


def assert_no_technical_chunks(text: str, *, label: str) -> None:
    hits = scan_technical_chunks(text)
    if hits:
        raise PlannerPreflightError(
            f"Technical window/chunk content in {label}: " + ", ".join(hits)
        )


def redact_secrets(payload: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    for key in ("x-api-key", "api_key", "authorization", "Authorization"):
        cleaned.pop(key, None)
    return cleaned


__all__ = [
    "PlannerPreflightError",
    "assert_no_book_generator",
    "assert_no_technical_chunks",
    "assert_offline_package",
    "assert_phase3b_untouched",
    "redact_secrets",
    "scan_technical_chunks",
]
