"""
Statistiques par politique (§23-38) — dérivées UNIQUEMENT des décisions déjà
calculées par `app.cleanup_policy.evaluation` (jamais un second calcul de
risque ou de politique ici : ce module ne fait qu'agréger et trier).

Toutes les listes sont triées de façon déterministe (jamais `random`, §34) :
par défaut par `block_id` ; les classements par impact (`top_n_by_word_count`,
diffs) trient par `word_count` décroissant puis `block_id` croissant pour
départager les égalités.
"""

from __future__ import annotations

from app.cleanup_policy.constants import (
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_TRANSLATION_BEFORE,
    CLASSIFICATION_UNCERTAIN,
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    DECISIONS,
    LONG_BLOCK_WORD_THRESHOLD,
    MEDIUM_BLOCK_MAX_WORDS,
    MEDIUM_BLOCK_MIN_WORDS,
    ORIGIN_NO_ENGLISH_CONTEXT,
    ORIGIN_PHASE_3A1_RESOLVED,
    POLICY_A,
    POLICY_B,
    POLICY_C,
    POLICY_IDS,
    EXTRA_CONTENT_SIGNAL_TERMS,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_FORMER_ALL_KEEP,
    RISK_FORMER_REVIEW,
    RISK_HIGH_RISK_EXISTING,
    RISK_MULTI_SRC,
    TRANSLATION_CLASSIFICATIONS,
)
from app.cleanup_policy.evaluation import BlockEvaluation
from app.cleanup_policy.transcript_index import TranscriptIndex

TOP_N_DEFAULT = 20

CLASSIFICATION_BUCKET_LEGACY = "LEGACY_RESOLVED"
CLASSIFICATION_BUCKET_NO_CONTEXT = "NO_ENGLISH_CONTEXT"

CLASSIFICATION_BUCKETS = (
    CLASSIFICATION_TRANSLATION_BEFORE,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_UNCERTAIN,
    CLASSIFICATION_BUCKET_LEGACY,
    CLASSIFICATION_BUCKET_NO_CONTEXT,
)

# §27 : bornes exactes demandées par le cahier des charges — plus fines que
# `confidence_range` de la Phase 3A.1.2B (qui fusionne 0.80-0.89) : un
# vocabulaire DÉDIÉ à cette phase, jamais réutilisé silencieusement.
CONFIDENCE_FINE_BUCKETS = ("<0.70", "0.70-0.79", "0.80-0.84", "0.85-0.89", "0.90-0.94", ">=0.95")


def confidence_fine_bucket(confidence: float) -> str:
    if confidence < 0.70:
        return "<0.70"
    if confidence < 0.80:
        return "0.70-0.79"
    if confidence < 0.85:
        return "0.80-0.84"
    if confidence < 0.90:
        return "0.85-0.89"
    if confidence < 0.95:
        return "0.90-0.94"
    return ">=0.95"


def _empty_decision_counts() -> dict[str, int]:
    return {decision: 0 for decision in DECISIONS}


def _detail(evaluation: BlockEvaluation) -> dict:
    """Vue commune réutilisée par toutes les listes d'inspection (§28-33)."""
    record = evaluation.record
    return {
        "block_id": record.block_id,
        "audio_id": record.audio_id,
        "start_seconds": record.start_seconds,
        "end_seconds": record.end_seconds,
        "fr_source_refs": list(record.fr_source_refs),
        "bridge_source_refs": list(record.bridge_source_refs),
        "word_count": record.word_count,
        "classification": record.classification,
        "confidence": record.confidence,
        "risk_flags": list(evaluation.risk_flags),
        "fr_text": record.text,
        "english_before_text": record.english_before_text,
        "english_after_text": record.english_after_text,
        "matched_english_text": record.matched_english_text(),
        "decision_policy_a": evaluation.decision_for(POLICY_A).decision,
        "decision_policy_b": evaluation.decision_for(POLICY_B).decision,
        "decision_policy_c": evaluation.decision_for(POLICY_C).decision,
    }


def _sorted_by_word_count_desc(evaluations: list[BlockEvaluation]) -> list[BlockEvaluation]:
    return sorted(
        evaluations,
        key=lambda e: (-e.record.word_count, e.record.block_id),
    )


