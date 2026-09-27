"""
Grammaire stricte des handles symboliques locaux.

Labels 1-based, typés par préfixe, non canoniques.
Aucune réparation floue. Aucun strip. Aucune conversion T3→I3.
"""

from __future__ import annotations

import re
from typing import Any

TOPIC_HANDLE_RE = re.compile(r"^T[1-9][0-9]*$")
IDEA_HANDLE_RE = re.compile(r"^I[1-9][0-9]*$")

HANDLE_KIND_PREFIX = {
    "TOPIC": "T",
    "IDEA": "I",
}
PREFIX_KIND = {
    "T": "TOPIC",
    "I": "IDEA",
}


def is_topic_handle(value: str) -> bool:
    return isinstance(value, str) and TOPIC_HANDLE_RE.fullmatch(value) is not None


def is_idea_handle(value: str) -> bool:
    return isinstance(value, str) and IDEA_HANDLE_RE.fullmatch(value) is not None


def is_valid_handle(value: str) -> bool:
    return is_topic_handle(value) or is_idea_handle(value)


def handle_kind(value: str) -> str | None:
    if is_topic_handle(value):
        return "TOPIC"
    if is_idea_handle(value):
        return "IDEA"
    return None


def owner_handle_for_kind(kind: str, raw: Any) -> tuple[str | None, str | None]:
    """
    Retourne (handle, error). handle="" pour les kinds sans owner.
    Aucune normalisation.
    """
    if not isinstance(raw, str):
        return None, "h doit être une chaîne"
    if kind in {"TOPIC", "IDEA"}:
        expected = HANDLE_KIND_PREFIX[kind]
        if raw == "":
            return None, f"{kind} exige un handle owner {expected}n"
        if kind == "TOPIC" and not is_topic_handle(raw):
            return None, f"handle owner TOPIC mal formé « {raw} »"
        if kind == "IDEA" and not is_idea_handle(raw):
            return None, f"handle owner IDEA mal formé « {raw} »"
        return raw, None
    if raw != "":
        return None, f"{kind} ne possède pas de handle (h doit être vide)"
    return "", None


def parse_link_handle(raw: Any) -> tuple[str | None, str | None]:
    """Retourne (handle, error). Aucune réparation."""
    if isinstance(raw, bool) or isinstance(raw, int):
        return None, f"handle lien numérique interdit « {raw} » — labels symboliques requis"
    if not isinstance(raw, str):
        return None, f"handle lien doit être une chaîne, reçu {type(raw).__name__}"
    if not is_valid_handle(raw):
        return None, f"handle lien mal formé « {raw} »"
    return raw, None


def recommended_handle(kind: str, ordinal: int) -> str:
    """Label recommandé (1-based) — pas une exigence de validité."""
    if ordinal < 1:
        raise ValueError("les handles recommandés commencent à 1")
    prefix = HANDLE_KIND_PREFIX.get(kind)
    if prefix is None:
        raise ValueError(f"{kind} n'a pas de handle")
    return f"{prefix}{ordinal}"


__all__ = [
    "HANDLE_KIND_PREFIX",
    "IDEA_HANDLE_RE",
    "PREFIX_KIND",
    "TOPIC_HANDLE_RE",
    "handle_kind",
    "is_idea_handle",
    "is_topic_handle",
    "is_valid_handle",
    "owner_handle_for_kind",
    "parse_link_handle",
    "recommended_handle",
]
