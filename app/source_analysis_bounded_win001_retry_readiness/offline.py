"""Garde-fous offline 3B.7.7A.3."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"
_MAIN = Path(__file__).resolve().parents[2] / "main.py"
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})


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
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _FORBIDDEN_ATTR_CALLS:
                    hits.append(f"{path.name}:{node.func.attr}")
    return hits


def analyzer_wires_this_phase() -> list[str]:
    text = _ANALYZER.read_text(encoding="utf-8")
    return [
        needle
        for needle in (
            "source_analysis_bounded_win001_retry_readiness",
            "BOUNDED_WIN001_ONLY",
        )
        if needle in text
    ]


def main_wires_this_phase() -> list[str]:
    if not _MAIN.is_file():
        return []
    text = _MAIN.read_text(encoding="utf-8")
    return [
        needle
        for needle in (
            "source_analysis_bounded_win001_retry_readiness",
            "execute-real",
        )
        if needle in text
    ]


def assert_offline_package() -> None:
    imported = package_imports_network_clients()
    if imported:
        raise RuntimeError(
            "Le paquet 3B.7.7A.3 ne doit pas importer de client réseau : "
            + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise RuntimeError(
            "Le paquet 3B.7.7A.3 ne doit pas appeler generate/post/_invoke : "
            + ", ".join(calls)
        )


def assert_analyzer_not_wired() -> None:
    hits = analyzer_wires_this_phase()
    if hits:
        raise RuntimeError(
            "analyzer.py ne doit pas être branché sur cette revue : "
            + ", ".join(hits)
        )
    main_hits = main_wires_this_phase()
    if main_hits:
        raise RuntimeError(
            "main.py ne doit pas être branché sur cette revue : "
            + ", ".join(main_hits)
        )
