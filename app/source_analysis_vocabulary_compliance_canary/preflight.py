"""Contrôles offline Prompt 1.3 / contrat lexical / parité — avant tout réseau."""

from __future__ import annotations

from typing import Any, Mapping

from app.file_utils import content_hash
from app.source_analysis.cache import prompt_fingerprint
from app.source_analysis.canonical_vocabulary import (
    CURRENT_PROMPT_VERSION,
    VOCABULARY_BLOCK_BEGIN,
    VOCABULARY_BLOCK_END,
    VOCABULARY_CATEGORY_ORDER,
    build_canonical_vocabulary_contract,
    canonical_allowed_vocabulary,
    extract_prompt_controlled_vocabularies,
    prompt_decoder_parity,
    vocabulary_fallbacks,
)
from app.source_analysis.prompt import (
    SOURCE_ANALYZER_PROMPT_VERSION,
    build_system_prompt,
    build_user_prompt,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_vocabulary_compliance_canary.constants import (
    EXPECTED_PROMPT_VERSION,
    REFERENCE_3B44_PROMPT_SHA256,
)
from app.source_analysis_vocabulary_compliance_canary.errors import (
    PreCallFailure,
    VocabularyParityError,
)

_PROTOCOL_MARKERS = (
    "JETONS DE PROTOCOLE",
    "n'invente aucun synonyme",
    "ne le traduis pas",
    "ne le paraphrase pas",
    "ne remplace pas les underscores",
    "ne crée pas de catégorie plus descriptive",
)


def vocabulary_contract_sha256() -> str:
    return content_hash(build_canonical_vocabulary_contract())


def verify_prompt_version() -> str:
    if SOURCE_ANALYZER_PROMPT_VERSION != EXPECTED_PROMPT_VERSION:
        raise PreCallFailure(
            f"Prompt version {SOURCE_ANALYZER_PROMPT_VERSION!r} "
            f"≠ {EXPECTED_PROMPT_VERSION!r}."
        )
    if CURRENT_PROMPT_VERSION != EXPECTED_PROMPT_VERSION:
        raise PreCallFailure(
            f"CURRENT_PROMPT_VERSION {CURRENT_PROMPT_VERSION!r} "
            f"≠ {EXPECTED_PROMPT_VERSION!r}."
        )
    return SOURCE_ANALYZER_PROMPT_VERSION


def verify_vocabulary_contract_included(system_prompt: str) -> bool:
    contract = build_canonical_vocabulary_contract()
    if contract not in system_prompt:
        raise PreCallFailure(
            "build_canonical_vocabulary_contract() absent du prompt système. "
            "STOP : 0 appel."
        )
    if VOCABULARY_BLOCK_BEGIN not in system_prompt:
        raise PreCallFailure("CONTROLLED_VOCABULARY_BEGIN absent du prompt.")
    if VOCABULARY_BLOCK_END not in system_prompt:
        raise PreCallFailure("CONTROLLED_VOCABULARY_END absent du prompt.")
    return True


def verify_protocol_token_rules(system_prompt: str) -> bool:
    missing = [marker for marker in _PROTOCOL_MARKERS if marker not in system_prompt]
    if missing:
        raise PreCallFailure(
            "Règle de jetons de protocole incomplète : " + ", ".join(missing)
        )
    return True


def verify_fallbacks(system_prompt: str) -> bool:
    for key, fallback in vocabulary_fallbacks().items():
        if f"{key}:" not in system_prompt:
            raise PreCallFailure(f"Vocabulaire {key} absent du prompt.")
        if fallback not in system_prompt:
            raise PreCallFailure(f"Repli de {key} absent du prompt.")
    return True


def verify_vocabulary_parity(system_prompt: str) -> dict[str, list[str]]:
    advertised = extract_prompt_controlled_vocabularies(system_prompt)
    allowed = canonical_allowed_vocabulary()
    missing_from_prompt: list[str] = []
    extra_in_prompt: list[str] = []
    for key in VOCABULARY_CATEGORY_ORDER:
        prompt_values = tuple(advertised.get(key, ()))
        decoder_values = tuple(allowed.get(key, ()))
        missing_from_prompt.extend(
            f"{key}:{value}"
            for value in decoder_values
            if value not in prompt_values
        )
        extra_in_prompt.extend(
            f"{key}:{value}"
            for value in prompt_values
            if value not in decoder_values
        )
    contract_parity = prompt_decoder_parity()
    for key, row in contract_parity.items():
        if row["missing_from_prompt"] or row["extra_in_prompt"]:
            raise VocabularyParityError(
                f"Parité du contrat {key} rompue avant appel."
            )
    if missing_from_prompt or extra_in_prompt:
        raise VocabularyParityError(
            "Parité prompt envoyé / decoder rompue. "
            f"missing_from_prompt={missing_from_prompt} "
            f"extra_in_prompt={extra_in_prompt}"
        )
    return {
        "missing_from_prompt": [],
        "extra_in_prompt": [],
    }


def production_prompt_sha256(transcript: TranscriptInput) -> str:
    """Empreinte Prompt 1.3 sur le transcript chargé — même méthode que 3B.4.4."""
    system = build_system_prompt(transcript.primary_language)
    user = build_user_prompt(transcript)
    return prompt_fingerprint(system, user)


def verify_production_prompt_sha(
    transcript: TranscriptInput,
    *,
    require_historical_match: bool,
) -> str:
    sha = production_prompt_sha256(transcript)
    if require_historical_match and sha != REFERENCE_3B44_PROMPT_SHA256:
        raise PreCallFailure(
            "Prompt 1.3 production SHA ≠ diagnostic 3B.4.4. "
            f"recalculé={sha} attendu={REFERENCE_3B44_PROMPT_SHA256}"
        )
    return sha


def canary_prompt_sha256(system_prompt: str, user_prompt: str) -> str:
    return prompt_fingerprint(system_prompt, user_prompt)


def prompt_preflight_report(
    system_prompt: str,
    *,
    production_sha: str,
    canary_sha: str,
    parity: Mapping[str, list[str]],
) -> dict[str, Any]:
    return {
        "version": SOURCE_ANALYZER_PROMPT_VERSION,
        "production_sha256": production_sha,
        "canary_sha256": canary_sha,
        "vocabulary_contract_sha256": vocabulary_contract_sha256(),
        "vocabulary_contract_included": True,
        "protocol_token_rules": True,
        "fallbacks_present": True,
        "parity": dict(parity),
        "matches_3b44_production_sha": production_sha == REFERENCE_3B44_PROMPT_SHA256,
    }
