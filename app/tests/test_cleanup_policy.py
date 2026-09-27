"""
Tests de la Phase 3A.2A — simulation déterministe des politiques de
nettoyage linguistique (app.cleanup_policy).

Organisation (§40 du cahier des charges) :

    TestExtraContentSignal    détection déterministe du signal de prudence
    TestRiskFlags             risk_flags par bloc (§11-14)
    TestFixedOriginPolicies   NOT_TRANSLATION / UNCERTAIN / NO_ENGLISH_CONTEXT
                              / LEGACY_RESOLVED -> décision fixe (§15-18)
    TestPolicyA/B/C           seuils exacts de chaque politique (§8)
    TestCandidateRefs         candidate_removed_source_refs (§19)
    TestPopulation            fusion 333 blocs, validation stricte (§7, §39)
    TestValidator             contrat strict indépendant (§39)
    TestAggregator            safe consensus, diffs, former_all_keep,
                              high_risk, translation_after, médium/long (§28-38)
    TestIntegrity             5 artefacts protégés (§5, §44)
    TestRunnerIntegration     bout en bout sur un vrai petit projet, hash
                              inchangés, déterminisme, zéro réseau (§39-44)

Aucun test de ce fichier ne touche au réseau : ce paquet n'importe aucun
module capable d'émettre une requête (§3, §43) ; le test d'intégration
utilise en plus `no_ai_network` par défensive supplémentaire.
"""

from __future__ import annotations

import copy
import json

import pytest

from app.cleanup_policy import aggregator as aggregator_module
from app.cleanup_policy import integrity as integrity_module
from app.cleanup_policy import population as population_module
from app.cleanup_policy import simulation as simulation_module
from app.cleanup_policy.constants import (
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    LEGACY_REASON_CODE,
    POLICY_A,
    POLICY_B,
    POLICY_C,
    RISK_BRIDGE_PRESENT,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_FORMER_ALL_KEEP,
    RISK_FORMER_REVIEW,
    RISK_HIGH_RISK_EXISTING,
    RISK_LEGACY_RESOLVED,
    RISK_LONG_BLOCK,
    RISK_LOW_CONFIDENCE,
    RISK_MEDIUM_BLOCK,
    RISK_MULTI_SRC,
    RISK_NO_ENGLISH_CONTEXT,
    RISK_OTHER_STRUCTURE,
    RISK_TRANSLATION_AFTER,
)
from app.cleanup_policy.errors import PopulationError, SimulationValidationError
from app.cleanup_policy.evaluation import evaluate_population
from app.cleanup_policy.policies import decide_all_policies
from app.cleanup_policy.risk import compute_risk_flags, has_extra_content_signal
from app.cleanup_policy.transcript_index import build_transcript_index
from app.tests.cleanup_policy_fixtures import make_record


# ---------------------------------------------------------------------------
# TestExtraContentSignal (§10)
# ---------------------------------------------------------------------------

class TestExtraContentSignal:
    def test_detects_english_term(self):
        assert has_extra_content_signal("This contains additional commentary.") is True

    def test_detects_french_equivalent_ajout(self):
        assert has_extra_content_signal("Le bloc ajoute une idee personnelle.") is True

    def test_detects_french_equivalent_developpe(self):
        assert has_extra_content_signal("Le FR developpe un point absent de l'anglais.") is True

    def test_detects_partiellement(self):
        assert has_extra_content_signal("Le FR traduit partiellement le EN.") is True

    def test_case_insensitive(self):
        assert has_extra_content_signal("ADDITIONAL CONTENT DETECTED") is True

    def test_no_signal_on_neutral_reason(self):
        assert has_extra_content_signal("Correspondance directe et complete.") is False

    def test_none_reason_is_false(self):
        assert has_extra_content_signal(None) is False

    def test_empty_reason_is_false(self):
        assert has_extra_content_signal("") is False


# ---------------------------------------------------------------------------
# TestRiskFlags (§11-14)
# ---------------------------------------------------------------------------