# ---------------------------------------------------------------------------
# §23 : totaux globaux par politique
# ---------------------------------------------------------------------------

def build_global_totals(
    evaluations: list[BlockEvaluation], transcript_index: TranscriptIndex
) -> dict:
    totals: dict[str, dict] = {}

    for policy_id in POLICY_IDS:
        auto = [e for e in evaluations if e.decision_for(policy_id).decision == DECISION_AUTO_REMOVE]
        human = [
            e for e in evaluations if e.decision_for(policy_id).decision == DECISION_HUMAN_REVIEW
        ]
        keep = [e for e in evaluations if e.decision_for(policy_id).decision == DECISION_KEEP]

        auto_refs = [ref for e in auto for ref in e.record.fr_source_refs]
        human_refs = [ref for e in human for ref in e.record.fr_source_refs]
        keep_refs = [ref for e in keep for ref in e.record.fr_source_refs]

        totals[policy_id] = {
            "auto_remove_blocks": len(auto),
            "human_review_blocks": len(human),
            "keep_blocks": len(keep),
            "total_blocks_check": len(auto) + len(human) + len(keep),
            "auto_remove_fr_src_count": len(auto_refs),
            "auto_remove_words": transcript_index.word_count_for_refs(auto_refs),
            "auto_remove_duration_seconds": transcript_index.duration_for_refs(auto_refs),
            "human_review_src_count": len(human_refs),
            "human_review_words": transcript_index.word_count_for_refs(human_refs),
            "keep_src_count": len(keep_refs),
            "keep_words": transcript_index.word_count_for_refs(keep_refs),
        }

    return totals


# ---------------------------------------------------------------------------
# §24 : impact transcript
# ---------------------------------------------------------------------------

def build_transcript_impact(
    global_totals: dict, transcript_index: TranscriptIndex
) -> dict:
    impact = {}
    for policy_id in POLICY_IDS:
        removed_src = global_totals[policy_id]["auto_remove_fr_src_count"]
        removed_words = global_totals[policy_id]["auto_remove_words"]
        impact[policy_id] = {
            "original_segments": transcript_index.total_segment_count,
            "candidate_removed_fr_src_count": removed_src,
            "remaining_src_count": transcript_index.total_segment_count - removed_src,
            "original_words": transcript_index.total_word_count,
            "candidate_removed_words": removed_words,
            "estimated_remaining_words": transcript_index.total_word_count - removed_words,
        }
    return impact


# ---------------------------------------------------------------------------
# §25 : impact par audio
# ---------------------------------------------------------------------------

def build_by_audio(
    evaluations: list[BlockEvaluation], transcript_index: TranscriptIndex
) -> dict:
    audio_ids = sorted({e.record.audio_id for e in evaluations})
    result: dict[str, dict] = {}

    for audio_id in audio_ids:
        subset = [e for e in evaluations if e.record.audio_id == audio_id]
        per_policy = {}
        for policy_id in POLICY_IDS:
            auto = [e for e in subset if e.decision_for(policy_id).decision == DECISION_AUTO_REMOVE]
            human = [
                e for e in subset if e.decision_for(policy_id).decision == DECISION_HUMAN_REVIEW
            ]
            keep = [e for e in subset if e.decision_for(policy_id).decision == DECISION_KEEP]
            auto_refs = [ref for e in auto for ref in e.record.fr_source_refs]

            per_policy[policy_id] = {
                "auto_remove": len(auto),
                "human_review": len(human),
                "keep": len(keep),
                "candidate_removed_src": len(auto_refs),
                "candidate_removed_words": transcript_index.word_count_for_refs(auto_refs),
                "candidate_removed_duration_seconds": transcript_index.duration_for_refs(auto_refs),
            }

        result[audio_id] = {"fr_blocks": len(subset), "policies": per_policy}

    return result


# ---------------------------------------------------------------------------
# §26 : impact par classification (+ LEGACY_RESOLVED, NO_ENGLISH_CONTEXT)
# ---------------------------------------------------------------------------

