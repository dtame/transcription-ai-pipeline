"""Decode book-generation-transport-1.0. No service json.loads of provider text."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_generation.errors import BookGenerationTransportError
from app.book_generation.models import scan_forbidden_book_structure

_TOP_LEVEL = frozenset({"sections"})
_SECTION = frozenset({"sid", "paras"})
_PARAGRAPH = frozenset({"h", "k", "t", "e", "u"})


def decode_transport(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise BookGenerationTransportError(
            [f"transport inattendu : {type(payload).__name__}"]
        )
    leaked = scan_forbidden_book_structure(payload)
    if leaked:
        raise BookGenerationTransportError(
            [f"structure interdite dans le transport : {name}" for name in leaked]
        )
    errors: list[str] = []
    _reject_unknown(payload, _TOP_LEVEL, "transport", errors)
    sections = _as_list(payload.get("sections"), "sections", errors)
    if not sections:
        errors.append("sections manquant")
    for s_index, section in enumerate(sections):
        if not isinstance(section, Mapping):
            errors.append(f"sections[{s_index}] n'est pas un objet")
            continue
        _reject_unknown(section, _SECTION, f"sections[{s_index}]", errors)
        paras = _as_list(section.get("paras"), f"sections[{s_index}].paras", errors)
        if not paras:
            errors.append(f"sections[{s_index}].paras vide")
        for p_index, para in enumerate(paras):
            if not isinstance(para, Mapping):
                errors.append(
                    f"sections[{s_index}].paras[{p_index}] n'est pas un objet"
                )
                continue
            _reject_unknown(
                para, _PARAGRAPH, f"sections[{s_index}].paras[{p_index}]", errors
            )
    if errors:
        raise BookGenerationTransportError(errors)
    return dict(payload)


def _as_list(value: Any, path: str, errors: list[str]) -> list:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        errors.append(f"{path} doit être un tableau")
        return []
    return list(value)


def _reject_unknown(
    payload: Mapping[str, Any],
    allowed: frozenset[str],
    path: str,
    errors: list[str],
) -> None:
    extra = sorted(str(key) for key in payload.keys() if str(key) not in allowed)
    for key in extra:
        errors.append(f"champ inconnu {path}.{key}")