class TestRiskFlags:
    def test_high_risk_existing_flag(self):
        record = make_record(is_high_risk_existing=True)
        assert RISK_HIGH_RISK_EXISTING in compute_risk_flags(record)

    def test_no_high_risk_flag_when_not_flagged(self):
        record = make_record(is_high_risk_existing=False)
        assert RISK_HIGH_RISK_EXISTING not in compute_risk_flags(record)

    def test_low_confidence_flag_for_translation_under_threshold(self):
        record = make_record(classification="TRANSLATION_BEFORE", confidence=0.89)
        assert RISK_LOW_CONFIDENCE in compute_risk_flags(record)

    def test_no_low_confidence_flag_at_threshold(self):
        record = make_record(classification="TRANSLATION_BEFORE", confidence=0.90)
        assert RISK_LOW_CONFIDENCE not in compute_risk_flags(record)

    def test_no_low_confidence_flag_for_not_translation(self):
        """LOW_CONFIDENCE ne s'applique qu'aux TRANSLATION_* (§32 réutilisé)."""
        record = make_record(classification="NOT_TRANSLATION", confidence=0.1)
        assert RISK_LOW_CONFIDENCE not in compute_risk_flags(record)

    def test_multi_src_flag_when_several_refs(self):
        record = make_record(fr_source_refs=("SRC1", "SRC2"))
        assert RISK_MULTI_SRC in compute_risk_flags(record)

    def test_no_multi_src_flag_for_single_ref(self):
        record = make_record(fr_source_refs=("SRC1",))
        assert RISK_MULTI_SRC not in compute_risk_flags(record)

    def test_long_block_flag_over_60(self):
        record = make_record(word_count=61)
        flags = compute_risk_flags(record)
        assert RISK_LONG_BLOCK in flags
        assert RISK_MEDIUM_BLOCK not in flags

    def test_medium_block_flag_31_to_60(self):
        record = make_record(word_count=45)
        flags = compute_risk_flags(record)
        assert RISK_MEDIUM_BLOCK in flags
        assert RISK_LONG_BLOCK not in flags

    def test_no_medium_or_long_flag_for_short_block(self):
        record = make_record(word_count=10)
        flags = compute_risk_flags(record)
        assert RISK_MEDIUM_BLOCK not in flags
        assert RISK_LONG_BLOCK not in flags

    def test_bridge_present_flag(self):
        record = make_record(bridge_source_refs=("SRC_BRIDGE",))
        assert RISK_BRIDGE_PRESENT in compute_risk_flags(record)

    def test_extra_content_signal_flag(self):
        record = make_record(reason="Le FR ajoute une idee supplementaire.")
        assert RISK_EXTRA_CONTENT_SIGNAL in compute_risk_flags(record)

    def test_legacy_resolved_flag(self):
        record = make_record(
            semantic_origin="PHASE_3A1_RESOLVED",
            classification=None,
            matched_direction=None,
            confidence=None,
            reason=None,
        )
        assert RISK_LEGACY_RESOLVED in compute_risk_flags(record)

    def test_no_english_context_flag(self):
        record = make_record(
            semantic_origin="NO_ENGLISH_CONTEXT",
            classification=None,
            matched_direction=None,
            confidence=None,
            reason=None,
            structure="OTHER",
        )
        flags = compute_risk_flags(record)
        assert RISK_NO_ENGLISH_CONTEXT in flags
        assert RISK_OTHER_STRUCTURE in flags  # structure OTHER, hors vocabulaire connu

    def test_former_all_keep_flag(self):
        record = make_record(phase_3a1_status="ALL_KEEP", classification="TRANSLATION_BEFORE")
        assert RISK_FORMER_ALL_KEEP in compute_risk_flags(record)

    def test_no_former_all_keep_flag_when_not_translation(self):
        record = make_record(phase_3a1_status="ALL_KEEP", classification="NOT_TRANSLATION")
        assert RISK_FORMER_ALL_KEEP not in compute_risk_flags(record)

    def test_former_review_flag_all_review(self):
        record = make_record(phase_3a1_status="ALL_REVIEW")
        assert RISK_FORMER_REVIEW in compute_risk_flags(record)

    def test_former_review_flag_has_review(self):
        record = make_record(phase_3a1_status="HAS_REVIEW")
        assert RISK_FORMER_REVIEW in compute_risk_flags(record)

    def test_translation_after_flag(self):
        record = make_record(classification="TRANSLATION_AFTER", matched_direction="AFTER")
        assert RISK_TRANSLATION_AFTER in compute_risk_flags(record)

    def test_other_structure_flag_for_unknown_structure(self):
        record = make_record(structure="FR_ISOLATED")
        assert RISK_OTHER_STRUCTURE in compute_risk_flags(record)

    def test_no_other_structure_flag_for_known_structures(self):
        for structure in ("EN_FR_EN", "EN_FR", "FR_EN"):
            record = make_record(structure=structure)
            assert RISK_OTHER_STRUCTURE not in compute_risk_flags(record)

    def test_deterministic_order(self):
        """Deux appels sur le même bloc produisent EXACTEMENT la même liste."""
        record = make_record(
            is_high_risk_existing=True,
            confidence=0.5,
            fr_source_refs=("SRC1", "SRC2"),
            bridge_source_refs=("SRC3",),
        )
        assert compute_risk_flags(record) == compute_risk_flags(record)


# ---------------------------------------------------------------------------
# TestFixedOriginPolicies (§15-18) — tests 1-4 du §40
# ---------------------------------------------------------------------------

class TestFixedOriginPolicies:
    def test_not_translation_keep_in_all_policies(self):
        record = make_record(classification="NOT_TRANSLATION", confidence=0.99)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        for policy_id in (POLICY_A, POLICY_B, POLICY_C):
            assert decisions[policy_id].decision == DECISION_KEEP

    def test_uncertain_keep_in_all_policies(self):
        record = make_record(classification="UNCERTAIN", confidence=0.99)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        for policy_id in (POLICY_A, POLICY_B, POLICY_C):
            assert decisions[policy_id].decision == DECISION_KEEP

    def test_no_english_context_keep_in_all_policies(self):
        record = make_record(
            semantic_origin="NO_ENGLISH_CONTEXT",
            classification=None,
            matched_direction=None,
            confidence=None,
            reason=None,
        )
        decisions = decide_all_policies(record, compute_risk_flags(record))
        for policy_id in (POLICY_A, POLICY_B, POLICY_C):
            assert decisions[policy_id].decision == DECISION_KEEP

    def test_legacy_resolved_human_review_in_all_policies(self):
        record = make_record(
            semantic_origin="PHASE_3A1_RESOLVED",
            classification=None,
            matched_direction=None,
            confidence=None,
            reason=None,
            phase_3a1_status="ALL_REMOVE",
        )
        decisions = decide_all_policies(record, compute_risk_flags(record))
        for policy_id in (POLICY_A, POLICY_B, POLICY_C):
            decision = decisions[policy_id]
            assert decision.decision == DECISION_HUMAN_REVIEW
            assert LEGACY_REASON_CODE in decision.reason
            assert decision.candidate_removed_source_refs == ()


