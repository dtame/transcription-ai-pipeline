"""
Sélection de la population COMPLÈTE de cette phase (§2) : tous les blocs
`semantic_review_status == "NEEDED"`, triés par block_id — jamais un
échantillon, à la différence de app.semantic_canary.selection qui choisit
~20 blocs représentatifs pour le canary.

Réutilise app.semantic_canary.models.SelectedBlock comme conteneur : c'est
la même vue (block_id, groupe/raison locaux, dict brut) que le canary, seul
le sens du « groupe » change (ici, un simple marqueur de population, pas une
catégorie d'échantillonnage).
"""

from __future__ import annotations

from app.semantic_batch.errors import SourceIntegrityError
from app.semantic_batch.models import STATUS_NEEDED
from app.semantic_canary.models import SelectedBlock

POPULATION_GROUP = "NEEDED_FULL_POPULATION"


def select_needed_blocks(blocks: list[dict]) -> list[SelectedBlock]:
    """Tous les blocs NEEDED, triés par block_id (ordre déterministe, §13)."""
    needed = sorted(
        (block for block in blocks if block.get("semantic_review_status") == STATUS_NEEDED),
        key=lambda block: str(block["block_id"]),
    )

    return [
        SelectedBlock(
            block_id=str(block["block_id"]),
            selection_group=POPULATION_GROUP,
            selection_reason=(
                "Phase 3A.1.2B : population complète des blocs NEEDED, "
                "ordre déterministe par block_id."
            ),
            raw_block=block,
        )
        for block in needed
    ]


def validate_needed_population(
    selected_blocks: list[SelectedBlock],
    *,
    expected_count: int,
) -> None:
    """
    Contrôle local AVANT tout plan de lots (§2, §14, §17) : STOP AVANT RÉSEAU.

    Vérifie : le compte exact attendu, aucun doublon, aucun bloc dont le
    statut n'est pas NEEDED (donc aucun ALREADY_RESOLVED ni
    NO_ENGLISH_CONTEXT ne s'est glissé dans la population), toutes les
    source_refs et tous les textes reconstructibles — mêmes garanties que le
    canary (§14).
    """
    errors: list[str] = []

    if len(selected_blocks) != expected_count:
        errors.append(
            f"{len(selected_blocks)} bloc(s) sélectionné(s) au lieu de "
            f"{expected_count} attendu(s)."
        )

    ids = [block.block_id for block in selected_blocks]
    duplicates = sorted({block_id for block_id in ids if ids.count(block_id) > 1})
    if duplicates:
        errors.append(f"block_id dupliqué(s) : {duplicates}.")

    for block in selected_blocks:
        if block.semantic_review_status != STATUS_NEEDED:
            errors.append(
                f"{block.block_id} : statut inattendu "
                f"« {block.semantic_review_status} », seul NEEDED est éligible à cette "
                "phase (§2)."
            )

        if not block.fr_source_refs:
            errors.append(f"{block.block_id} : aucune source_ref française.")

        if not str(block.raw_block.get("text", "")).strip():
            errors.append(f"{block.block_id} : texte français vide ou non reconstructible.")

        before = block.english_before
        if before is not None and not (
            before.get("source_refs") and str(before.get("text", "")).strip()
        ):
            errors.append(f"{block.block_id} : english_before invalide (refs ou texte vide).")

        after = block.english_after
        if after is not None and not (
            after.get("source_refs") and str(after.get("text", "")).strip()
        ):
            errors.append(f"{block.block_id} : english_after invalide (refs ou texte vide).")

        if before is None and after is None:
            errors.append(
                f"{block.block_id} : ni english_before ni english_after — aucun contexte "
                "anglais disponible (devrait être NO_ENGLISH_CONTEXT, pas NEEDED)."
            )

    if errors:
        raise SourceIntegrityError(
            "Population NEEDED invalide, STOP AVANT RÉSEAU (§2, §14, §17) : "
            + " | ".join(errors)
        )
