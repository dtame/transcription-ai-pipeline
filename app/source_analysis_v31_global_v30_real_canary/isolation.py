"""Isolation réseau A.46. Les tests / FakeAI / A.45 ne POSTent pas."""

from __future__ import annotations

import ast
from pathlib import Path

from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    assert_analyzer_not_wired as assert_a45_analyzer_not_wired,
    assert_offline_package as assert_a45_offline_package,
)
from app.source_analysis_v31_global_v30_real_canary.guard import GlobalRealCanaryError

_PACKAGE_DIR = Path(__file__).resolve().parent
_TESTS_DIR = Path(__file__).resolve().parents[1] / "tests"
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"
_MAIN = Path(__file__).resolve().parents[2] / "main.py"
_MARKER = "source_analysis_v31_global_v30_real_canary"
_FORBIDDEN_TEST_CLIENTS = {"anthropic", "openai", "httpx"}
_AUTHORIZED_ENGINE = "engine.py"


def assert_analyzer_not_wired() -> None:
    assert_a45_analyzer_not_wired()
    text = _ANALYZER.read_text(encoding="utf-8")
    if _MARKER in text:
        raise GlobalRealCanaryError(f"analyzer.py must not be wired to {_MARKER}")
    if _MAIN.is_file() and _MARKER in _MAIN.read_text(encoding="utf-8"):
        raise GlobalRealCanaryError(f"main.py must not be wired to {_MARKER}")


def test_modules_import_provider_clients() -> list[str]:
    hits: list[str] = []
    for path in sorted(_TESTS_DIR.glob("test_source_analysis_v31_global_v30_real_canary*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                bad = names & _FORBIDDEN_TEST_CLIENTS
                if bad:
                    hits.append(f"{path.name}:import {sorted(bad)}")
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in _FORBIDDEN_TEST_CLIENTS:
                    hits.append(f"{path.name}:from {root}")
    return hits


def package_posts_outside_engine() -> list[str]:
    hits: list[str] = []
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        if path.name == _AUTHORIZED_ENGINE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"post", "_invoke"}:
                    hits.append(f"{path.name}:{node.func.attr}")
    return hits


def assert_network_isolation() -> None:
    assert_a45_offline_package()
    imported = test_modules_import_provider_clients()
    if imported:
        raise GlobalRealCanaryError(
            "A.46 tests must not import provider HTTP clients: " + ", ".join(imported)
        )
    stray = package_posts_outside_engine()
    if stray:
        raise GlobalRealCanaryError(
            "Only engine.py may POST/_invoke: " + ", ".join(stray)
        )


__all__ = [
    "assert_analyzer_not_wired",
    "assert_network_isolation",
    "package_posts_outside_engine",
    "test_modules_import_provider_clients",
]
