"""
Validateur strict de l'artefact final (§39) — indépendant du chemin de
calcul qui l'a produit : il relit `artifact["blocks"]` (des dicts, la forme
JSON exacte) et recalcule ses propres vérifications, plutôt que de faire
confiance aux objets internes déjà utilisés pour construire l'artefact.
C'est la même philosophie que app.semantic_canary.validator : un contrat
relu, jamais une simple relecture des mêmes objets.

`validate_artifact` lève `SimulationValidationError` avec la liste COMPLÈTE
des violations trouvées — jamais un seul message tronqué au premier
problème (§39 : « chaque bloc/politique » doit pouvoir être audité).
"""

from __future__ import annotations

from app.cleanup_policy.constants import (
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_UNCERTAIN,
    CLASSIFICATIONS,
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    DECISIONS,
    LEGACY_REASON_CODE,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    ORIGIN_SEMANTIC_BATCH,
    POLICY_A,
    POLICY_A_MAX_WORDS,
    POLICY_A_MIN_CONFIDENCE,
    POLICY_B,
    POLICY_B_MAX_WORDS,
    POLICY_B_MIN_CONFIDENCE,
    POLICY_C,
    POLICY_C_MAX_WORDS,
    POLICY_C_MIN_CONFIDENCE,
    POLICY_IDS,
    SEMANTIC_ORIGINS,
    TRANSLATION_CLASSIFICATIONS,
)
from app.cleanup_policy.errors import SimulationValidationError
from app.cleanup_policy.risk import has_extra_content_signal


def _policy_a_ok(block: dict) -> bool:
    semantic = block["semantic"]
    source = block["source"]
    risk_flags = set(block["risk_flags"])
    confidence = semantic["confidence"]
    return (
        confidence is not None
        and confidence >= POLICY_A_MIN_CONFIDENCE
        and "HIGH_RISK_EXISTING" not in risk_flags
        and source["word_count"] <= POLICY_A_MAX_WORDS
        and not source["bridge_source_refs"]
    )


def _policy_b_ok(block: dict) -> bool:
    semantic = block["semantic"]
    source = block["source"]
    confidence = semantic["confidence"]
    return (
        confidence is not None
        and confidence >= POLICY_B_MIN_CONFIDENCE
        and source["word_count"] <= POLICY_B_MAX_WORDS
        and not source["bridge_source_refs"]
        and not semantic.get("requires_human_review_flag")
    )


def _policy_c_ok(block: dict) -> bool:
    semantic = block["semantic"]
    source = block["source"]
    confidence = semantic["confidence"]
    extra_signal = has_extra_content_signal(semantic.get("reason"))
    return (
        confidence is not None
        and confidence >= POLICY_C_MIN_CONFIDENCE
        and source["word_count"] <= POLICY_C_MAX_WORDS
        and not extra_signal
    )


_POLICY_CONDITION_CHECK = {
    POLICY_A: _policy_a_ok,
    POLICY_B: _policy_b_ok,
    POLICY_C: _policy_c_ok,
}