def _classification_bucket(evaluation: BlockEvaluation) -> str:
    record = evaluation.record
    if record.semantic_origin == ORIGIN_PHASE_3A1_RESOLVED:
        return CLASSIFICATION_BUCKET_LEGACY
    if record.semantic_origin == ORIGIN_NO_ENGLISH_CONTEXT:
        return CLASSIFICATION_BUCKET_NO_CONTEXT
    return str(record.classification)


def build_by_classification(evaluations: list[BlockEvaluation]) -> dict:
    result = {bucket: {policy_id: _empty_decision_counts() for policy_id in POLICY_IDS}
              for bucket in CLASSIFICATION_BUCKETS}

    for evaluation in evaluations:
        bucket = _classification_bucket(evaluation)
        if bucket not in result:
            result[bucket] = {policy_id: _empty_decision_counts() for policy_id in POLICY_IDS}
        for policy_id in POLICY_IDS:
            decision = evaluation.decision_for(policy_id).decision
            result[bucket][policy_id][decision] += 1

    return result


# ---------------------------------------------------------------------------
# §27 : impact par confidence (314 résultats sémantiques uniquement)
# ---------------------------------------------------------------------------

def build_by_confidence(evaluations: list[BlockEvaluation]) -> dict:
    result = {bucket: {policy_id: _empty_decision_counts() for policy_id in POLICY_IDS}
              for bucket in CONFIDENCE_FINE_BUCKETS}

    for evaluation in evaluations:
        confidence = evaluation.record.confidence
        if confidence is None:
            continue
        bucket = confidence_fine_bucket(confidence)
        for policy_id in POLICY_IDS:
            decision = evaluation.decision_for(policy_id).decision
            result[bucket][policy_id][decision] += 1

    return result


# ---------------------------------------------------------------------------
# §28, §13 : FORMER_ALL_KEEP
# ---------------------------------------------------------------------------

def build_former_all_keep(evaluations: list[BlockEvaluation]) -> dict:
    subset = [e for e in evaluations if RISK_FORMER_ALL_KEEP in e.risk_flags]

    distribution = {policy_id: _empty_decision_counts() for policy_id in POLICY_IDS}
    auto_remove_candidates = {policy_id: [] for policy_id in POLICY_IDS}

    for evaluation in subset:
        for policy_id in POLICY_IDS:
            decision = evaluation.decision_for(policy_id).decision
            distribution[policy_id][decision] += 1
            if decision == DECISION_AUTO_REMOVE:
                auto_remove_candidates[policy_id].append(_detail(evaluation))

    for policy_id in POLICY_IDS:
        auto_remove_candidates[policy_id].sort(key=lambda d: d["block_id"])

    return {
        "total": len(subset),
        "distribution": distribution,
        "auto_remove_candidates": auto_remove_candidates,
    }


# ---------------------------------------------------------------------------
# §14 : FORMER_REVIEW (ALL_REVIEW / HAS_REVIEW)
# ---------------------------------------------------------------------------

def build_former_review(evaluations: list[BlockEvaluation]) -> dict:
    subset = [e for e in evaluations if RISK_FORMER_REVIEW in e.risk_flags]

    distribution = {policy_id: _empty_decision_counts() for policy_id in POLICY_IDS}
    for evaluation in subset:
        for policy_id in POLICY_IDS:
            distribution[policy_id][evaluation.decision_for(policy_id).decision] += 1

    return {"total": len(subset), "distribution": distribution}


# ---------------------------------------------------------------------------
# §29 : HIGH_RISK (high_risk_for_deletion_review, 153 attendus pour le
# projet réel)
# ---------------------------------------------------------------------------

def build_high_risk(evaluations: list[BlockEvaluation]) -> dict:
    subset = [e for e in evaluations if RISK_HIGH_RISK_EXISTING in e.risk_flags]

    distribution = {policy_id: _empty_decision_counts() for policy_id in POLICY_IDS}
    auto_remove_listed = {policy_id: [] for policy_id in POLICY_IDS}

    for evaluation in subset:
        for policy_id in POLICY_IDS:
            decision = evaluation.decision_for(policy_id).decision
            distribution[policy_id][decision] += 1
            if decision == DECISION_AUTO_REMOVE:
                auto_remove_listed[policy_id].append(_detail(evaluation))

    for policy_id in POLICY_IDS:
        auto_remove_listed[policy_id].sort(key=lambda d: d["block_id"])

    return {
        "total": len(subset),
        "distribution": distribution,
        "auto_remove_listed": auto_remove_listed,
    }