# ---------------------------------------------------------------------------
# TestPolicyA (§40, tests 5-9)
# ---------------------------------------------------------------------------

class TestPolicyA:
    def test_confidence_095_eligible(self):
        record = make_record(confidence=0.95, word_count=20)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].decision == DECISION_AUTO_REMOVE
        assert decisions[POLICY_A].candidate_removed_source_refs == record.fr_source_refs

    def test_confidence_094_not_auto(self):
        record = make_record(confidence=0.94, word_count=20)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].decision == DECISION_HUMAN_REVIEW

    def test_high_risk_not_auto(self):
        record = make_record(confidence=0.99, word_count=10, is_high_risk_existing=True)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].decision == DECISION_HUMAN_REVIEW

    def test_over_30_words_not_auto(self):
        record = make_record(confidence=0.99, word_count=31)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].decision == DECISION_HUMAN_REVIEW

    def test_30_words_is_eligible_boundary(self):
        record = make_record(confidence=0.99, word_count=30)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].decision == DECISION_AUTO_REMOVE

    def test_bridge_not_auto(self):
        record = make_record(confidence=0.99, word_count=10, bridge_source_refs=("SRC_B",))
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].decision == DECISION_HUMAN_REVIEW

    def test_translation_after_can_be_eligible(self):
        record = make_record(
            classification="TRANSLATION_AFTER", matched_direction="AFTER",
            confidence=0.99, word_count=10,
        )
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].decision == DECISION_AUTO_REMOVE


# ---------------------------------------------------------------------------
# TestPolicyB (§40, tests 10-13)
# ---------------------------------------------------------------------------

class TestPolicyB:
    def test_confidence_090_eligible(self):
        record = make_record(confidence=0.90, word_count=20)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_B].decision == DECISION_AUTO_REMOVE

    def test_confidence_089_not_auto(self):
        record = make_record(confidence=0.89, word_count=20)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_B].decision == DECISION_HUMAN_REVIEW

    def test_over_30_not_auto(self):
        record = make_record(confidence=0.99, word_count=31)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_B].decision == DECISION_HUMAN_REVIEW

    def test_bridge_not_auto(self):
        record = make_record(confidence=0.99, word_count=10, bridge_source_refs=("SRC_B",))
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_B].decision == DECISION_HUMAN_REVIEW

    def test_high_risk_does_not_block_auto_remove(self):
        """§8 : high_risk_for_deletion_review ne bloque PAS automatiquement B."""
        record = make_record(confidence=0.99, word_count=10, is_high_risk_existing=True)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_B].decision == DECISION_AUTO_REMOVE
        # mais l'information reste tracée (§8)
        assert RISK_HIGH_RISK_EXISTING in compute_risk_flags(record)

    def test_requires_human_review_not_auto(self):
        """§8 : bloc marqué long/complexe (requires_human_review) → pas AUTO_REMOVE."""
        record = make_record(
            confidence=0.99, word_count=10, requires_human_review_flag=True,
        )
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_B].decision == DECISION_HUMAN_REVIEW


# ---------------------------------------------------------------------------
# TestPolicyC (§40, tests 14-17 + bridge non bloquant)
# ---------------------------------------------------------------------------

class TestPolicyC:
    def test_confidence_085_eligible(self):
        record = make_record(confidence=0.85, word_count=50)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_C].decision == DECISION_AUTO_REMOVE

    def test_confidence_084_not_auto(self):
        record = make_record(confidence=0.84, word_count=50)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_C].decision == DECISION_HUMAN_REVIEW

    def test_over_60_not_auto(self):
        record = make_record(confidence=0.99, word_count=61)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_C].decision == DECISION_HUMAN_REVIEW

    def test_60_words_is_eligible_boundary(self):
        record = make_record(confidence=0.99, word_count=60)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_C].decision == DECISION_AUTO_REMOVE

    def test_extra_content_signal_not_auto(self):
        record = make_record(
            confidence=0.99, word_count=20,
            reason="Le FR ajoute une idee supplementaire absente du EN.",
        )
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_C].decision == DECISION_HUMAN_REVIEW

    def test_bridge_does_not_block_auto_remove(self):
        """§8 : les bridges ne bloquent pas automatiquement POLICY_C."""
        record = make_record(confidence=0.99, word_count=20, bridge_source_refs=("SRC_B",))
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_C].decision == DECISION_AUTO_REMOVE