def validate_artifact(
    artifact: dict,
    *,
    expected_total: int | None = None,
    expected_semantic_batch: int | None = None,
    expected_phase_3a1_resolved: int | None = None,
    expected_no_english_context: int | None = None,
    valid_block_ids: set[str] | None = None,
    valid_src_ids: set[str] | None = None,
    expected_source_hashes: dict[str, str] | None = None,
) -> None:
    errors: list[str] = []

    blocks = artifact.get("blocks") or []

    # --- §39 : compte total, aucun doublon --------------------------------
    ids = [str(b["block_id"]) for b in blocks]
    if expected_total is not None and len(ids) != expected_total:
        errors.append(f"total blocks = {len(ids)}, attendu {expected_total}.")

    duplicates = sorted({bid for bid in ids if ids.count(bid) > 1})
    if duplicates:
        errors.append(f"block_id dupliqué(s) : {duplicates}.")

    if valid_block_ids is not None:
        invented = sorted(set(ids) - valid_block_ids)
        if invented:
            errors.append(f"block_id inventé(s), absent(s) de la source : {invented}.")

    # --- §7 : répartition par origine -------------------------------------
    origin_counts = {origin: 0 for origin in SEMANTIC_ORIGINS}
    for block in blocks:
        origin = block["semantic"]["semantic_origin"]
        if origin not in origin_counts:
            errors.append(f"{block['block_id']} : semantic_origin inconnu « {origin} ».")
            continue
        origin_counts[origin] += 1

    if expected_semantic_batch is not None and origin_counts[ORIGIN_SEMANTIC_BATCH] != expected_semantic_batch:
        errors.append(
            f"SEMANTIC_BATCH = {origin_counts[ORIGIN_SEMANTIC_BATCH]}, "
            f"attendu {expected_semantic_batch}."
        )
    if (
        expected_phase_3a1_resolved is not None
        and origin_counts[ORIGIN_PHASE_3A1_RESOLVED] != expected_phase_3a1_resolved
    ):
        errors.append(
            f"PHASE_3A1_RESOLVED = {origin_counts[ORIGIN_PHASE_3A1_RESOLVED]}, "
            f"attendu {expected_phase_3a1_resolved}."
        )
    if (
        expected_no_english_context is not None
        and origin_counts[ORIGIN_NO_ENGLISH_CONTEXT] != expected_no_english_context
    ):
        errors.append(
            f"NO_ENGLISH_CONTEXT = {origin_counts[ORIGIN_NO_ENGLISH_CONTEXT]}, "
            f"attendu {expected_no_english_context}."
        )

    # --- §39 : aucun FR ref inventé / dupliqué entre blocs ----------------
    all_fr_refs: list[str] = []
    for block in blocks:
        all_fr_refs.extend(block["source"]["fr_source_refs"])

    fr_duplicates = sorted({ref for ref in all_fr_refs if all_fr_refs.count(ref) > 1})
    if fr_duplicates:
        errors.append(f"fr_source_ref dupliqué(s) entre blocs : {fr_duplicates}.")

    if valid_src_ids is not None:
        for block in blocks:
            invented_refs = sorted(
                (set(block["source"]["fr_source_refs"]) | set(block["source"]["bridge_source_refs"]))
                - valid_src_ids
            )
            if invented_refs:
                errors.append(f"{block['block_id']} : source_ref inventé(e) : {invented_refs}.")

    # --- par bloc : cohérence classification / décisions / candidats ------
    for block in blocks:
        block_id = block["block_id"]
        semantic = block["semantic"]
        source = block["source"]
        origin = semantic["semantic_origin"]
        classification = semantic["classification"]
        simulations = block["simulations"]

        if origin == ORIGIN_SEMANTIC_BATCH:
            if classification is None or classification not in CLASSIFICATIONS:
                errors.append(
                    f"{block_id} : SEMANTIC_BATCH avec classification invalide "
                    f"« {classification} »."
                )
        elif classification is not None:
            errors.append(
                f"{block_id} : origine {origin} ne devrait porter aucune "
                f"classification (trouvé {classification!r})."
            )

        for policy_id in POLICY_IDS:
            simulation = simulations.get(policy_id)
            if simulation is None:
                errors.append(f"{block_id} : simulation absente pour {policy_id}.")
                continue

            decision = simulation["decision"]
            candidate_refs = simulation["candidate_removed_source_refs"]

            if decision not in DECISIONS:
                errors.append(f"{block_id}/{policy_id} : decision inconnue « {decision} ».")

            # NOT_TRANSLATION toujours KEEP (§17, §39)
            if classification == CLASSIFICATION_NOT_TRANSLATION and decision != DECISION_KEEP:
                errors.append(
                    f"{block_id}/{policy_id} : NOT_TRANSLATION doit être KEEP, "
                    f"trouvé {decision}."
                )

            # UNCERTAIN toujours KEEP (§18, §39)
            if classification == CLASSIFICATION_UNCERTAIN and decision != DECISION_KEEP:
                errors.append(
                    f"{block_id}/{policy_id} : UNCERTAIN doit être KEEP, trouvé {decision}."
                )

            # NO_ENGLISH_CONTEXT toujours KEEP (§16, §39)
            if origin == ORIGIN_NO_ENGLISH_CONTEXT and decision != DECISION_KEEP:
                errors.append(
                    f"{block_id}/{policy_id} : NO_ENGLISH_CONTEXT doit être KEEP, "
                    f"trouvé {decision}."
                )

            # LEGACY_RESOLVED toujours HUMAN_REVIEW (§15, §39)
            if origin == ORIGIN_PHASE_3A1_RESOLVED:
                if decision != DECISION_HUMAN_REVIEW:
                    errors.append(
                        f"{block_id}/{policy_id} : PHASE_3A1_RESOLVED doit être "
                        f"HUMAN_REVIEW, trouvé {decision}."
                    )
                elif LEGACY_REASON_CODE not in simulation["reason"]:
                    errors.append(
                        f"{block_id}/{policy_id} : raison HUMAN_REVIEW legacy ne "
                        f"contient pas {LEGACY_REASON_CODE!r}."
                    )

            # AUTO_REMOVE uniquement TRANSLATION_* (§39)
            if decision == DECISION_AUTO_REMOVE and classification not in TRANSLATION_CLASSIFICATIONS:
                errors.append(
                    f"{block_id}/{policy_id} : AUTO_REMOVE avec classification "
                    f"« {classification} » (doit être TRANSLATION_BEFORE/AFTER)."
                )

            # candidate_removed_source_refs == fr_source_refs pour AUTO_REMOVE,
            # vide sinon (§19, §39)
            if decision == DECISION_AUTO_REMOVE:
                if list(candidate_refs) != list(source["fr_source_refs"]):
                    errors.append(
                        f"{block_id}/{policy_id} : candidate_removed_source_refs "
                        f"!= fr_source_refs pour un bloc AUTO_REMOVE."
                    )
            elif candidate_refs:
                errors.append(
                    f"{block_id}/{policy_id} : candidate_removed_source_refs non "
                    f"vide pour une décision {decision}."
                )

            # bridge refs jamais dans candidate_removed_source_refs (§19, §39)
            if set(candidate_refs) & set(source["bridge_source_refs"]):
                errors.append(
                    f"{block_id}/{policy_id} : bridge_source_refs présent(s) dans "
                    "candidate_removed_source_refs."
                )

            # Chaque politique respecte ses propres conditions (§39) — check
            # ré-implémenté indépendamment de app.cleanup_policy.policies.
            if decision == DECISION_AUTO_REMOVE and origin == ORIGIN_SEMANTIC_BATCH:
                condition_ok = _POLICY_CONDITION_CHECK[policy_id](block)
                if not condition_ok:
                    errors.append(
                        f"{block_id}/{policy_id} : AUTO_REMOVE mais les conditions "
                        f"propres à {policy_id} ne sont pas satisfaites (re-vérifié "
                        "indépendamment)."
                    )

    # --- source hashes ------------------------------------------------------
    if expected_source_hashes is not None:
        actual = artifact.get("source_hashes") or {}
        mismatches = {
            key: (expected_source_hashes[key], actual.get(key))
            for key in expected_source_hashes
            if actual.get(key) != expected_source_hashes[key]
        }
        if mismatches:
            errors.append(f"source_hashes incohérent(s) : {mismatches}.")

    if errors:
        raise SimulationValidationError(
            f"Artefact cleanup_policy_simulation.json invalide ({len(errors)} "
            "violation(s)) : " + " | ".join(errors)
        )
