"""4B.2.10 fail-closed guards. Offline only. No Terra authorization."""

from __future__ import annotations

import ast
from pathlib import Path

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b210.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    PRODUCTION_PIPELINE_HOOK,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_201_ACTIVATED,
    PUBLICATION_AUTHORIZED,
    REAL_TERRA_CANARY_AUTHORIZED,
    SEMANTIC_GATE_20_ENABLED,
    SEMANTIC_GATE_201_ENABLED,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_FORBIDDEN_CLIENTS = {"requests", "urllib", "httpx", "openai", "anthropic"}
_FORBIDDEN_ATTR_CALLS = frozenset({"generate", "post", "_invoke"})
_FORBIDDEN_ENGINE_NAMES = frozenset(
    {
        "openai",
        "anthropic",
        "OpenAIEngine",
        "AnthropicEngine",
        "gpt-5.6-terra",
        "claude-sonnet-5",
    }
)


class BookSemanticGate210Error(RuntimeError):
    pass


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise BookSemanticGate210Error(
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


def reject_remote_provider(name: str | None) -> None:
    token = str(name or "").strip()
    if not token:
        return
    lowered = token.lower()
    for forbidden in _FORBIDDEN_ENGINE_NAMES:
        if forbidden.lower() in lowered:
            raise BookSemanticGate210Error(
                "Remote semantic providers are disabled in 4B.2.10. "
                f"Refused provider/engine {token!r}. "
                "API key absence is not the safety mechanism."
            )


def assert_offline_only() -> None:
    imported = package_imports_network_clients()
    if imported:
        raise BookSemanticGate210Error(
            "4B.2.10 must not import a network client: " + ", ".join(imported)
        )
    calls = package_invokes_provider()
    if calls:
        raise BookSemanticGate210Error(
            "4B.2.10 must not call generate/post/_invoke: " + ", ".join(calls)
        )
    if TERRA_EXECUTION_AUTHORIZED:
        raise BookSemanticGate210Error("Terra execution is not authorized in 4B.2.10.")
    if AUTHORIZED_TERRA_CALLS != 0:
        raise BookSemanticGate210Error("AUTHORIZED_TERRA_CALLS must remain 0.")
    if REAL_TERRA_CANARY_AUTHORIZED:
        raise BookSemanticGate210Error("A real Terra canary is not authorized in 4B.2.10.")
    if PUBLICATION_AUTHORIZED:
        raise BookSemanticGate210Error("publication is not authorized")
    if SEMANTIC_GATE_20_ENABLED or SEMANTIC_GATE_201_ENABLED:
        raise BookSemanticGate210Error("Semantic Gate 2.0 must remain disabled.")
    if PRODUCTION_PIPELINE_HOOK:
        raise BookSemanticGate210Error("Production pipeline hook must remain disconnected.")
    if (
        PROMPT_VERSION_20_ACTIVATED
        or PROMPT_VERSION_201_ACTIVATED
        or TRANSPORT_VERSION_20_ACTIVATED
    ):
        raise BookSemanticGate210Error("Contract/transport 2.0 must remain inactive.")
    if not production_book_absent(PROJECT_NAME):
        raise BookSemanticGate210Error("book.json must remain unpublished")


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookSemanticGate210Error(
            f"Production book.json already present at {path}."
        )
    assert_offline_only()


__all__ = [
    "BookSemanticGate210Error",
    "assert_no_publication",
    "assert_offline_only",
    "package_imports_network_clients",
    "package_invokes_provider",
    "reject_remote_provider",
    "validate_authorization_scope",
]
