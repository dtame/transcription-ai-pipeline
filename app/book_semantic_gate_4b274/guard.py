"""4B.2.7.4 fail-closed guards. Offline only. No Terra authorization."""

from __future__ import annotations

import ast
from pathlib import Path

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b274.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    PROJECT_NAME,
    PUBLICATION_AUTHORIZED,
    TERRA_EXECUTION_AUTHORIZED,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})


class BookSemanticGate274Error(RuntimeError):
    pass


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise BookSemanticGate274Error(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


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


def assert_offline_only() -> None:
    imported = package_imports_network_clients()
    if imported:
        raise BookSemanticGate274Error(
            "4B.2.7.4 must not import a network client: " + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise BookSemanticGate274Error(
            "4B.2.7.4 must not call generate/post/_invoke: " + ", ".join(calls)
        )
    if TERRA_EXECUTION_AUTHORIZED:
        raise BookSemanticGate274Error("Terra execution is not authorized in 4B.2.7.4.")
    if AUTHORIZED_TERRA_CALLS != 0:
        raise BookSemanticGate274Error("AUTHORIZED_TERRA_CALLS must remain 0.")
    if PUBLICATION_AUTHORIZED:
        raise BookSemanticGate274Error("publication is not authorized")
    if not production_book_absent(PROJECT_NAME):
        raise BookSemanticGate274Error("book.json must remain unpublished")


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookSemanticGate274Error(
            f"Production book.json already present at {path}."
        )
    assert_offline_only()


__all__ = [
    "BookSemanticGate274Error",
    "assert_no_publication",
    "assert_offline_only",
    "package_imports_network_clients",
    "package_invokes_provider",
    "validate_authorization_scope",
]