# ---------------------------------------------------------------------------
# §30 : TRANSLATION_AFTER (11 attendus pour le projet réel)
# ---------------------------------------------------------------------------

def build_translation_after(evaluations: list[BlockEvaluation]) -> dict:
    subset = [
        e for e in evaluations if e.record.classification == CLASSIFICATION_TRANSLATION_AFTER
    ]
    subset.sort(key=lambda e: e.record.block_id)

    return {
        "total": len(subset),
        "blocks": [_detail(evaluation) for evaluation in subset],
    }


# ---------------------------------------------------------------------------
# §31 : blocs multi-SRC (TRANSLATION_* avec plusieurs fr_source_refs)
# ---------------------------------------------------------------------------

def build_multi_src(evaluations: list[BlockEvaluation]) -> dict:
    subset = [
        e
        for e in evaluations
        if e.record.classification in TRANSLATION_CLASSIFICATIONS
        and RISK_MULTI_SRC in e.risk_flags
    ]

    auto_remove_by_policy = {policy_id: [] for policy_id in POLICY_IDS}
    counts_by_policy = {policy_id: 0 for policy_id in POLICY_IDS}

    for evaluation in subset:
        for policy_id in POLICY_IDS:
            if evaluation.decision_for(policy_id).decision == DECISION_AUTO_REMOVE:
                counts_by_policy[policy_id] += 1
                auto_remove_by_policy[policy_id].append(_detail(evaluation))

    for policy_id in POLICY_IDS:
        auto_remove_by_policy[policy_id].sort(key=lambda d: d["block_id"])

    return {
        "total_translation_multi_src": len(subset),
        "auto_remove_counts": counts_by_policy,
        "auto_remove_listed": auto_remove_by_policy,
    }


# ---------------------------------------------------------------------------
# §32 : blocs moyens/longs — 31-60 et >60 mots
# ---------------------------------------------------------------------------

def build_medium_long(evaluations: list[BlockEvaluation]) -> dict:
    medium = [
        e for e in evaluations if MEDIUM_BLOCK_MIN_WORDS <= e.record.word_count <= MEDIUM_BLOCK_MAX_WORDS
    ]
    long_blocks = [e for e in evaluations if e.record.word_count > LONG_BLOCK_WORD_THRESHOLD]

    def _bucket_report(subset: list[BlockEvaluation]) -> dict:
        by_classification = {bucket: 0 for bucket in CLASSIFICATION_BUCKETS}
        distribution = {policy_id: _empty_decision_counts() for policy_id in POLICY_IDS}
        for evaluation in subset:
            bucket = _classification_bucket(evaluation)
            by_classification[bucket] = by_classification.get(bucket, 0) + 1
            for policy_id in POLICY_IDS:
                distribution[policy_id][evaluation.decision_for(policy_id).decision] += 1
        return {
            "total": len(subset),
            "by_classification": by_classification,
            "distribution": distribution,
        }

    # §32 : vérification RÉELLE (pas une confiance aveugle au rapport 3A.1.2B)
    # qu'aucun bloc > 60 mots n'est classifié TRANSLATION_* — et, par
    # construction (POLICY_C plafonne à 60 mots), qu'aucune politique ne
    # pourrait jamais AUTO_REMOVE un tel bloc si un jour il apparaissait.
    long_translation_blocks = [
        e for e in long_blocks if e.record.classification in TRANSLATION_CLASSIFICATIONS
    ]
    long_auto_remove_by_policy = {
        policy_id: [
            e.record.block_id
            for e in long_blocks
            if e.decision_for(policy_id).decision == DECISION_AUTO_REMOVE
        ]
        for policy_id in POLICY_IDS
    }

    return {
        "medium_31_60": _bucket_report(medium),
        "long_over_60": _bucket_report(long_blocks),
        "long_blocks_classified_translation": sorted(
            e.record.block_id for e in long_translation_blocks
        ),
        "long_blocks_auto_remove_by_policy": long_auto_remove_by_policy,
    }


