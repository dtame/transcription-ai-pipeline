"""4B.2.1 guards. Offline only. No historical repair. No publication."""

from __future__ import annotations

import ast
from pathlib import Path

from app.book_generation.writer import production_book_absent
from app.book_generator_forensics_4b21.constants import (
    PROJECT_NAME,
    PUBLICATION_AUTHORIZED,
    REAL_PROVIDER_CALLS,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})


class BookGeneratorForensicsError(RuntimeError):
    pass


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
        raise BookGeneratorForensicsError(
            "4B.2.1 must not import a network client: " + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise BookGeneratorForensicsError(
            "4B.2.1 must not call generate/post/_invoke: " + ", ".join(calls)
        )
    if REAL_PROVIDER_CALLS != 0:
        raise BookGeneratorForensicsError("REAL_PROVIDER_CALLS must remain 0")
    if PUBLICATION_AUTHORIZED:
        raise BookGeneratorForensicsError("publication is not authorized")
    if not production_book_absent(PROJECT_NAME):
        raise BookGeneratorForensicsError("book.json must remain unpublished")


__all__ = [
    "BookGeneratorForensicsError",
    "assert_offline_package",
    "package_imports_network_clients",
    "package_invokes_provider",
]
