"""
Validateur local strict de la réponse du canary (§19).

Ce module ne fait AUCUN appel réseau et ne déclenche JAMAIS un second appel
(§19 : « FAIL, mais NE PAS effectuer un deuxième appel »). Il transforme un
payload décodé (déjà passé par app/ai/structured.py contre le schéma JSON)
en une liste de `CanaryClassification`, ou lève
`CanaryResponseValidationError` avec la liste complète des violations —
jamais la première rencontrée seule, pour qu'une inspection humaine voie
tout d'un coup.
"""

from __future__ import annotations

from typing import Any

from app.semantic_canary.errors import CanaryResponseValidationError
from app.semantic_canary.models import (
    CLASSIFICATIONS,
    EXPECTED_DIRECTION_FOR_CLASSIFICATION,
    MATCHED_DIRECTIONS,
    CanaryClassification,
)

# Clés autorisées dans une entrée `results[]` — §19 : « aucune donnée
# éditoriale supplémentaire ». Une clé en trop est une violation, pas un
# détail ignoré.
_ALLOWED_RESULT_KEYS = frozenset(
    {"block_id", "classification", "matched_direction", "confidence", "reason"}
)


def validate_canary_response(
    payload: Any,
    expected_block_ids: list[str],
) -> list[CanaryClassification]:
    """
    Valide `payload` (déjà décodé JSON) contre le contrat local du canary.

    Lève CanaryResponseValidationError avec TOUTES les violations trouvées
    si le contrat n'est pas respecté. Ne retourne que si la réponse est
    entièrement conforme.
    """
    errors: list[str] = []
    expected = list(expected_block_ids)
    expected_set = set(expected)

    if len(expected_set) != len(expected):
        # Erreur de programmation de l'appelant, pas de la réponse — signalée
        # quand même explicitement plutôt que de produire un diagnostic confus.
        errors.append(
            "expected_block_ids contient des doublons : la sélection en amont "
            "est invalide."
        )

    if not isinstance(payload, dict):
        raise CanaryResponseValidationError(
            [f"La réponse décodée n'est pas un objet JSON (type={type(payload).__name__})."]
        )

    results = payload.get("results")

    if not isinstance(results, list):
        raise CanaryResponseValidationError(
            ["Le champ « results » est absent ou n'est pas une liste."]
        )

    if len(results) != len(expected):
        errors.append(
            f"Nombre de résultats incorrect : {len(results)} reçu(s), "
            f"{len(expected)} attendu(s)."
        )

    seen_ids: dict[str, int] = {}
    classifications: list[CanaryClassification] = []

    for index, entry in enumerate(results):
        prefix = f"results[{index}]"

        if not isinstance(entry, dict):
            errors.append(f"{prefix} n'est pas un objet JSON.")
            continue

        extra_keys = set(entry.keys()) - _ALLOWED_RESULT_KEYS
        if extra_keys:
            errors.append(
                f"{prefix} contient des clés non autorisées : {sorted(extra_keys)}."
            )

        block_id = entry.get("block_id")

        if not isinstance(block_id, str) or not block_id.strip():
            errors.append(f"{prefix}.block_id est absent ou vide.")
            continue

        seen_ids[block_id] = seen_ids.get(block_id, 0) + 1

        if block_id not in expected_set:
            errors.append(
                f"{prefix}.block_id « {block_id} » n'a jamais été soumis au modèle "
                "(block_id inventé)."
            )

        classification = entry.get("classification")
        if classification not in CLASSIFICATIONS:
            errors.append(
                f"{prefix} ({block_id}).classification invalide : {classification!r}. "
                f"Attendu l'un de {list(CLASSIFICATIONS)}."
            )

        matched_direction = entry.get("matched_direction")
        if matched_direction not in MATCHED_DIRECTIONS:
            errors.append(
                f"{prefix} ({block_id}).matched_direction invalide : "
                f"{matched_direction!r}. Attendu l'un de {list(MATCHED_DIRECTIONS)}."
            )
        elif classification in EXPECTED_DIRECTION_FOR_CLASSIFICATION:
            expected_direction = EXPECTED_DIRECTION_FOR_CLASSIFICATION[classification]
            if matched_direction != expected_direction:
                errors.append(
                    f"{prefix} ({block_id}) incohérent : classification="
                    f"{classification} exige matched_direction="
                    f"{expected_direction}, reçu {matched_direction!r}."
                )

        confidence = entry.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            errors.append(
                f"{prefix} ({block_id}).confidence n'est pas un nombre : {confidence!r}."
            )
        elif not (0.0 <= float(confidence) <= 1.0):
            errors.append(
                f"{prefix} ({block_id}).confidence hors bornes [0, 1] : {confidence!r}."
            )

        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix} ({block_id}).reason est absent ou vide.")

    duplicates = sorted(bid for bid, count in seen_ids.items() if count > 1)
    if duplicates:
        errors.append(f"block_id dupliqué(s) dans la réponse : {duplicates}.")

    missing = sorted(expected_set - set(seen_ids))
    if missing:
        errors.append(f"block_id manquant(s) dans la réponse : {missing}.")

    if errors:
        raise CanaryResponseValidationError(errors)

    # Reconstruction finale, uniquement si tout est valide : chaque entrée
    # est désormais garantie conforme au contrat.
    for entry in results:
        classifications.append(
            CanaryClassification(
                block_id=str(entry["block_id"]),
                classification=str(entry["classification"]),
                matched_direction=str(entry["matched_direction"]),
                confidence=float(entry["confidence"]),
                reason=str(entry["reason"]),
            )
        )

    return classifications