# ---------------------------------------------------------------------------
# §33 : top 20 candidats AUTO_REMOVE par impact (word_count) par politique
# ---------------------------------------------------------------------------

def build_top_n_auto_remove(
    evaluations: list[BlockEvaluation], *, top_n: int = TOP_N_DEFAULT
) -> dict:
    result = {}
    for policy_id in POLICY_IDS:
        auto = [
            e for e in evaluations if e.decision_for(policy_id).decision == DECISION_AUTO_REMOVE
        ]
        ranked = _sorted_by_word_count_desc(auto)[:top_n]
        result[policy_id] = [_detail(evaluation) for evaluation in ranked]
    return result


# ---------------------------------------------------------------------------
# §35-36 : diff A->B, diff B->C
# ---------------------------------------------------------------------------

def _diff(
    evaluations: list[BlockEvaluation],
    *,
    from_policy: str,
    to_policy: str,
    transcript_index: TranscriptIndex,
    top_n: int = TOP_N_DEFAULT,
) -> dict:
    subset = [
        e
        for e in evaluations
        if e.decision_for(from_policy).decision == DECISION_HUMAN_REVIEW
        and e.decision_for(to_policy).decision == DECISION_AUTO_REMOVE
    ]
    refs = [ref for e in subset for ref in e.record.fr_source_refs]
    ranked = _sorted_by_word_count_desc(subset)[:top_n]

    return {
        "count": len(subset),
        "src_count": len(refs),
        "words": transcript_index.word_count_for_refs(refs),
        "top": [_detail(evaluation) for evaluation in ranked],
    }


def build_diff_a_to_b(evaluations: list[BlockEvaluation], transcript_index: TranscriptIndex) -> dict:
    return _diff(
        evaluations, from_policy=POLICY_A, to_policy=POLICY_B, transcript_index=transcript_index
    )


def build_diff_b_to_c(evaluations: list[BlockEvaluation], transcript_index: TranscriptIndex) -> dict:
    return _diff(
        evaluations, from_policy=POLICY_B, to_policy=POLICY_C, transcript_index=transcript_index
    )


# ---------------------------------------------------------------------------
# §37-38 : intersection des politiques + SAFE_CONSENSUS_CANDIDATE
# ---------------------------------------------------------------------------

def _is_auto(evaluation: BlockEvaluation, policy_id: str) -> bool:
    return evaluation.decision_for(policy_id).decision == DECISION_AUTO_REMOVE


def build_intersection(
    evaluations: list[BlockEvaluation], transcript_index: TranscriptIndex
) -> dict:
    """
    §37 : quatre catégories NOMMÉES par le cahier des charges, PLUS une
    catégorie de sécurité `other_combinations` — vide dans les données
    réelles observées (A ⊆ B ⊆ C empiriquement), mais garantit que
    `sum(count) == len(evaluations)` même si une future exécution (un autre
    projet, des seuils modifiés) produisait une combinaison non couverte par
    les quatre catégories explicites (ex. AUTO_REMOVE sous A mais pas B).
    """
    all_three = [e for e in evaluations if _is_auto(e, POLICY_A) and _is_auto(e, POLICY_B) and _is_auto(e, POLICY_C)]
    b_and_c_not_a = [
        e
        for e in evaluations
        if _is_auto(e, POLICY_B) and _is_auto(e, POLICY_C) and not _is_auto(e, POLICY_A)
    ]
    only_c = [
        e
        for e in evaluations
        if _is_auto(e, POLICY_C) and not _is_auto(e, POLICY_A) and not _is_auto(e, POLICY_B)
    ]
    never = [
        e
        for e in evaluations
        if not _is_auto(e, POLICY_A) and not _is_auto(e, POLICY_B) and not _is_auto(e, POLICY_C)
    ]

    categorized_ids = {
        e.record.block_id for e in (*all_three, *b_and_c_not_a, *only_c, *never)
    }
    other_combinations = [e for e in evaluations if e.record.block_id not in categorized_ids]

    def _stats(subset: list[BlockEvaluation]) -> dict:
        refs = [ref for e in subset for ref in e.record.fr_source_refs]
        return {
            "count": len(subset),
            "src_count": len(refs),
            "words": transcript_index.word_count_for_refs(refs),
            "duration_seconds": transcript_index.duration_for_refs(refs),
            "block_ids": sorted(e.record.block_id for e in subset),
        }

    result = {
        "auto_remove_in_a_b_c": _stats(all_three),
        "auto_remove_in_b_and_c_not_a": _stats(b_and_c_not_a),
        "auto_remove_only_c": _stats(only_c),
        "never_auto_remove": _stats(never),
        "other_combinations": _stats(other_combinations),
    }

    total_categorized = sum(result[key]["count"] for key in result)
    result["total_check"] = {
        "sum_of_categories": total_categorized,
        "total_blocks": len(evaluations),
        "matches": total_categorized == len(evaluations),
    }

    return result