# ---------------------------------------------------------------------------
# TestCandidateRefs (§19, §40 tests 18-19)
# ---------------------------------------------------------------------------

class TestCandidateRefs:
    def test_candidate_refs_exact_on_auto_remove(self):
        record = make_record(
            confidence=0.99, word_count=10, fr_source_refs=("SRC1", "SRC2"),
        )
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].candidate_removed_source_refs == ("SRC1", "SRC2")

    def test_candidate_refs_empty_on_human_review(self):
        record = make_record(confidence=0.5, word_count=10)
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].candidate_removed_source_refs == ()

    def test_candidate_refs_empty_on_keep(self):
        record = make_record(classification="NOT_TRANSLATION")
        decisions = decide_all_policies(record, compute_risk_flags(record))
        assert decisions[POLICY_A].candidate_removed_source_refs == ()

    def test_bridge_refs_never_in_candidate_removed(self):
        """§19 : même AUTO_REMOVE, les bridges ne sont jamais candidats."""
        record = make_record(
            confidence=0.99, word_count=20,
            fr_source_refs=("SRC1", "SRC2"),
            bridge_source_refs=("SRC_BRIDGE",),
        )
        decisions = decide_all_policies(record, compute_risk_flags(record))
        # POLICY_C n'est pas bloqué par le bridge (§8) : AUTO_REMOVE attendu.
        decision = decisions[POLICY_C]
        assert decision.decision == DECISION_AUTO_REMOVE
        assert "SRC_BRIDGE" not in decision.candidate_removed_source_refs
        assert set(decision.candidate_removed_source_refs) == {"SRC1", "SRC2"}


# ---------------------------------------------------------------------------
# TestPopulation (§6-7, §39, §40 tests 20-21)
# ---------------------------------------------------------------------------

def _lb_block(
    block_id, *, status, phase_3a1_status="ALL_REVIEW", word_count=10,
    fr_source_refs=None, bridge_source_refs=None, structure="EN_FR_EN",
    audio_id="AUDIO001",
):
    return {
        "block_id": block_id,
        "audio_id": audio_id,
        "start_seconds": 0.0,
        "end_seconds": 5.0,
        "all_source_refs": fr_source_refs or [f"SRC_{block_id}"],
        "fr_source_refs": fr_source_refs or [f"SRC_{block_id}"],
        "bridge_source_refs": bridge_source_refs or [],
        "text": "Texte francais.",
        "word_count": word_count,
        "segment_count": 1,
        "fr_segment_count": 1,
        "structure": structure,
        "candidate_direction": "BEFORE",
        "english_before": {"text": "English text."} if status != "NO_ENGLISH_CONTEXT" else None,
        "english_after": None,
        "phase_3a1_status": phase_3a1_status,
        "already_resolved": status == "ALREADY_RESOLVED",
        "needs_semantic_review": status == "NEEDED",
        "semantic_review_status": status,
    }


def _classification_result(block_id, *, classification="UNCERTAIN", confidence=0.5, matched_direction="NONE"):
    return {
        "block_id": block_id,
        "classification": classification,
        "matched_direction": matched_direction,
        "confidence": confidence,
        "reason": "Justification de test.",
        "requires_human_review": False,
    }


class TestPopulation:
    def test_full_coverage_no_loss_no_duplicate(self):
        blocks = [
            _lb_block("FRB0001", status="NEEDED"),
            _lb_block("FRB0002", status="NEEDED"),
            _lb_block("FRB0003", status="ALREADY_RESOLVED", phase_3a1_status="ALL_REMOVE"),
            _lb_block("FRB0004", status="NO_ENGLISH_CONTEXT", structure="OTHER"),
        ]
        classification = {
            "results": [
                _classification_result("FRB0001"),
                _classification_result("FRB0002", classification="NOT_TRANSLATION"),
            ],
            "high_risk_for_deletion_review": [],
        }

        records = population_module.build_population(blocks, classification)
        population_module.validate_population(
            records,
            expected_total=4,
            expected_semantic_batch=2,
            expected_phase_3a1_resolved=1,
            expected_no_english_context=1,
        )

        counts = population_module.count_population(records)
        assert counts.total == 4
        assert counts.semantic_batch == 2
        assert counts.phase_3a1_resolved == 1
        assert counts.no_english_context == 1

    def test_origins_are_never_mixed(self):
        blocks = [
            _lb_block("FRB0001", status="ALREADY_RESOLVED", phase_3a1_status="ALL_REMOVE"),
            _lb_block("FRB0002", status="NO_ENGLISH_CONTEXT", structure="OTHER"),
        ]
        classification = {"results": [], "high_risk_for_deletion_review": []}
        records = population_module.build_population(blocks, classification)

        by_id = {r.block_id: r for r in records}
        assert by_id["FRB0001"].semantic_origin == "PHASE_3A1_RESOLVED"
        assert by_id["FRB0001"].classification is None
        assert by_id["FRB0002"].semantic_origin == "NO_ENGLISH_CONTEXT"
        assert by_id["FRB0002"].classification is None

    def test_duplicate_block_id_raises(self):
        blocks = [
            _lb_block("FRB0001", status="NEEDED"),
            _lb_block("FRB0001", status="NEEDED"),
        ]
        with pytest.raises(PopulationError):
            population_module.build_population(blocks, {"results": [], "high_risk_for_deletion_review": []})

    def test_needed_without_classification_raises(self):
        blocks = [_lb_block("FRB0001", status="NEEDED")]
        with pytest.raises(PopulationError):
            population_module.build_population(
                blocks, {"results": [], "high_risk_for_deletion_review": []}
            )

    def test_orphan_classification_result_raises(self):
        blocks = [_lb_block("FRB0001", status="NEEDED")]
        classification = {
            "results": [
                _classification_result("FRB0001"),
                _classification_result("FRB_ORPHAN"),
            ],
            "high_risk_for_deletion_review": [],
        }
        with pytest.raises(PopulationError):
            population_module.build_population(blocks, classification)

    def test_validate_population_wrong_total_raises(self):
        blocks = [_lb_block("FRB0001", status="NEEDED")]
        classification = {
            "results": [_classification_result("FRB0001")],
            "high_risk_for_deletion_review": [],
        }
        records = population_module.build_population(blocks, classification)
        with pytest.raises(PopulationError):
            population_module.validate_population(records, expected_total=99)


