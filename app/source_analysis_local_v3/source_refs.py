"""
Contrat lexical SRC pour semantic-transport-v3.

Grammaire canonique Phase 1 / decoder partagé : ^SRC[0-9]{6}$
Préfixe exact SRC. Largeur 6 chiffres. Aucune normalisation.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from app.source_analysis.window_models import OWNERSHIP_RULE

SRC_LEXICAL_RE = re.compile(r"^SRC[0-9]{6}$")
SRC_CANONICAL_PATTERN = r"^SRC[0-9]{6}$"
SRC_WIDTH = 6
SRC_PREFIX = "SRC"

# Classification only — never used to accept / repair a token.
_ASCII_LETTER_DIGIT_SRC = re.compile(r"^[A-Za-z]{3}[0-9]{6}$")
_DIGIT_RUN = re.compile(r"[0-9]+")
_SRC_LIKE = re.compile(
    r"(?:"
    r"S[Rr][Cc]|s[Rr][Cc]|Src|src|SRC"
    r"|S\uFF32C|ＳRC|ＳＲＣ"
    r")"
    r"[\s\-_]*[0-9]{1,12}"
    r"[A-Za-z0-9]*"
)

_SUBSTANTIVE = frozenset(
    {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY"}
)
_EMPTY_REQUIRED = frozenset({"RELATION"})
_EMPTY_FORBIDDEN = frozenset(_SUBSTANTIVE)


def is_canonical_src(value: Any) -> bool:
    return isinstance(value, str) and SRC_LEXICAL_RE.fullmatch(value) is not None


def classify_src_token(raw: Any) -> str:
    """
    Classe un jeton brut. Ne répare rien. N'appelle pas .upper() pour accepter.
    """
    if not isinstance(raw, str):
        return "not_string"
    if raw != raw.strip() or " " in raw or "\t" in raw or "\n" in raw:
        stripped = raw.strip()
        if is_canonical_src(stripped):
            return "whitespace_mutated"
        return "whitespace_mutated"
    if is_canonical_src(raw):
        return "canonical"
    if "-" in raw or "_" in raw:
        return "separator_mutated"
    if _ASCII_LETTER_DIGIT_SRC.fullmatch(raw):
        prefix = raw[:3]
        digits = raw[3:]
        if prefix != SRC_PREFIX and len(digits) == SRC_WIDTH:
            return "wrong_case"
        return "malformed_lexical"
    digits = _DIGIT_RUN.findall(raw)
    if raw.startswith("SRC") or raw[:3].lower() == "src":
        if digits and len(digits[0]) < SRC_WIDTH:
            return "missing_zeros"
        if digits and len(digits[0]) > SRC_WIDTH:
            return "excessive_digits"
        if raw and raw[-1].isalpha():
            return "non_digit_suffix"
    return "malformed_lexical"


def src_existence(
    token: str,
    *,
    allowed: set[str] | None,
    owned: set[str] | None,
) -> str:
    if not is_canonical_src(token):
        return "not_applicable"
    if allowed is None:
        return "canonical_unscoped"
    if token in allowed:
        if owned is not None and token not in owned:
            return "contextual_not_owned"
        return "owned_or_allowed"
    if owned is not None and token in owned:
        return "owned_or_allowed"
    return "unknown"


def collect_v3_source_refs(
    raw: Any,
    context: str,
    errors: list[str],
    allowed_source_refs: set[str] | None,
) -> list[str]:
    """
    Parse fail-closed. Pas de strip-accept, pas de dedup silencieux,
    pas de .upper(), pas de zero-pad, pas de nearest-SRC.
    """
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        errors.append(f"{context}.s : une liste de chaînes est attendue")
        return []
    refs: list[str] = []
    seen: set[str] = set()
    for position, value in enumerate(raw):
        loc = f"{context}.s[{position}]"
        kind = classify_src_token(value)
        if kind != "canonical":
            shown = value if isinstance(value, str) else type(value).__name__
            errors.append(f"{loc} : source_ref mal formé « {shown} »")
            continue
        assert isinstance(value, str)
        if allowed_source_refs is not None and value not in allowed_source_refs:
            errors.append(f"{loc} : source_ref inconnu « {value} »")
            continue
        if value in seen:
            errors.append(f"{loc} : source_ref dupliqué « {value} »")
            continue
        seen.add(value)
        refs.append(value)
    return refs


def empty_s_permitted(kind: str) -> bool:
    return kind in _EMPTY_REQUIRED or kind not in _EMPTY_FORBIDDEN


def ownership_rule() -> str:
    return OWNERSHIP_RULE


def find_src_like_tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        return [match.group(0) for match in _SRC_LIKE.finditer(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        found: list[str] = []
        for item in value:
            found.extend(find_src_like_tokens(item))
        return found
    return []


def walk_src_like_fields(payload: Any, prefix: str = "") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key == "s" and isinstance(value, list):
                for index, item in enumerate(value):
                    if isinstance(item, str):
                        hits.append({"path": f"{path}[{index}]", "token": item})
                continue
            hits.extend(walk_src_like_fields(value, path))
        return hits
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            hits.extend(walk_src_like_fields(item, f"{prefix}[{index}]"))
        return hits
    if isinstance(payload, str):
        for token in find_src_like_tokens(payload):
            hits.append({"path": prefix, "token": token})
    return hits


def per_kind_empty_s_rules() -> dict[str, str]:
    return {
        "TOPIC": "required_non_empty",
        "IDEA": "required_non_empty",
        "EXAMPLE": "required_non_empty",
        "REFERENCE": "required_non_empty",
        "UNCERTAINTY": "required_non_empty",
        "RELATION": "required_empty — grounding via linked IDEA source_refs",
    }


__all__ = [
    "SRC_CANONICAL_PATTERN",
    "SRC_LEXICAL_RE",
    "SRC_PREFIX",
    "SRC_WIDTH",
    "classify_src_token",
    "collect_v3_source_refs",
    "empty_s_permitted",
    "find_src_like_tokens",
    "is_canonical_src",
    "ownership_rule",
    "per_kind_empty_s_rules",
    "src_existence",
    "walk_src_like_fields",
]