def build_safe_consensus_candidate(intersection: dict) -> dict:
    """
    §38 : SAFE_CONSENSUS_CANDIDATE = auto_remove_in_a_b_c. Nom descriptif
    UNIQUEMENT — signifie que les trois politiques simulées convergent,
    jamais « autorisé à supprimer ».
    """
    stats = intersection["auto_remove_in_a_b_c"]
    return {
        "meaning": (
            "Les trois politiques simulées (A, B, C) convergent vers "
            "AUTO_REMOVE pour ce bloc. Ceci ne signifie PAS « autorisé à "
            "supprimer » (§38) : décision humaine requise avant toute "
            "application réelle."
        ),
        **stats,
    }


# ---------------------------------------------------------------------------
# §43 : réseau — zéro appel par construction (aucun import IA dans ce paquet)
# ---------------------------------------------------------------------------

def build_extra_content_signal(evaluations: list[BlockEvaluation]) -> dict:
    """§10, §45.7 : signal de prudence extrait des justifications existantes."""
    subset = [e for e in evaluations if RISK_EXTRA_CONTENT_SIGNAL in e.risk_flags]
    return {
        "method": (
            "Recherche déterministe, insensible à la casse, en sous-chaîne, "
            "dans reason. Jamais une nouvelle classification."
        ),
        "terms": list(EXTRA_CONTENT_SIGNAL_TERMS),
        "detected_count": len(subset),
        "block_ids": sorted(e.record.block_id for e in subset),
    }


def build_network_report() -> dict:
    return {
        "anthropic_calls": 0,
        "openai_calls": 0,
        "whisper_calls": 0,
        "ollama_calls": 0,
        "lm_studio_calls": 0,
        "other_network_calls": 0,
        "note": (
            "Cette phase ne recalcule aucune classification sémantique et "
            "n'importe aucun module réseau (app.ai.*, app.semantic_canary.runner, "
            "app.semantic_batch.runner). Seules la lecture des artefacts "
            "existants et leur hashing SHA-256 sont effectués."
        ),
    }


# ---------------------------------------------------------------------------
# Assemblage complet
# ---------------------------------------------------------------------------

def build_statistics(
    evaluations: list[BlockEvaluation], transcript_index: TranscriptIndex
) -> dict:
    global_totals = build_global_totals(evaluations, transcript_index)
    intersection = build_intersection(evaluations, transcript_index)

    return {
        "global_totals": global_totals,
        "transcript_impact": build_transcript_impact(global_totals, transcript_index),
        "by_audio": build_by_audio(evaluations, transcript_index),
        "by_classification": build_by_classification(evaluations),
        "by_confidence": build_by_confidence(evaluations),
        "former_all_keep": build_former_all_keep(evaluations),
        "former_review": build_former_review(evaluations),
        "high_risk": build_high_risk(evaluations),
        "translation_after": build_translation_after(evaluations),
        "multi_src": build_multi_src(evaluations),
        "medium_long": build_medium_long(evaluations),
        "top_20_auto_remove_by_word_count": build_top_n_auto_remove(evaluations),
        "diff_a_to_b": build_diff_a_to_b(evaluations, transcript_index),
        "diff_b_to_c": build_diff_b_to_c(evaluations, transcript_index),
        "intersection": intersection,
        "safe_consensus_candidate": build_safe_consensus_candidate(intersection),
        "extra_content_signal": build_extra_content_signal(evaluations),
        "network": build_network_report(),
    }
