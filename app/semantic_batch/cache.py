"""
Vérification cache/reprise d'un lot déjà écrit sur disque (§18-19).

Un fichier de lot existant n'est un CACHE HIT que si TOUTES les conditions
du §19 sont satisfaites :

    1. la signature déterministe correspond ;
    2. les hashes de source correspondent ;
    3. la version de prompt correspond ;
    4. le provider et le modèle correspondent ;
    5. tous les résultats en cache sont valides contre le contrat local
       (app.semantic_canary.validator, réutilisé tel quel) ;
    6. les block_ids correspondent exactement (ordre et contenu).

Sinon : STOP (CacheSignatureMismatchError) — ne JAMAIS écraser
silencieusement un résultat existant incompatible (§19).
"""

from __future__ import annotations

from app.semantic_batch.errors import CacheSignatureMismatchError
from app.semantic_batch.signature import compute_batch_signature, payload_content_hash
from app.semantic_canary.errors import CanaryResponseValidationError
from app.semantic_canary.models import CanaryClassification
from app.semantic_canary.validator import validate_canary_response


def check_cached_batch(
    cached_payload: dict | None,
    *,
    batch_id: str,
    block_ids: list[str],
    payloads: list[dict],
    language_blocks_sha256: str,
    prompt_version: str,
    response_schema_sha256: str,
    provider: str,
    model: str,
) -> list[CanaryClassification] | None:
    """
    Retourne les classifications si CACHE HIT.

    Retourne None si aucun fichier de lot n'existe encore (première tentative
    légitime, pas une anomalie). Lève CacheSignatureMismatchError si un
    fichier existe mais ne correspond pas exactement à ce qui serait rejoué
    (§19) : c'est un STOP, jamais un second appel silencieux.
    """
    if cached_payload is None:
        return None

    expected_payload_hash = payload_content_hash(payloads)
    expected_signature = compute_batch_signature(
        language_blocks_sha256=language_blocks_sha256,
        prompt_version=prompt_version,
        response_schema_sha256=response_schema_sha256,
        provider=provider,
        model=model,
        block_ids=block_ids,
        payload_hash=expected_payload_hash,
    )

    mismatches: list[str] = []

    if cached_payload.get("batch_id") != batch_id:
        mismatches.append(
            f"batch_id : cache={cached_payload.get('batch_id')!r} != attendu={batch_id!r}."
        )

    if cached_payload.get("signature") != expected_signature:
        mismatches.append(
            "signature : le lot en cache ne correspond pas au plan/contenu actuel."
        )

    cached_hashes = cached_payload.get("source_hashes") or {}
    if cached_hashes.get("language_blocks") != language_blocks_sha256:
        mismatches.append("source_hashes.language_blocks : ne correspond pas à la source actuelle.")

    if cached_payload.get("prompt_version") != prompt_version:
        mismatches.append(
            f"prompt_version : cache={cached_payload.get('prompt_version')!r} "
            f"!= attendu={prompt_version!r}."
        )

    if cached_payload.get("provider") != provider or cached_payload.get("model") != model:
        mismatches.append(
            "provider/model : cache="
            f"{cached_payload.get('provider')!r}/{cached_payload.get('model')!r} "
            f"!= attendu={provider!r}/{model!r}."
        )

    if cached_payload.get("block_ids") != list(block_ids):
        mismatches.append("block_ids : ne correspondent pas exactement (ordre ou contenu).")

    if mismatches:
        raise CacheSignatureMismatchError(
            f"{batch_id} : fichier de lot existant incompatible, STOP (§19) : "
            + " | ".join(mismatches)
        )

    try:
        results = validate_canary_response(
            {"results": cached_payload.get("results")},
            block_ids,
        )
    except CanaryResponseValidationError as exc:
        raise CacheSignatureMismatchError(
            f"{batch_id} : résultats en cache invalides contre le contrat local, "
            f"STOP (§19) : {exc}"
        ) from exc

    return results