# ---------------------------------------------------------------------------
# TestValidator (§39, §40 test 22 déterminisme couvert plus bas)
# ---------------------------------------------------------------------------

class TestValidator:
    def _minimal_valid_artifact(self) -> dict:
        record = make_record(confidence=0.99, word_count=10)
        evaluations = evaluate_population([record])
        return {
            "schema_version": "1.0",
            "project": "test",
            "source_hashes": {"a": "1"},
            "blocks": simulation_module.build_block_entries(evaluations),
        }

    def test_valid_artifact_passes(self):
        from app.cleanup_policy.validator import validate_artifact

        artifact = self._minimal_valid_artifact()
        validate_artifact(artifact, expected_total=1, valid_block_ids={"FRB0001"})

    def test_detects_wrong_candidate_refs(self):
        from app.cleanup_policy.validator import validate_artifact

        artifact = self._minimal_valid_artifact()
        artifact["blocks"][0]["simulations"]["POLICY_A"]["candidate_removed_source_refs"] = [
            "WRONG_REF"
        ]

        with pytest.raises(SimulationValidationError):
            validate_artifact(artifact)

    def test_detects_not_translation_violation(self):
        from app.cleanup_policy.validator import validate_artifact

        record = make_record(classification="NOT_TRANSLATION", confidence=0.99)
        evaluations = evaluate_population([record])
        artifact = {
            "blocks": simulation_module.build_block_entries(evaluations),
        }
        # Corrompt volontairement la décision KEEP -> AUTO_REMOVE.
        artifact["blocks"][0]["simulations"]["POLICY_A"]["decision"] = DECISION_AUTO_REMOVE
        artifact["blocks"][0]["simulations"]["POLICY_A"]["candidate_removed_source_refs"] = list(
            record.fr_source_refs
        )

        with pytest.raises(SimulationValidationError):
            validate_artifact(artifact)

    def test_detects_legacy_not_human_review(self):
        from app.cleanup_policy.validator import validate_artifact

        record = make_record(
            semantic_origin="PHASE_3A1_RESOLVED", classification=None,
            matched_direction=None, confidence=None, reason=None,
        )
        evaluations = evaluate_population([record])
        artifact = {"blocks": simulation_module.build_block_entries(evaluations)}
        artifact["blocks"][0]["simulations"]["POLICY_A"]["decision"] = DECISION_KEEP

        with pytest.raises(SimulationValidationError):
            validate_artifact(artifact)

    def test_detects_bridge_in_candidate_refs(self):
        from app.cleanup_policy.validator import validate_artifact

        record = make_record(
            confidence=0.99, word_count=10,
            fr_source_refs=("SRC1",), bridge_source_refs=("SRC_BRIDGE",),
        )
        evaluations = evaluate_population([record])
        artifact = {"blocks": simulation_module.build_block_entries(evaluations)}
        # POLICY_C AUTO_REMOVE (bridge non bloquant) — on corrompt pour y glisser le bridge.
        artifact["blocks"][0]["simulations"]["POLICY_C"]["candidate_removed_source_refs"] = [
            "SRC1", "SRC_BRIDGE",
        ]

        with pytest.raises(SimulationValidationError):
            validate_artifact(artifact)


# ---------------------------------------------------------------------------
# TestAggregator (§28-38, §40 tests 24-29)
# ---------------------------------------------------------------------------

