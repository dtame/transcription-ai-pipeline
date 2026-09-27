"""Garde-fous offline du paquet 3B.7.6 (audit/runner)."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"
_MAIN = Path(__file__).resolve().parents[2] / "main.py"
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}


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


def analyzer_wires_hybrid_readiness() -> list[str]:
    text = _ANALYZER.read_text(encoding="utf-8")
    hits: list[str] = []
    for needle in (
        "source_analysis_hybrid_readiness",
        "run_win001_canary",
        "HybridCanonicalReconstructor",
        "source_analysis_window",
        "window-analysis-1.0",
        "WindowPlannerV2",
    ):
        if needle in text:
            hits.append(needle)
    return hits


def main_wires_hybrid_readiness() -> list[str]:
    if not _MAIN.is_file():
        return []
    text = _MAIN.read_text(encoding="utf-8")
    hits: list[str] = []
    for needle in (
        "source_analysis_hybrid_readiness",
        "run_win001_canary",
        "execute-real",
    ):
        if needle in text:
            hits.append(needle)
    return hits


def assert_offline_package() -> None:
    imported = package_imports_network_clients()
    if imported:
        raise RuntimeError(
            "Le paquet 3B.7.6 ne doit pas importer de client réseau : "
            + ", ".join(imported)
        )


def assert_analyzer_not_wired() -> None:
    hits = analyzer_wires_hybrid_readiness()
    if hits:
        raise RuntimeError(
            "analyzer.py ne doit pas être branché sur le runner hybride : "
            + ", ".join(hits)
        )
    main_hits = main_wires_hybrid_readiness()
    if main_hits:
        raise RuntimeError(
            "main.py ne doit pas être branché sur le runner hybride : "
            + ", ".join(main_hits)
        )
