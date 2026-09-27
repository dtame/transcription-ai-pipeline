"""
Sélection déterministe des ~20 blocs du canary (§13-14).

Algorithme volontairement simple et documentable : chaque groupe (A/B/C) est
un échantillonnage PAR PAS (« stride sampling ») sur un bassin de candidats
trié par `block_id` (donc par ordre d'apparition chronologique, voir
app/language_blocks/builder.py). Le groupe D (atypique) est constitué de
cinq règles ciblées, chacune déterministe.

Ce module ne lit AUCUN fichier : il opère sur la liste `blocks` déjà décodée
de language_blocks.json. C'est ce qui le rend testable sans fixture disque
(cf. §30.1-§30.4).

RÈGLE ABSOLUE (§13, IMPORTANT) : NO_ENGLISH_CONTEXT n'est jamais sélectionné.
Seuls ALREADY_RESOLVED (groupe A) et NEEDED (groupes B, C, D) sont éligibles.
"""

from __future__ import annotations

from app.semantic_canary.errors import SelectionError
from app.semantic_canary.models import (
    GROUP_ATYPICAL,
    GROUP_CONTROL_RESOLVED,
    GROUP_KEEP,
    GROUP_REVIEW,
    TARGET_TOTAL_SIZE,
    TARGET_GROUP_SIZE,
    SelectedBlock,
)

STATUS_ALREADY_RESOLVED = "ALREADY_RESOLVED"
STATUS_NEEDED = "NEEDED"

PHASE_STATUS_ALL_REVIEW = "ALL_REVIEW"
PHASE_STATUS_HAS_REVIEW = "HAS_REVIEW"
PHASE_STATUS_ALL_KEEP = "ALL_KEEP"

DIRECTION_BEFORE = "BEFORE"
DIRECTION_AFTER = "AFTER"
DIRECTION_BOTH = "BOTH"

# Seuil de la règle heuristique D5 : le FR fait au moins 1.5x la somme des
# contextes anglais adjacents -> indice qu'il contient plus qu'une simple
# traduction (§5, §13.D). Un seuil, pas une certitude : la classification
# finale reste celle du modèle, inspectée humainement (§25).
_EXTRA_CONTENT_RATIO = 1.5


def _sorted_pool(blocks: list[dict], predicate) -> list[dict]:
    return sorted(
        (block for block in blocks if predicate(block)),
        key=lambda block: str(block["block_id"]),
    )


def _stride_pick(
    pool: list[dict],
    count: int,
    *,
    description: str,
) -> list[tuple[dict, str]]:
    """
    Échantillon par pas de `count` blocs dans `pool` (déjà trié).

    stride = len(pool) // count (division entière) : garantit des index
    strictement croissants tant que len(pool) >= count, donc aucun doublon.
    """
    total = len(pool)

    if total < count:
        raise SelectionError(
            f"{description} : bassin de candidats insuffisant "
            f"({total} disponible(s), {count} requis)."
        )

    stride = total // count
    picks: list[tuple[dict, str]] = []

    for i in range(count):
        index = min(i * stride, total - 1)
        block = pool[index]
        reason = (
            f"{description} : échantillon par pas (stride={stride}) — "
            f"index {index}/{total}, bassin trié par block_id."
        )
        picks.append((block, reason))

    ids = [block["block_id"] for block, _ in picks]
    if len(set(ids)) != count:
        raise SelectionError(
            f"{description} : l'échantillonnage par pas a produit des doublons "
            f"({ids})."
        )

    return picks


def _extra_content_ratio(block: dict) -> float:
    before = block.get("english_before") or {}
    after = block.get("english_after") or {}
    denom = int(before.get("word_count") or 0) + int(after.get("word_count") or 0)

    if denom <= 0:
        return 0.0

    return float(block.get("word_count", 0)) / float(denom)


def _pick_single(
    candidates: list[dict],
    *,
    description: str,
) -> tuple[dict, str]:
    if not candidates:
        raise SelectionError(f"{description} : aucun candidat disponible.")

    block = sorted(candidates, key=lambda b: str(b["block_id"]))[0]
    return block, f"{description} (block_id le plus petit parmi les candidats)."


