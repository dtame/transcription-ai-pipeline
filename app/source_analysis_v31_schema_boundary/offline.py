"""Garde-fous offline 3B.7.7A.26.1. 0 réseau. FakeAI isolé seulement."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"
_MAIN = Path(__file__).resolve().parents[2] / "main.py"
_SCHEMA = Path(__file__).resolve().parents[1] / "source_analysis" / "schema.py"
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})
_FAKEAI_FILES = frozenset({"probes.py", "runner.py"})
_MARKERS = (
    "source_analysis_v31_schema_boundary",
    "source_analysis_v31_local_lite",
    "window-analysis-1.4.0",
    "semantic-transport-v3.1-local-lite",
)


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
        if path.name in _FAKEAI_FILES:
            continue
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
            "Le paquet 3B.7.7A.26.1 ne doit pas importer de client réseau : "
            + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise RuntimeError(
            "Hors FakeAI isolé, le paquet ne doit pas appeler "
            "generate/post/_invoke : " + ", ".join(calls)
        )


def assert_analyzer_not_wired() -> None:
    text = _ANALYZER.read_text(encoding="utf-8")
    for marker in _MARKERS:
        if marker in text:
            raise RuntimeError(f"analyzer.py ne doit pas être branché sur {marker}")
    if _MAIN.is_file():
        main = _MAIN.read_text(encoding="utf-8")
        for marker in _MARKERS:
            if marker in main:
                raise RuntimeError(f"main.py ne doit pas être branché sur {marker}")


def assert_schema_py_untouched() -> None:
    text = _SCHEMA.read_text(encoding="utf-8")
    if 'enum": list(IDEA_KINDS)' not in text:
        raise RuntimeError("schema.py ideas[].kind enum a été modifié")
    if '"kind",' not in text:
        raise RuntimeError("schema.py n'exige plus ideas[].kind")


__all__ = [
    "assert_analyzer_not_wired",
    "assert_offline_package",
    "assert_schema_py_untouched",
    "package_imports_network_clients",
    "package_invokes_provider",
]
