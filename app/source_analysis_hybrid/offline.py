"""Garde-fous offline du paquet 3B.7.1."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"


def package_calls_generate_or_post() -> list[str]:
    hits: list[str] = []
    forbidden = {"generate", "post_json"}
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name in forbidden:
                    hits.append(f"{path.name}:{name}")
    return hits


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


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def analyzer_wires_window_planner() -> list[str]:
    text = _ANALYZER.read_text(encoding="utf-8")
    hits: list[str] = []
    for needle in (
        "source_analysis_hybrid",
        "WindowPlannerV2",
        "window-planner-v2.0",
        "plan_windows_v2",
    ):
        if needle in text:
            hits.append(needle)
    return hits


def assert_offline_package() -> None:
    hits = package_calls_generate_or_post()
    if hits:
        raise RuntimeError(
            "Le paquet 3B.7.1 ne doit pas appeler generate/post_json : "
            + ", ".join(hits)
        )
    imported = package_imports_network_clients()
    if imported:
        raise RuntimeError(
            "Le paquet 3B.7.1 ne doit pas importer de client réseau : "
            + ", ".join(imported)
        )


def assert_analyzer_not_wired() -> None:
    hits = analyzer_wires_window_planner()
    if hits:
        raise RuntimeError(
            "analyzer.py ne doit pas être branché sur WindowPlannerV2 : "
            + ", ".join(hits)
        )
