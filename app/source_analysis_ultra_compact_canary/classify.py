"""Classification d'une erreur HTTP Anthropic — grammaire vs schéma vs autre 400."""

from __future__ import annotations

import re

from app.source_analysis_ultra_compact_canary.constants import (
    CLASS_SERVER_GRAMMAR_REJECTED,
    CLASS_SERVER_REQUEST_REJECTED,
    CLASS_SERVER_SCHEMA_REJECTED,
    GRAMMAR_ACCEPTANCE_REJECTED,
    GRAMMAR_ACCEPTANCE_UNKNOWN,
    GRAMMAR_ACCEPTED,
    GRAMMAR_REJECTED,
    GRAMMAR_UNKNOWN,
)

_STATUS_RE = re.compile(r"(?:répondu|responded|status[:\s])\s*(\d{3})", re.IGNORECASE)
_GRAMMAR_RE = re.compile(
    r"compiled grammar is too large|grammar is too large",
    re.IGNORECASE,
)
_SCHEMA_RE = re.compile(
    r"invalid schema|schema is invalid|unsupported[\w\s.-]*schema|"
    r"json[_\s-]?schema|additionalProperties|strict mode",
    re.IGNORECASE,
)
_TYPE_RE = re.compile(r'"type"\s*:\s*"([^"]+)"')
_MESSAGE_LIMIT = 500


def extract_http_status(error: BaseException | str | None) -> int | None:
    if error is None:
        return None
    match = _STATUS_RE.search(str(error))
    if match:
        return int(match.group(1))
    return None


def extract_error_type(error: BaseException | str | None) -> str | None:
    if error is None:
        return None
    text = str(error)
    nested = re.search(r'"error"\s*:\s*\{[^}]*"type"\s*:\s*"([^"]+)"', text)
    if nested:
        return nested.group(1)
    match = _TYPE_RE.search(text)
    if match and match.group(1) != "error":
        return match.group(1)
    if match:
        return match.group(1)
    return type(error).__name__ if not isinstance(error, str) else None


def truncate_error_message(error: BaseException | str | None) -> str:
    if error is None:
        return ""
    text = str(error).strip()
    if len(text) <= _MESSAGE_LIMIT:
        return text
    return text[:_MESSAGE_LIMIT] + "…"


def is_grammar_rejection(error: BaseException | str | None) -> bool:
    if error is None:
        return False
    return bool(_GRAMMAR_RE.search(str(error)))


def is_other_schema_rejection(error: BaseException | str | None) -> bool:
    if error is None or is_grammar_rejection(error):
        return False
    return bool(_SCHEMA_RE.search(str(error)))


def classify_server_error(
    error: BaseException | str | None,
) -> tuple[str, str, str, int | None]:
    """
    Retourne (classification, grammar_result, grammar_acceptance, http_status).

    Une 400 « compiled grammar too large » n'est pas une 400 générique
    et n'est pas une autre incompatibilité de schéma.
    """
    status = extract_http_status(error)
    if is_grammar_rejection(error):
        return (
            CLASS_SERVER_GRAMMAR_REJECTED,
            GRAMMAR_REJECTED,
            GRAMMAR_ACCEPTANCE_REJECTED,
            status if status is not None else 400,
        )
    if is_other_schema_rejection(error):
        return (
            CLASS_SERVER_SCHEMA_REJECTED,
            GRAMMAR_REJECTED,
            GRAMMAR_ACCEPTANCE_REJECTED,
            status if status is not None else 400,
        )
    if status == 400:
        return (
            CLASS_SERVER_REQUEST_REJECTED,
            GRAMMAR_UNKNOWN,
            GRAMMAR_ACCEPTANCE_UNKNOWN,
            status,
        )
    return (
        CLASS_SERVER_REQUEST_REJECTED,
        GRAMMAR_UNKNOWN,
        GRAMMAR_ACCEPTANCE_UNKNOWN,
        status,
    )


def success_grammar() -> tuple[str, str]:
    return GRAMMAR_ACCEPTED, "VERIFIED"
