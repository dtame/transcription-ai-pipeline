"""Gardes-fous offline 3B.7.7A.49. 0 réseau. 0 generate/post/_invoke."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"
_MAIN = Path(__file__).resolve().parents[2] / "main.py"
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})
_MARKERS = (
    "source_analysis_v31_global_a49_source_map_publication",
    "source_analysis_v31_global_a48_offline_revalidation",
    "source_analysis_v31_global_a47_contract_forensics",
    "source_analysis_v31_global_v30_real_canary",
    "source_analysis_v31_global_v30_exact_preflight",
    "source_analysis_v31_global_reuse_output",
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
            "Le paquet 3B.7.7A.49 ne doit pas importer de client réseau : "
            + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise RuntimeError(
            "Le paquet ne doit pas appeler generate/post/_invoke : "
            + ", ".join(calls)
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


def assert_no_phase4_artifacts(package_dir: Path | None = None) -> None:
    directory = package_dir or _PACKAGE_DIR
    forbidden = (
        "def build_editorial_plan",
        "class EditorialPlanner",
        "class BookGenerator",
        'write_bytes_atomic(artifact_path(project_name, "editorial_plan.json"',
        "chapter_plans =",
        "section_plans =",
    )
    hits: list[str] = []
    for path in sorted(directory.glob("*.py")):
        if path.name == "offline.py":
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                hits.append(f"{path.name}:{token}")
    if hits:
        raise RuntimeError("A.49 ne doit pas contenir de code Phase 4 : " + ", ".join(hits))


__all__ = [
    "assert_analyzer_not_wired",
    "assert_no_phase4_artifacts",
    "assert_offline_package",
    "package_imports_network_clients",
    "package_invokes_provider",
]
