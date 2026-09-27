"""Garde-fous offline 3B.7.7A.11. 0 réseau. 0 generate/post/_invoke."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"
_MAIN = Path(__file__).resolve().parents[2] / "main.py"
_WINDOW_PROMPT = (
    Path(__file__).resolve().parents[1] / "source_analysis" / "window_prompt.py"
)
_ULTRA = (
    Path(__file__).resolve().parents[1] / "source_analysis" / "ultra_compact_schema.py"
)
_GRANULARITY = (
    Path(__file__).resolve().parents[1] / "source_analysis" / "window_granularity.py"
)
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
        if path.name in {"pipeline.py", "e2e.py", "fixtures.py"}:
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
            "Le paquet 3B.7.7A.11 ne doit pas importer de client réseau : "
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
    if "source_analysis_local_v2" in text:
        raise RuntimeError("analyzer.py ne doit pas être branché sur local_v2")
    if _MAIN.is_file() and "source_analysis_local_v2" in _MAIN.read_text(
        encoding="utf-8"
    ):
        raise RuntimeError("main.py ne doit pas être branché sur local_v2")


def historical_contract_paths() -> dict[str, Path]:
    return {
        "window_prompt": _WINDOW_PROMPT,
        "ultra_compact_schema": _ULTRA,
        "window_granularity": _GRANULARITY,
        "analyzer": _ANALYZER,
        "main": _MAIN,
    }
