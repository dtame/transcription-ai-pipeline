"""
Planification déterministe des lots (§13-17), EN MÉMOIRE, avant tout appel
réseau.

Algorithme glouton, à une seule passe, sur les blocs déjà triés par
block_id (app.semantic_batch.selection.select_needed_blocks) :

    on ajoute les blocs un par un au lot courant ;
    un lot se ferme dès qu'il atteint MAX_BLOCKS_PER_BATCH (20, §13) OU dès
    que l'ajout du bloc suivant dépasserait MAX_ESTIMATED_TOKENS_PER_BATCH
    (§16 : « réduire le nombre de blocs de CE batch », jamais tronquer un
    bloc) ;
    un lot ne contient donc jamais plus de 20 blocs, et peut en contenir
    moins si un très gros bloc l'exigeait — mais jamais zéro : un bloc, même
    surdimensionné seul, forme son propre lot plutôt que d'être perdu ou
    tronqué (§16).

Ordre toujours déterministe (§13) : jamais de mélange aléatoire.
"""

from __future__ import annotations

from app.ai.estimation import estimate_tokens
from app.semantic_batch.errors import BatchPlanError
from app.semantic_batch.models import MAX_BLOCKS_PER_BATCH, BatchPlanItem, batch_id_for_index
from app.semantic_canary import payload as payload_module
from app.semantic_canary import prompt as prompt_module
from app.semantic_canary.models import SelectedBlock

# Budget prudent et documenté (§16) : une borne large pour ne jamais forcer
# une réduction en fonctionnement normal. Le plus gros bloc réel connu du
# corpus (FRB0108, 565 mots) tient déjà, aux côtés de 19 autres blocs, dans
# un lot dont l'appel réel a consommé ~8623 tokens d'entrée (Phase 3A.1.2A).
# Cette constante protège seulement le cas pathologique d'un lot qui
# enchaînerait plusieurs blocs exceptionnellement longs.
MAX_ESTIMATED_TOKENS_PER_BATCH = 12_000


def _rendered_block_tokens(block: SelectedBlock) -> int:
    """Estimation locale (heuristique) du coût en tokens d'UN bloc rendu."""
    payload = payload_module.build_block_payload(block)
    rendered = prompt_module.render_block_payload(payload)
    return estimate_tokens(rendered).tokens


def build_batch_plan(
    selected_blocks: list[SelectedBlock],
    *,
    max_batch_size: int = MAX_BLOCKS_PER_BATCH,
    max_estimated_tokens: int = MAX_ESTIMATED_TOKENS_PER_BATCH,
) -> list[BatchPlanItem]:
    """
    Construit le plan complet de lots, EN MÉMOIRE (§17).

    Ordre déterministe : celui de `selected_blocks` (déjà trié par
    block_id). Ne mélange jamais aléatoirement (§13).
    """
    if max_batch_size < 1:
        raise BatchPlanError(f"max_batch_size doit être >= 1 : {max_batch_size}")

    plan: list[BatchPlanItem] = []
    current: list[SelectedBlock] = []
    current_tokens = 0

    def _flush() -> None:
        nonlocal current, current_tokens
        if current:
            plan.append(
                BatchPlanItem(
                    batch_id=batch_id_for_index(len(plan) + 1),
                    blocks=tuple(current),
                    estimated_input_tokens=current_tokens,
                )
            )
            current = []
            current_tokens = 0

    for block in selected_blocks:
        block_tokens = _rendered_block_tokens(block)

        would_exceed_size = len(current) + 1 > max_batch_size
        would_exceed_tokens = bool(current) and (
            current_tokens + block_tokens > max_estimated_tokens
        )

        if current and (would_exceed_size or would_exceed_tokens):
            _flush()

        current.append(block)
        current_tokens += block_tokens

    _flush()

    return plan


def validate_batch_plan(
    plan: list[BatchPlanItem],
    selected_blocks: list[SelectedBlock],
    *,
    max_batch_size: int = MAX_BLOCKS_PER_BATCH,
) -> None:
    """
    Contrôle local du plan AVANT tout appel réseau (§17) : STOP AVANT RÉSEAU.

    Vérifie : chaque bloc de la population apparaît exactement une fois dans
    le plan (aucun doublon, aucune omission, aucun ID inventé), aucun lot ne
    dépasse `max_batch_size`, aucun lot vide, et les IDs de lot sont
    séquentiels (BATCH001, BATCH002, ...).
    """
    errors: list[str] = []

    expected_ids = [block.block_id for block in selected_blocks]
    expected_set = set(expected_ids)

    plan_ids: list[str] = []
    for item in plan:
        plan_ids.extend(item.block_ids)

        if item.block_count == 0:
            errors.append(f"{item.batch_id} : lot vide.")

        if item.block_count > max_batch_size:
            errors.append(
                f"{item.batch_id} : {item.block_count} bloc(s), dépasse "
                f"max_batch_size={max_batch_size}."
            )

    duplicates = sorted({bid for bid in plan_ids if plan_ids.count(bid) > 1})
    if duplicates:
        errors.append(f"block_id dupliqué(s) entre lots : {duplicates}.")

    missing = sorted(expected_set - set(plan_ids))
    if missing:
        errors.append(f"block_id omis du plan : {missing}.")

    unexpected = sorted(set(plan_ids) - expected_set)
    if unexpected:
        errors.append(f"block_id inattendu(s) dans le plan (jamais soumis) : {unexpected}.")

    expected_batch_ids = [batch_id_for_index(i) for i in range(1, len(plan) + 1)]
    actual_batch_ids = [item.batch_id for item in plan]
    if actual_batch_ids != expected_batch_ids:
        errors.append(
            f"IDs de lot non séquentiels : {actual_batch_ids} != {expected_batch_ids}."
        )

    if errors:
        raise BatchPlanError(
            "Plan de lots invalide, STOP AVANT RÉSEAU (§17) : " + " | ".join(errors)
        )
