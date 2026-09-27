"""
Garde-fous offline du paquet 3B.7.

Aucun engine.generate(), aucun post_json, aucun réseau.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent


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


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def assert_offline_package() -> None:
    hits = package_calls_generate_or_post()
    if hits:
        raise RuntimeError(
            "Le paquet 3B.7 ne doit pas appeler generate/post_json : "
            + ", ".join(hits)
        )
