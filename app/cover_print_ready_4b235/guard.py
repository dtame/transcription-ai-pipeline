"""Fail-closed guards. This phase prints covers and does not call a provider."""

from __future__ import annotations

import ast
from pathlib import Path

from app.cover_print_ready_4b235.constants import (
    AI_GENERATION_AUTHORIZED,
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_BFL_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    NETWORK_CALLS_AUTHORIZED,
)


class CoverPrintReady4235Error(RuntimeError):
    """Print-ready cover phase rejected."""


class ApprovedImageHashError(CoverPrintReady4235Error):
    """The approved front image hash does not match. STOP."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    if text != AUTHORIZATION_SCOPE:
        raise CoverPrintReady4235Error(
            "authorization scope does not match the 4B.2.35 print-ready cover phase"
        )
    return text


def assert_no_provider_calls() -> None:
    if (
        AI_GENERATION_AUTHORIZED
        or NETWORK_CALLS_AUTHORIZED
        or AUTHORIZED_OPENAI_CALLS
        or AUTHORIZED_BFL_CALLS
        or AUTHORIZED_ANTHROPIC_CALLS
        or AUTHORIZED_TERRA_CALLS
    ):
        raise CoverPrintReady4235Error("provider calls are not authorized. STOP.")


def assert_output_allowed(path: Path) -> None:
    text = str(path.resolve()).replace("\\", "/").lower()
    blocked = (
        "/publication/print_review_v1/",
        "/publication/print_review_v1_1/",
        "/covers/generated/",
        "/covers/draft_v1/",
        "/analysis/book.json",
    )
    for token in blocked:
        if token in text:
            raise CoverPrintReady4235Error(
                f"refusing to write into a protected path: {path}. STOP."
            )


def forbidden_imports(package_dir: Path) -> list[str]:
    banned = {
        "requests",
        "openai",
        "anthropic",
        "httpx",
        "torch",
        "diffusers",
        "huggingface_hub",
        "urllib",
        "socket",
    }
    hits: list[str] = []
    for path in package_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name in banned:
                    hits.append(f"{path.name}:{name}")
    return hits


__all__ = [
    "ApprovedImageHashError",
    "CoverPrintReady4235Error",
    "assert_no_provider_calls",
    "assert_output_allowed",
    "forbidden_imports",
    "validate_authorization_scope",
]
