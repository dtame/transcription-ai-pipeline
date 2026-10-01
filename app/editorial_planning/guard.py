"""Gardes-fous Phase 4A : 0 provider, 0 publication, 0 Book Generator."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})
# runner.py appelle FakeAIEngine.generate uniquement — jamais Anthropic/OpenAI.
_ALLOWED_GENERATE_FILES = frozenset({"runner.py"})
_ANALYZER = Path(__file__).resolve().parents[1] / "source_analysis" / "analyzer.py"


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
    imported = package_imports_network_clients()
    if imported:
        raise RuntimeError(
            "editorial_planning ne doit pas importer de client réseau : "
            + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise RuntimeError(
            "editorial_planning ne doit pas appeler generate/post/_invoke : "
            + ", ".join(calls)
        )


def assert_analyzer_untouched() -> None:
    text = _ANALYZER.read_text(encoding="utf-8")
    if "editorial_planning" in text:
        raise RuntimeError("analyzer.py ne doit pas être branché sur editorial_planning")


def assert_no_book_generator(package_dir: Path | None = None) -> None:
    directory = package_dir or _PACKAGE_DIR
    forbidden = (
        "class BookGenerator",
        "def generate_book",
        "book.json",
        "book.md",
        "book.docx",
        "book.pdf",
    )
    hits: list[str] = []
    for path in sorted(directory.glob("*.py")):
        if path.name in {"guard.py", "constants.py", "errors.py", "report.py", "runner.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                hits.append(f"{path.name}:{token}")
    if hits:
        raise RuntimeError("Phase 4A ne doit pas contenir de Book Generator : " + ", ".join(hits))