class TestAggregator:
    def _index(self, refs: list[str]) -> "aggregator_module.TranscriptIndex":
        segments = [
            {"id": ref, "source_id": "AUDIO001", "start": float(i * 5), "end": float(i * 5 + 5), "text": "un deux trois"}
            for i, ref in enumerate(refs)
        ]
        return build_transcript_index(
            {"segments": segments, "stats": {"segment_count": len(segments), "word_count": len(segments) * 3, "duration_seconds": len(segments) * 5.0}}
        )

    def test_safe_consensus_candidate(self):
        # Éligible sous A (donc aussi B et C) -> doit apparaître en consensus.
        consensus_record = make_record(
            block_id="FRB0001", confidence=0.99, word_count=10, fr_source_refs=("SRC1",),
        )
        # Éligible seulement sous C (mots > 30, confidence 0.85).
        c_only_record = make_record(
            block_id="FRB0002", confidence=0.85, word_count=45, fr_source_refs=("SRC2",),
        )
        records = [consensus_record, c_only_record]
        evaluations = evaluate_population(records)
        index = self._index(["SRC1", "SRC2"])

        intersection = aggregator_module.build_intersection(evaluations, index)
        safe_consensus = aggregator_module.build_safe_consensus_candidate(intersection)

        assert safe_consensus["count"] == 1
        assert safe_consensus["block_ids"] == ["FRB0001"]
        assert intersection["auto_remove_only_c"]["count"] == 1
        assert intersection["total_check"]["matches"] is True

    def test_diff_a_to_b(self):
        # HUMAN_REVIEW sous A (confidence 0.92 < 0.95) mais AUTO_REMOVE sous B (>=0.90).
        record = make_record(block_id="FRB0001", confidence=0.92, word_count=10, fr_source_refs=("SRC1",))
        evaluations = evaluate_population([record])
        index = self._index(["SRC1"])

        diff = aggregator_module.build_diff_a_to_b(evaluations, index)

        assert diff["count"] == 1
        assert diff["src_count"] == 1
        assert diff["top"][0]["block_id"] == "FRB0001"

    def test_diff_b_to_c(self):
        # HUMAN_REVIEW sous B (confidence 0.87 < 0.90) mais AUTO_REMOVE sous C (>=0.85).
        record = make_record(block_id="FRB0001", confidence=0.87, word_count=10, fr_source_refs=("SRC1",))
        evaluations = evaluate_population([record])
        index = self._index(["SRC1"])

        diff = aggregator_module.build_diff_b_to_c(evaluations, index)

        assert diff["count"] == 1
        assert diff["top"][0]["block_id"] == "FRB0001"

    def test_former_all_keep_tracking(self):
        eligible = make_record(
            block_id="FRB0001", phase_3a1_status="ALL_KEEP", classification="TRANSLATION_BEFORE",
            confidence=0.99, word_count=10,
        )
        not_eligible = make_record(
            block_id="FRB0002", phase_3a1_status="ALL_KEEP", classification="NOT_TRANSLATION",
            confidence=0.99, word_count=10,
        )
        evaluations = evaluate_population([eligible, not_eligible])

        former_all_keep = aggregator_module.build_former_all_keep(evaluations)

        assert former_all_keep["total"] == 1
        assert former_all_keep["distribution"][POLICY_A][DECISION_AUTO_REMOVE] == 1
        assert former_all_keep["auto_remove_candidates"][POLICY_A][0]["block_id"] == "FRB0001"

    def test_high_risk_tracking(self):
        risky_and_eligible = make_record(
            block_id="FRB0001", confidence=0.99, word_count=10, is_high_risk_existing=True,
        )
        evaluations = evaluate_population([risky_and_eligible])

        high_risk = aggregator_module.build_high_risk(evaluations)

        assert high_risk["total"] == 1
        # POLICY_A exclut les high-risk -> jamais AUTO_REMOVE.
        assert high_risk["distribution"][POLICY_A][DECISION_AUTO_REMOVE] == 0
        # POLICY_B/C n'excluent pas les high-risk -> AUTO_REMOVE, listé explicitement (§29).
        assert high_risk["distribution"][POLICY_B][DECISION_AUTO_REMOVE] == 1
        assert high_risk["auto_remove_listed"][POLICY_B][0]["block_id"] == "FRB0001"

    def test_translation_after_tracking(self):
        after_block = make_record(
            block_id="FRB0001", classification="TRANSLATION_AFTER", matched_direction="AFTER",
            confidence=0.99, word_count=10,
        )
        before_block = make_record(block_id="FRB0002", classification="TRANSLATION_BEFORE")
        evaluations = evaluate_population([after_block, before_block])

        result = aggregator_module.build_translation_after(evaluations)

        assert result["total"] == 1
        assert result["blocks"][0]["block_id"] == "FRB0001"

    def test_medium_long_hypothesis_check_detects_positive(self):
        """§32 : si un futur run produit un bloc >60 mots TRANSLATION_*, il doit
        être détecté — jamais une confiance aveugle au rapport précédent."""
        long_translation = make_record(
            block_id="FRB0001", classification="TRANSLATION_BEFORE",
            confidence=0.99, word_count=74,
        )
        evaluations = evaluate_population([long_translation])

        medium_long = aggregator_module.build_medium_long(evaluations)

        assert medium_long["long_blocks_classified_translation"] == ["FRB0001"]
        # Mais AUCUNE politique ne peut jamais l'AUTO_REMOVE (plafond max 60, POLICY_C).
        for policy_id in (POLICY_A, POLICY_B, POLICY_C):
            assert medium_long["long_blocks_auto_remove_by_policy"][policy_id] == []

    def test_medium_long_no_false_positive_on_real_shaped_data(self):
        not_translation_long = make_record(
            block_id="FRB0001", classification="NOT_TRANSLATION", confidence=0.7, word_count=78,
        )
        evaluations = evaluate_population([not_translation_long])
        medium_long = aggregator_module.build_medium_long(evaluations)
        assert medium_long["long_blocks_classified_translation"] == []

    def test_multi_src_tracking(self):
        multi = make_record(
            block_id="FRB0001", confidence=0.99, word_count=10,
            fr_source_refs=("SRC1", "SRC2"),
        )
        evaluations = evaluate_population([multi])
        result = aggregator_module.build_multi_src(evaluations)
        assert result["total_translation_multi_src"] == 1
        assert result["auto_remove_counts"][POLICY_A] == 1
        assert result["auto_remove_listed"][POLICY_A][0]["block_id"] == "FRB0001"

    def test_extra_content_signal_tracking(self):
        flagged = make_record(
            block_id="FRB0001",
            reason="Le FR ajoute une idee supplementaire absente du EN.",
        )
        clean = make_record(block_id="FRB0002", reason="Correspondance directe.")
        evaluations = evaluate_population([flagged, clean])
        result = aggregator_module.build_extra_content_signal(evaluations)
        assert result["detected_count"] == 1
        assert result["block_ids"] == ["FRB0001"]
        assert "ajout" in result["terms"]

    def test_global_totals_sum_to_population(self):
        records = [
            make_record(block_id="FRB0001", confidence=0.99, word_count=10),
            make_record(block_id="FRB0002", classification="NOT_TRANSLATION"),
            make_record(block_id="FRB0003", classification="UNCERTAIN"),
        ]
        evaluations = evaluate_population(records)
        index = self._index(["SRC000001"])
        totals = aggregator_module.build_global_totals(evaluations, index)
        for policy_id in (POLICY_A, POLICY_B, POLICY_C):
            assert totals[policy_id]["total_blocks_check"] == 3