def select_canary_blocks(blocks: list[dict]) -> list[SelectedBlock]:
    """
    Sélectionne exactement 20 blocs, répartis en 4 groupes de 5 (§13).

    Lève SelectionError si un bassin est insuffisant : la fonction ne
    dégrade jamais silencieusement vers moins de 20 blocs (§14, STOP AVANT
    RÉSEAU).
    """
    selected: dict[str, SelectedBlock] = {}

    def _reserve(block: dict, group: str, reason: str) -> None:
        block_id = str(block["block_id"])
        if block_id in selected:
            raise SelectionError(
                f"Le bloc {block_id} a déjà été sélectionné "
                f"(groupe {selected[block_id].selection_group}) ; "
                f"tentative de re-sélection pour le groupe {group}."
            )
        selected[block_id] = SelectedBlock(
            block_id=block_id,
            selection_group=group,
            selection_reason=reason,
            raw_block=block,
        )

    def _remaining_needed() -> list[dict]:
        return [
            block
            for block in blocks
            if block.get("semantic_review_status") == STATUS_NEEDED
            and str(block["block_id"]) not in selected
        ]

    # -- Groupe A : contrôle positif — ALREADY_RESOLVED (§13.A) -------------
    pool_a = _sorted_pool(
        blocks, lambda b: b.get("semantic_review_status") == STATUS_ALREADY_RESOLVED
    )
    for block, reason in _stride_pick(
        pool_a, TARGET_GROUP_SIZE, description="Groupe A (ALREADY_RESOLVED)"
    ):
        _reserve(block, GROUP_CONTROL_RESOLVED, reason)

    # -- Groupe B : ALL_REVIEW / HAS_REVIEW parmi NEEDED (§13.B) ------------
    pool_b = _sorted_pool(
        blocks,
        lambda b: (
            b.get("semantic_review_status") == STATUS_NEEDED
            and b.get("phase_3a1_status")
            in (PHASE_STATUS_ALL_REVIEW, PHASE_STATUS_HAS_REVIEW)
            and str(b["block_id"]) not in selected
        ),
    )
    for block, reason in _stride_pick(
        pool_b,
        TARGET_GROUP_SIZE,
        description="Groupe B (ALL_REVIEW/HAS_REVIEW, indications lexicales fortes)",
    ):
        _reserve(block, GROUP_REVIEW, reason)

    # -- Groupe C : ALL_KEEP parmi NEEDED (§13.C) ----------------------------
    pool_c = _sorted_pool(
        blocks,
        lambda b: (
            b.get("semantic_review_status") == STATUS_NEEDED
            and b.get("phase_3a1_status") == PHASE_STATUS_ALL_KEEP
            and str(b["block_id"]) not in selected
        ),
    )
    for block, reason in _stride_pick(
        pool_c,
        TARGET_GROUP_SIZE,
        description="Groupe C (ALL_KEEP, traduction libre potentiellement ratée)",
    ):
        _reserve(block, GROUP_KEEP, reason)

    # -- Groupe D : atypiques (§13.D) ---------------------------------------
    # D1 — bloc long (le plus grand word_count restant, tie-break block_id).
    candidates = _remaining_needed()
    if not candidates:
        raise SelectionError("Groupe D1 (bloc long) : aucun candidat NEEDED restant.")
    d1 = sorted(candidates, key=lambda b: (-int(b.get("word_count", 0)), str(b["block_id"])))[0]
    _reserve(
        d1,
        GROUP_ATYPICAL,
        f"D1 — bloc long : word_count={d1.get('word_count')} maximum parmi le "
        "bassin NEEDED restant.",
    )

    # D2 — un bloc AUDIO003.
    candidates = _remaining_needed()
    audio003 = [b for b in candidates if b.get("audio_id") == "AUDIO003"]
    block, reason = _pick_single(audio003, description="D2 — bloc AUDIO003")
    _reserve(block, GROUP_ATYPICAL, reason)

    # D3 — cas BEFORE-only (candidate_direction == BEFORE).
    candidates = _remaining_needed()
    before_only = [b for b in candidates if b.get("candidate_direction") == DIRECTION_BEFORE]
    block, reason = _pick_single(before_only, description="D3 — cas BEFORE-only")
    _reserve(block, GROUP_ATYPICAL, reason)

    # D4 — cas AFTER-only (candidate_direction == AFTER).
    candidates = _remaining_needed()
    after_only = [b for b in candidates if b.get("candidate_direction") == DIRECTION_AFTER]
    block, reason = _pick_single(after_only, description="D4 — cas AFTER-only")
    _reserve(block, GROUP_ATYPICAL, reason)

    # D5 — cas BOTH où le FR semble contenir plus qu'une simple traduction.
    candidates = _remaining_needed()
    both = [b for b in candidates if b.get("candidate_direction") == DIRECTION_BOTH]
    rich = sorted(
        (b for b in both if _extra_content_ratio(b) >= _EXTRA_CONTENT_RATIO),
        key=lambda b: str(b["block_id"]),
    )
    if rich:
        d5 = rich[0]
        reason = (
            "D5 — cas BOTH avec contenu potentiellement excédentaire : "
            f"word_count FR ({d5.get('word_count')}) >= "
            f"{_EXTRA_CONTENT_RATIO}x la somme des contextes EN adjacents."
        )
    else:
        fallback = sorted(both, key=lambda b: str(b["block_id"]))
        if not fallback:
            raise SelectionError("Groupe D5 (cas BOTH) : aucun candidat disponible.")
        d5 = fallback[0]
        reason = (
            "D5 — repli : aucun bloc BOTH ne dépassait le seuil heuristique de "
            "contenu excédentaire ; bloc BOTH de plus petit block_id retenu."
        )
    _reserve(d5, GROUP_ATYPICAL, reason)

    if len(selected) != TARGET_TOTAL_SIZE:
        raise SelectionError(
            f"La sélection a produit {len(selected)} bloc(s) au lieu de "
            f"{TARGET_TOTAL_SIZE}."
        )

    return list(selected.values())


