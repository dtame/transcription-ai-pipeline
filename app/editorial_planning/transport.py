"""Décodage du transport provider. Pas de json.loads métier hors structured.py."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.editorial_planning.errors import EditorialPlanTransportError
from app.editorial_planning.models import scan_forbidden_plan_structure

_TOP_LEVEL = frozenset(
    {
        "concept",
        "titles",
        "pick",
        "subtitle",
        "angle",
        "reader",
        "strategy",
        "chapters",
        "deferred",
        "excluded",
    }
)
_CONCEPT = frozenset({"promise", "subject", "journey", "progression"})
_TITLE = frozenset({"t", "why"})
_CHAPTER = frozenset({"h", "t", "p", "sum", "top", "act", "sections"})
_SECTION = frozenset({"h", "t", "p", "i", "x", "ref", "u", "rep", "top", "act"})
_ACTION = frozenset({"k", "n"})
_COVERAGE = frozenset({"id", "why", "n"})


def decode_transport(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise EditorialPlanTransportError(
            [f"transport inattendu : {type(payload).__name__}"]
        )
    leaked = scan_forbidden_plan_structure(payload)
    if leaked:
        raise EditorialPlanTransportError(
            [f"structure interdite dans le transport : {name}" for name in leaked]
        )
    errors: list[str] = []
    _reject_unknown(payload, _TOP_LEVEL, "transport", errors)
    concept = payload.get("concept")
    if not isinstance(concept, Mapping):
        errors.append("concept manquant")
    else:
        _reject_unknown(concept, _CONCEPT, "concept", errors)
    titles = _as_list(payload.get("titles"), "titles", errors)
    for index, title in enumerate(titles):
        if isinstance(title, Mapping):
            _reject_unknown(title, _TITLE, f"titles[{index}]", errors)
    chapters = _as_list(payload.get("chapters"), "chapters", errors)
    for c_index, chapter in enumerate(chapters):
        if not isinstance(chapter, Mapping):
            errors.append(f"chapters[{c_index}] n'est pas un objet")
            continue
        _reject_unknown(chapter, _CHAPTER, f"chapters[{c_index}]", errors)
        sections = _as_list(
            chapter.get("sections"), f"chapters[{c_index}].sections", errors
        )
        for s_index, section in enumerate(sections):
            if not isinstance(section, Mapping):
                errors.append(
                    f"chapters[{c_index}].sections[{s_index}] n'est pas un objet"
                )
                continue
            _reject_unknown(
                section, _SECTION, f"chapters[{c_index}].sections[{s_index}]", errors
            )
            _check_actions(
                section.get("act"),
                f"chapters[{c_index}].sections[{s_index}].act",
                errors,
            )
        _check_actions(chapter.get("act"), f"chapters[{c_index}].act", errors)
    for label in ("deferred", "excluded"):
        rows = _as_list(payload.get(label), label, errors)
        for index, row in enumerate(rows):
            if isinstance(row, Mapping):
                _reject_unknown(row, _COVERAGE, f"{label}[{index}]", errors)
    if errors:
        raise EditorialPlanTransportError(errors)
    return dict(payload)


def _check_actions(value: Any, path: str, errors: list[str]) -> None:
    if value is None:
        return
    rows = _as_list(value, path, errors)
    for index, row in enumerate(rows):
        if isinstance(row, Mapping):
            _reject_unknown(row, _ACTION, f"{path}[{index}]", errors)


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
