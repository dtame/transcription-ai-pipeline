"""Garde-fous offline du paquet 3B.7.3 (audit/runner)."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"
_MAIN = Path(__file__).resolve().parents[2] / "main.py"


def package_imports_network_clients() -> list[str]:
    forbidden = {"requests", "urllib", "httpx", "openai", "anthropic"}
    hits: list[str] = []
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                bad = names & forbidden
                if bad:
                    hits.append(f"{path.name}:import {sorted(bad)}")
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in forbidden:
                    hits.append(f"{path.name}:from {root}")
    return hits


def analyzer_wires_orchestrator() -> list[str]:
    text = _ANALYZER.read_text(encoding="utf-8")
    hits: list[str] = []
    for needle in (
        "window_orchestrator",
        "orchestrate_windows",
        "WindowAnalysisOrchestrator",
        "source_analysis_window_orchestration",
        "window_analyzer",
        "analyze_window",
        "source_analysis_hybrid",
        "WindowPlannerV2",
    ):
        if needle in text:
            hits.append(needle)
    return hits


def main_wires_orchestrator() -> list[str]:
    if not _MAIN.is_file():
        return []
    text = _MAIN.read_text(encoding="utf-8")
    hits: list[str] = []
    for needle in (
        "window_orchestrator",
        "orchestrate_windows",
        "source_analysis_window_orchestration",
    ):
        if needle in text:
            hits.append(needle)
    return hits


def assert_offline_package() -> None:
    imported = package_imports_network_clients()
    if imported:
        raise RuntimeError(
            "Le paquet 3B.7.3 ne doit pas importer de client réseau : "
            + ", ".join(imported)
        )


def assert_analyzer_not_wired() -> None:
    hits = analyzer_wires_orchestrator()
    if hits:
        raise RuntimeError(
            "analyzer.py ne doit pas être branché sur l'orchestrateur : "
            + ", ".join(hits)
        )
    main_hits = main_wires_orchestrator()
    if main_hits:
        raise RuntimeError(
            "main.py ne doit pas être branché sur l'orchestrateur : "
            + ", ".join(main_hits)
        )