def validate_selection(selected_blocks: list[SelectedBlock]) -> None:
    """
    Contrôle local de la sélection AVANT tout appel réseau (§14).

    Vérifie : 20 IDs uniques, aucun NO_ENGLISH_CONTEXT, toutes les
    source_refs présentes et non vides, tous les textes reconstructibles
    (non vides). Lève SelectionError avec la liste complète des violations —
    STOP AVANT RÉSEAU (§14).
    """
    errors: list[str] = []

    if len(selected_blocks) != TARGET_TOTAL_SIZE:
        errors.append(
            f"{len(selected_blocks)} bloc(s) sélectionné(s) au lieu de "
            f"{TARGET_TOTAL_SIZE}."
        )

    ids = [block.block_id for block in selected_blocks]
    duplicates = sorted({block_id for block_id in ids if ids.count(block_id) > 1})
    if duplicates:
        errors.append(f"block_id dupliqué(s) dans la sélection : {duplicates}.")

    for block in selected_blocks:
        if block.semantic_review_status == "NO_ENGLISH_CONTEXT":
            errors.append(
                f"{block.block_id} : NO_ENGLISH_CONTEXT ne doit jamais être "
                "sélectionné (§13)."
            )

        if not block.fr_source_refs:
            errors.append(f"{block.block_id} : aucune source_ref française.")

        if not str(block.raw_block.get("text", "")).strip():
            errors.append(f"{block.block_id} : texte français vide ou non reconstructible.")

        before = block.english_before
        if before is not None and not (before.get("source_refs") and str(before.get("text", "")).strip()):
            errors.append(f"{block.block_id} : english_before invalide (refs ou texte vide).")

        after = block.english_after
        if after is not None and not (after.get("source_refs") and str(after.get("text", "")).strip()):
            errors.append(f"{block.block_id} : english_after invalide (refs ou texte vide).")

        if before is None and after is None:
            errors.append(
                f"{block.block_id} : ni english_before ni english_after — "
                "aucune comparaison n'est définie pour ce bloc."
            )

    if errors:
        raise SelectionError(
            "Sélection invalide, STOP AVANT RÉSEAU (§14) : " + " | ".join(errors)
        )
