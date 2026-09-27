"""Vérification offline : decoder fail-closed, aucun alias / fuzzy / synonyme."""

from __future__ import annotations

import inspect
import re

from app.source_analysis import semantic_transport_decoder as decoder_module
from app.source_analysis.canonical_vocabulary import (
    EXACT_IDENTIFIER_EXAMPLES,
    OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS,
)
from app.source_analysis.errors import SourceMapValidationError
from app.source_analysis.semantic_transport_decoder import decode_to_canonical_raw
from app.source_analysis.vocabulary_fixtures import build_observed_3b43_invalid_transport
from app.source_analysis_vocabulary_compliance_canary.errors import PreCallFailure

_FORBIDDEN_REPAIR_MARKERS = (
    "alias_map",
    "synonym_map",
    "fuzzy",
    "casefold",
    "hyphen_normal",
    "translate_token",
    "repair_token",
    "canonicalize_token",
    "TOKEN_ALIASES",
    "SYNONYMS",
)


def decoder_source() -> str:
    return inspect.getsource(decoder_module)


def decoder_is_fail_closed() -> bool:
    source = decoder_source()
    return (
        "SourceMapValidationError" in source
        and "kind inconnu" in source
        and "source_ref inconnu" in source
        and "hors plage" in source
        and callable(decode_to_canonical_raw)
    )


def decoder_has_repair() -> bool:
    source = decoder_source()
    return any(marker in source for marker in _FORBIDDEN_REPAIR_MARKERS)


def decoder_normalizes_tokens() -> bool:
    """True si le decoder semble normaliser casse / tirets des jetons."""
    source = decoder_source()
    # Des .lower() existent peut-être ailleurs ; on cherche un usage sur les kinds.
    return bool(
        re.search(r"(kind|token|value)\.lower\(", source)
        or re.search(r"\.replace\(\s*[\"']-[\"']", source)
    )


def verify_decoder_integrity() -> dict[str, bool]:
    fail_closed = decoder_is_fail_closed()
    has_repair = decoder_has_repair()
    normalizes = decoder_normalizes_tokens()
    if not fail_closed:
        raise PreCallFailure("Le decoder n'est plus fail-closed. STOP : 0 appel.")
    if has_repair:
        raise PreCallFailure(
            "Le decoder contient un marqueur d'alias / synonyme / fuzzy. "
            "STOP : 0 appel."
        )
    if normalizes:
        raise PreCallFailure(
            "Le decoder normalise encore les jetons. STOP : 0 appel."
        )
    return {
        "fail_closed": True,
        "aliases": False,
        "synonym_map": False,
        "fuzzy_repair": False,
        "case_normalization": False,
        "hyphen_normalization": False,
        "translation_mapping": False,
    }


def observed_3b43_tokens_still_rejected() -> bool:
    payload = build_observed_3b43_invalid_transport("SRC000001")
    try:
        decode_to_canonical_raw(payload, allowed_source_refs={"SRC000001"})
    except SourceMapValidationError as exc:
        joined = " ".join(exc.errors)
        return all(token in joined for token in OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS)
    return False


def examples_are_not_a_repair_table() -> bool:
    """Les exemples WRONG→VALID du prompt ne sont pas une table de decoder."""
    source = decoder_source()
    for wrong, valid in EXACT_IDENTIFIER_EXAMPLES:
        if wrong in source:
            return False
        if f'"{valid}"' in source and "UNCERTAINTY_KINDS" not in source:
            return False
    return True