# ---------------------------------------------------------------------------
# TestDeterminism (§22, §34, §40 test 22)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_block_entries_identical_across_two_builds(self):
        records = [
            make_record(block_id="FRB0002", confidence=0.9, word_count=15),
            make_record(block_id="FRB0001", confidence=0.5, word_count=5),
        ]
        evaluations_1 = evaluate_population(records)
        evaluations_2 = evaluate_population(list(reversed(records)))

        entries_1 = simulation_module.build_block_entries(evaluations_1)
        entries_2 = simulation_module.build_block_entries(evaluations_2)

        assert entries_1 == entries_2
        assert [e["block_id"] for e in entries_1] == ["FRB0001", "FRB0002"]

    def test_json_round_trip_is_stable(self):
        records = [make_record(block_id="FRB0001", confidence=0.99, word_count=10)]
        evaluations = evaluate_population(records)
        entries = simulation_module.build_block_entries(evaluations)

        dumped_1 = json.dumps(entries, ensure_ascii=False, sort_keys=False)
        dumped_2 = json.dumps(copy.deepcopy(entries), ensure_ascii=False, sort_keys=False)

        assert dumped_1 == dumped_2


# ---------------------------------------------------------------------------
# TestIntegrity (§5, §44, §40 test 23)
# ---------------------------------------------------------------------------

class TestIntegrity:
    def test_source_paths_has_five_keys(self, tmp_path):
        paths = integrity_module.source_paths("proj", sortie_dir=tmp_path)
        assert set(paths.keys()) == {
            "transcript_data",
            "language_cleanup",
            "language_blocks",
            "semantic_translation_canary",
            "semantic_translation_classification",
        }

    def test_ensure_unchanged_detects_classification_change(self):
        before = integrity_module.IntegritySnapshot(
            hashes={
                "transcript_data": "a",
                "language_cleanup": "b",
                "language_blocks": "c",
                "semantic_translation_canary": "d",
                "semantic_translation_classification": "e",
            }
        )
        after = integrity_module.IntegritySnapshot(
            hashes={**before.hashes, "semantic_translation_classification": "CHANGED"}
        )
        with pytest.raises(Exception):
            integrity_module.ensure_unchanged(before, after)

    def test_ensure_unchanged_ok_when_identical(self):
        snapshot = integrity_module.IntegritySnapshot(
            hashes={
                "transcript_data": "a",
                "language_cleanup": "b",
                "language_blocks": "c",
                "semantic_translation_canary": "d",
                "semantic_translation_classification": "e",
            }
        )
        integrity_module.ensure_unchanged(snapshot, snapshot)  # ne lève pas


# ---------------------------------------------------------------------------
# TestRunnerIntegration — vrai petit projet, bout en bout (§39-44)
# ---------------------------------------------------------------------------

