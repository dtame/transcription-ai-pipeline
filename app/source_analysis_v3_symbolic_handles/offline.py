"""Garde-fous offline 3B.7.7A.17 phase package. 0 generate/post/_invoke."""

from __future__ import annotations

import ast
from pathlib import Path

from app.source_analysis_local_v3.offline import (
    assert_analyzer_not_wired as assert_v3_analyzer_not_wired,
)
from app.source_analysis_local_v3.offline import assert_offline_package as assert_v3_local_offline

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


def assert_offline_package() -> None:
    imported = package_imports_network_clients()
    if imported:
        raise RuntimeError(
            "Le paquet A.17 ne doit pas importer de client réseau : "
            + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise RuntimeError(
            "Le paquet A.17 ne doit pas appeler generate/post/_invoke : "
            + ", ".join(calls)
        )
    assert_v3_local_offline()


def assert_analyzer_not_wired() -> None:
    assert_v3_analyzer_not_wired()
    text = _ANALYZER.read_text(encoding="utf-8")
    if "source_analysis_v3_symbolic_handles" in text:
        raise RuntimeError("analyzer.py ne doit pas être branché sur A.17")
    if _MAIN.is_file() and "source_analysis_v3_symbolic_handles" in _MAIN.read_text(
        encoding="utf-8"
    ):
        raise RuntimeError("main.py ne doit pas être branché sur A.17")


__all__ = [
    "assert_analyzer_not_wired",
    "assert_offline_package",
    "package_imports_network_clients",
    "package_invokes_provider",
]