class TestRunnerIntegration:
    def _build_project(self, tmp_path):
        from app.tests.cleanup_policy_fixtures import PROJECT, build_full_fixture_project

        sortie_dir = tmp_path / "sortie"
        overrides = {
            "FRB0007": {"classification": "TRANSLATION_BEFORE", "confidence": 0.97},
            "FRB0008": {"classification": "TRANSLATION_BEFORE", "confidence": 0.94},
            "FRB0009": {"classification": "TRANSLATION_BEFORE", "confidence": 0.99, "high_risk": True},
            "FRB0013": {"classification": "NOT_TRANSLATION", "confidence": 0.9},
            "FRB0014": {"classification": "UNCERTAIN", "confidence": 0.4},
            "FRB0021": {"classification": "TRANSLATION_BEFORE", "confidence": 0.99},  # 74 mots
        }
        build_full_fixture_project(sortie_dir, overrides=overrides)
        return PROJECT, sortie_dir

    def _snapshot_bytes(self, project_name, sortie_dir):
        paths = integrity_module.source_paths(project_name, sortie_dir=sortie_dir)
        return {key: path.read_bytes() for key, path in paths.items()}

    def test_end_to_end_produces_valid_artifact_and_preserves_hashes(self, tmp_path, no_ai_network):
        from app.cleanup_policy.runner import run_cleanup_policy_simulation

        project_name, sortie_dir = self._build_project(tmp_path)
        before = self._snapshot_bytes(project_name, sortie_dir)

        result = run_cleanup_policy_simulation(
            project_name,
            sortie_dir=sortie_dir,
            expected_total=22,
            expected_semantic_batch=16,
            expected_phase_3a1_resolved=6,
            expected_no_english_context=0,
        )

        assert result.artifact_path.exists()
        assert len(result.artifact["blocks"]) == 22

        after = self._snapshot_bytes(project_name, sortie_dir)
        assert before.keys() == after.keys()
        for key in before:
            assert before[key] == after[key], f"{key} a changé de contenu (octets)"

        # §21 : FRB0021 (74 mots, TRANSLATION_BEFORE, confidence 0.99) ne
        # doit JAMAIS être AUTO_REMOVE (dépasse le plafond des 3 politiques).
        block_by_id = {b["block_id"]: b for b in result.artifact["blocks"]}
        for policy_id in (POLICY_A, POLICY_B, POLICY_C):
            assert (
                block_by_id["FRB0021"]["simulations"][policy_id]["decision"] != DECISION_AUTO_REMOVE
            )

        # FRB0007 (0.97, court, pas high-risk) doit être AUTO_REMOVE sous A/B/C.
        for policy_id in (POLICY_A, POLICY_B, POLICY_C):
            assert block_by_id["FRB0007"]["simulations"][policy_id]["decision"] == DECISION_AUTO_REMOVE

        # FRB0009 (high-risk) : pas AUTO_REMOVE sous A, mais oui sous B/C.
        assert block_by_id["FRB0009"]["simulations"][POLICY_A]["decision"] != DECISION_AUTO_REMOVE
        assert block_by_id["FRB0009"]["simulations"][POLICY_B]["decision"] == DECISION_AUTO_REMOVE

    def test_deterministic_across_two_runs(self, tmp_path, no_ai_network):
        from app.cleanup_policy.runner import run_cleanup_policy_simulation

        project_name, sortie_dir = self._build_project(tmp_path)

        result_1 = run_cleanup_policy_simulation(project_name, sortie_dir=sortie_dir)
        artifact_1 = json.loads(result_1.artifact_path.read_text(encoding="utf-8"))

        result_2 = run_cleanup_policy_simulation(project_name, sortie_dir=sortie_dir)
        artifact_2 = json.loads(result_2.artifact_path.read_text(encoding="utf-8"))

        assert artifact_1 == artifact_2

    def test_zero_network_calls_during_full_run(self, tmp_path, no_ai_network):
        """`no_ai_network` fait échouer bruyamment tout POST HTTP sortant (§3, §43)."""
        from app.cleanup_policy.runner import run_cleanup_policy_simulation

        project_name, sortie_dir = self._build_project(tmp_path)

        result = run_cleanup_policy_simulation(project_name, sortie_dir=sortie_dir)

        assert result.artifact_path.exists()
        assert result.artifact["statistics"]["network"]["anthropic_calls"] == 0
        assert result.artifact["statistics"]["network"]["openai_calls"] == 0
        assert "extra_content_signal" in result.artifact["statistics"]

    def test_sources_do_not_import_ai_or_network_runners(self):
        """§3, §43 : aucun import exécutable vers app.ai ni un runner réseau."""
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "cleanup_policy"
        forbidden_prefixes = (
            "app.ai",
            "app.semantic_batch.runner",
            "app.semantic_canary.runner",
            "app.semantic_canary.guard",
            "app.semantic_canary.preflight",
            "requests",
            "urllib",
        )
        violations = []
        for path in sorted(root.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.append(node.module)
                for module in modules:
                    if any(
                        module == prefix or module.startswith(prefix + ".")
                        for prefix in forbidden_prefixes
                    ):
                        violations.append(f"{path.name}: {module}")
        assert violations == []

    def test_validator_runs_inside_runner_and_would_reject_bad_data(self, tmp_path, no_ai_network):
        """Le runner appelle déjà validate_artifact : une source invalide lève avant écriture."""
        from app.cleanup_policy.runner import run_cleanup_policy_simulation

        project_name, sortie_dir = self._build_project(tmp_path)

        with pytest.raises(Exception):
            run_cleanup_policy_simulation(
                project_name, sortie_dir=sortie_dir, expected_total=999999
            )
