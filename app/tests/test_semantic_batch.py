"""
Tests de la Phase 3A.1.2B — classification par lots FR <-> EN
(app.semantic_batch).

Organisation, alignée sur le §35 du cahier des charges :

    TestSelection            population NEEDED complète, exclusion
                             ALREADY_RESOLVED / NO_ENGLISH_CONTEXT
    TestPlanner              planification par lots (20 max, IDs
                             déterministes, pas de doublon/omission,
                             réduction sur gros bloc)
    TestSignature            signature déterministe, sensible à tout
                             changement de contexte
    TestCache                cache hit, cache absent, cache incompatible
                             (STOP), résultats en cache invalides (STOP)
    TestWriter               écriture atomique, relecture, artefact final
    TestAggregator           blocs longs (§33), liste de risque (§32),
                             distributions, divergences, agrégation
                             usage/coût (cache compris)
    TestRunnerIntegration    FakeAIEngine bout en bout : succès multi-lots,
                             reprise/cache, max_attempts=1 sans réparation,
                             cache incompatible -> STOP avant tout appel,
                             intégrité des 4 artefacts protégée

Aucun test de ce fichier ne touche au réseau (fixture `no_ai_network` +
`_isolated_ai_credentials` déjà autouse, voir app/tests/conftest.py) : seul
FakeAIEngine simule les appels Anthropic.
"""

from __future__ import annotations

import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.semantic_batch import aggregator as aggregator_module
from app.semantic_batch import cache as cache_module
from app.semantic_batch import integrity as integrity_module
from app.semantic_batch import planner as planner_module
from app.semantic_batch import selection as selection_module
from app.semantic_batch import signature as signature_module
from app.semantic_batch import writer as writer_module
from app.semantic_batch.errors import (
    BatchPlanError,
    CacheSignatureMismatchError,
    SourceIntegrityError,
)
from app.semantic_batch.models import batch_id_for_index
from app.semantic_batch.runner import (
    load_and_validate_sources,
    run_semantic_batch_classification,
)
from app.semantic_canary.models import CanaryClassification, SelectedBlock


# ---------------------------------------------------------------------------
# Fabrique de blocs synthétiques (dicts bruts language_blocks.json), reprise
# du même schéma que test_semantic_canary.py._make_block.
# ---------------------------------------------------------------------------

def _ctx(refs: list[str], text: str) -> dict:
    return {
        "source_refs": list(refs),
        "start_seconds": 0.0,
        "end_seconds": 1.0,
        "text": text,
        "word_count": len(text.split()),
        "segment_count": len(refs),
        "distance_segments": 1,
        "distance_seconds": 1.0,
        "truncated": False,
    }


def _make_block(
    block_id: str,
    *,
    audio_id: str = "AUDIO001",
    semantic_review_status: str,
    phase_3a1_status: str = "ALL_KEEP",
    candidate_direction: str = "BOTH",
    structure: str = "EN_FR_EN",
    text: str = "Ceci est un bloc francais de test suffisamment long pour compter.",
    word_count: int | None = None,
    fr_segment_count: int = 1,
    bridge_source_refs: list[str] | None = None,
    english_before: dict | None = None,
    english_after: dict | None = None,
    fr_source_refs: list[str] | None = None,
) -> dict:
    return {
        "block_id": block_id,
        "audio_id": audio_id,
        "start_seconds": 0.0,
        "end_seconds": 5.0,
        "all_source_refs": fr_source_refs or [f"SRC_{block_id}"],
        "fr_source_refs": fr_source_refs or [f"SRC_{block_id}"],
        "bridge_source_refs": bridge_source_refs or [],
        "text": text,
        "word_count": word_count if word_count is not None else len(text.split()),
        "segment_count": 1,
        "fr_segment_count": fr_segment_count,
        "structure": structure,
        "candidate_direction": candidate_direction,
        "english_before": english_before,
        "english_after": english_after,
        "phase_3a1_decisions": {},
        "phase_3a1_remove_refs": [],
        "phase_3a1_review_refs": [],
        "phase_3a1_keep_refs": [],
        "phase_3a1_status": phase_3a1_status,
        "already_resolved": semantic_review_status == "ALREADY_RESOLVED",
        "needs_semantic_review": semantic_review_status == "NEEDED",
        "semantic_review_status": semantic_review_status,
    }


def _needed_pool(count: int, *, prefix: str = "FRB", **overrides) -> list[dict]:
    blocks = []
    for index in range(1, count + 1):
        block_id = f"{prefix}{index:04d}"
        blocks.append(
            _make_block(
                block_id,
                semantic_review_status="NEEDED",
                english_before=_ctx([f"EN_{block_id}_B"], "English before context words."),
                english_after=_ctx([f"EN_{block_id}_A"], "English after context words."),
                **overrides,
            )
        )
    return blocks


def _selected(blocks: list[dict]) -> list[SelectedBlock]:
    return selection_module.select_needed_blocks(blocks)


def _classification(
    block_id: str,
    *,
    classification: str = "UNCERTAIN",
    matched_direction: str = "NONE",
    confidence: float = 0.5,
    reason: str = "Justification factuelle courte.",
) -> CanaryClassification:
    return CanaryClassification(
        block_id=block_id,
        classification=classification,
        matched_direction=matched_direction,
        confidence=confidence,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# TestSelection — population NEEDED complète (§2, §14)
# ---------------------------------------------------------------------------

class TestSelection:
    def test_selectionne_uniquement_needed_tries_par_block_id(self):
        blocks = _needed_pool(3)
        blocks.append(
            _make_block(
                "ZZZ_RESOLVED",
                semantic_review_status="ALREADY_RESOLVED",
                english_before=_ctx(["EN1"], "context"),
            )
        )
        blocks.append(
            _make_block(
                "AAA_NOCTX",
                semantic_review_status="NO_ENGLISH_CONTEXT",
                candidate_direction="NONE",
                english_before=None,
                english_after=None,
            )
        )

        selected = selection_module.select_needed_blocks(blocks)

        assert [b.block_id for b in selected] == ["FRB0001", "FRB0002", "FRB0003"]
        assert all(b.semantic_review_status == "NEEDED" for b in selected)

    def test_validation_reussit_sur_population_conforme(self):
        blocks = _needed_pool(5)
        selected = _selected(blocks)

        selection_module.validate_needed_population(selected, expected_count=5)

    def test_validation_echoue_si_compte_incorrect(self):
        blocks = _needed_pool(5)
        selected = _selected(blocks)

        with pytest.raises(SourceIntegrityError):
            selection_module.validate_needed_population(selected, expected_count=6)

    def test_validation_echoue_si_ni_before_ni_after(self):
        blocks = _needed_pool(2)
        blocks.append(
            _make_block(
                "FRB9999",
                semantic_review_status="NEEDED",
                english_before=None,
                english_after=None,
            )
        )
        selected = _selected(blocks)

        with pytest.raises(SourceIntegrityError):
            selection_module.validate_needed_population(selected, expected_count=3)


# ---------------------------------------------------------------------------
# TestPlanner — planification par lots (§13-17)
# ---------------------------------------------------------------------------

class TestPlanner:
    def test_lots_de_20_maximum_et_ids_sequentiels(self):
        blocks = _needed_pool(45)
        selected = _selected(blocks)

        plan = planner_module.build_batch_plan(selected)

        assert [item.batch_id for item in plan] == ["BATCH001", "BATCH002", "BATCH003"]
        assert [item.block_count for item in plan] == [20, 20, 5]

    def test_couverture_complete_sans_doublon_ni_omission(self):
        blocks = _needed_pool(37)
        selected = _selected(blocks)

        plan = planner_module.build_batch_plan(selected)
        planner_module.validate_batch_plan(plan, selected)

        all_ids = [bid for item in plan for bid in item.block_ids]
        assert sorted(all_ids) == sorted(b.block_id for b in selected)
        assert len(set(all_ids)) == len(all_ids)

    def test_ordre_deterministe_jamais_melange(self):
        blocks = _needed_pool(25)
        selected = _selected(blocks)

        first = planner_module.build_batch_plan(selected)
        second = planner_module.build_batch_plan(list(selected))

        assert [i.block_ids for i in first] == [i.block_ids for i in second]
        # Ordre = ordre d'entrée (déjà trié par block_id par selection.py).
        assert first[0].block_ids == sorted(first[0].block_ids)

    def test_un_gros_bloc_reduit_la_taille_de_son_lot_sans_le_tronquer(self):
        huge_text = "mot " * 3000  # bien au-delà de MAX_ESTIMATED_TOKENS_PER_BATCH seul
        blocks = _needed_pool(5)
        blocks.insert(
            2,
            _make_block(
                "FRB_HUGE",
                semantic_review_status="NEEDED",
                text=huge_text,
                word_count=3000,
                english_before=_ctx(["EN_HUGE_B"], "English before context words."),
                english_after=_ctx(["EN_HUGE_A"], "English after context words."),
            ),
        )
        selected = _selected(blocks)

        plan = planner_module.build_batch_plan(selected, max_estimated_tokens=2000)
        planner_module.validate_batch_plan(plan, selected)

        huge_batch = next(item for item in plan if "FRB_HUGE" in item.block_ids)
        # Le texte complet reste intact dans le payload — jamais tronqué (§16).
        payload = huge_batch.blocks[huge_batch.block_ids.index("FRB_HUGE")].raw_block
        assert payload["text"] == huge_text

    def test_batch_id_for_index_format(self):
        assert batch_id_for_index(1) == "BATCH001"
        assert batch_id_for_index(16) == "BATCH016"
        with pytest.raises(ValueError):
            batch_id_for_index(0)

    def test_validate_batch_plan_detecte_doublon_entre_lots(self):
        blocks = _needed_pool(3)
        selected = _selected(blocks)
        plan = planner_module.build_batch_plan(selected)

        # Fabrique un doublon artificiel entre deux lots.
        duplicated = list(plan[0].blocks) + list(plan[0].blocks)
        from app.semantic_batch.models import BatchPlanItem

        broken_plan = [
            BatchPlanItem(batch_id="BATCH001", blocks=tuple(duplicated), estimated_input_tokens=1)
        ]

        with pytest.raises(BatchPlanError):
            planner_module.validate_batch_plan(broken_plan, selected)

    def test_validate_batch_plan_detecte_omission(self):
        blocks = _needed_pool(3)
        selected = _selected(blocks)
        plan = planner_module.build_batch_plan(selected)

        from app.semantic_batch.models import BatchPlanItem

        truncated_plan = [
            BatchPlanItem(
                batch_id="BATCH001", blocks=tuple(plan[0].blocks[:-1]), estimated_input_tokens=1
            )
        ]

        with pytest.raises(BatchPlanError):
            planner_module.validate_batch_plan(truncated_plan, selected)

    def test_validate_batch_plan_detecte_lot_trop_grand(self):
        blocks = _needed_pool(25)
        selected = _selected(blocks)

        from app.semantic_batch.models import BatchPlanItem

        oversized_plan = [
            BatchPlanItem(batch_id="BATCH001", blocks=tuple(selected), estimated_input_tokens=1)
        ]

        with pytest.raises(BatchPlanError):
            planner_module.validate_batch_plan(oversized_plan, selected, max_batch_size=20)


# ---------------------------------------------------------------------------
# TestSignature — signature déterministe (§20)
# ---------------------------------------------------------------------------

class TestSignature:
    BASE_KWARGS = dict(
        language_blocks_sha256="abc123",
        prompt_version="1.0",
        response_schema_sha256="def456",
        provider="anthropic",
        model="claude-sonnet-5",
        block_ids=["FRB0001", "FRB0002"],
        payload_hash="ghi789",
    )

    def test_signature_stable_et_deterministe(self):
        first = signature_module.compute_batch_signature(**self.BASE_KWARGS)
        second = signature_module.compute_batch_signature(**self.BASE_KWARGS)

        assert first == second
        assert isinstance(first, str) and first

    @pytest.mark.parametrize(
        "field,new_value",
        [
            ("language_blocks_sha256", "different"),
            ("prompt_version", "2.0"),
            ("response_schema_sha256", "different"),
            ("provider", "openai"),
            ("model", "other-model"),
            ("block_ids", ["FRB0002", "FRB0001"]),
            ("payload_hash", "different"),
        ],
    )
    def test_signature_change_avec_tout_element_de_contexte(self, field, new_value):
        baseline = signature_module.compute_batch_signature(**self.BASE_KWARGS)

        modified = dict(self.BASE_KWARGS)
        modified[field] = new_value
        changed = signature_module.compute_batch_signature(**modified)

        assert baseline != changed

    def test_payload_content_hash_deterministe(self):
        payloads = [{"block_id": "FRB0001", "french": {"source_refs": ["S1"], "text": "t"}}]

        assert signature_module.payload_content_hash(
            payloads
        ) == signature_module.payload_content_hash(list(payloads))


# ---------------------------------------------------------------------------
# TestCache — cache/reprise (§18-19)
# ---------------------------------------------------------------------------

class TestCache:
    def _payloads(self):
        return [
            {
                "block_id": "FRB0001",
                "french": {"source_refs": ["SRC1"], "text": "texte"},
                "english_before": None,
                "english_after": None,
            }
        ]

    def _kwargs(self, **overrides):
        base = dict(
            batch_id="BATCH001",
            block_ids=["FRB0001"],
            payloads=self._payloads(),
            language_blocks_sha256="hash-lb",
            prompt_version="1.0",
            response_schema_sha256="hash-schema",
            provider="anthropic",
            model="claude-sonnet-5",
        )
        base.update(overrides)
        return base

    def _valid_cached_payload(self):
        kwargs = self._kwargs()
        payload_hash = signature_module.payload_content_hash(kwargs["payloads"])
        signature = signature_module.compute_batch_signature(
            language_blocks_sha256=kwargs["language_blocks_sha256"],
            prompt_version=kwargs["prompt_version"],
            response_schema_sha256=kwargs["response_schema_sha256"],
            provider=kwargs["provider"],
            model=kwargs["model"],
            block_ids=kwargs["block_ids"],
            payload_hash=payload_hash,
        )
        return {
            "batch_id": "BATCH001",
            "prompt_version": "1.0",
            "provider": "anthropic",
            "model": "claude-sonnet-5",
            "source_hashes": {"language_blocks": "hash-lb"},
            "block_ids": ["FRB0001"],
            "signature": signature,
            "payload_content_hash": payload_hash,
            "results": [
                {
                    "block_id": "FRB0001",
                    "classification": "UNCERTAIN",
                    "matched_direction": "NONE",
                    "confidence": 0.5,
                    "reason": "Réponse en cache.",
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "cost": {"total_cost": 0.001},
        }

    def test_absence_de_cache_retourne_none(self):
        result = cache_module.check_cached_batch(None, **self._kwargs())
        assert result is None

    def test_cache_hit_valide(self):
        cached = self._valid_cached_payload()
        results = cache_module.check_cached_batch(cached, **self._kwargs())

        assert results is not None
        assert results[0].block_id == "FRB0001"
        assert results[0].classification == "UNCERTAIN"

    def test_cache_mismatch_signature_stop(self):
        cached = self._valid_cached_payload()
        cached["signature"] = "wrong-signature"

        with pytest.raises(CacheSignatureMismatchError):
            cache_module.check_cached_batch(cached, **self._kwargs())

    def test_cache_mismatch_prompt_version_stop(self):
        cached = self._valid_cached_payload()
        cached["prompt_version"] = "9.9"

        with pytest.raises(CacheSignatureMismatchError):
            cache_module.check_cached_batch(cached, **self._kwargs())

    def test_cache_mismatch_provider_model_stop(self):
        cached = self._valid_cached_payload()
        cached["model"] = "other-model"

        with pytest.raises(CacheSignatureMismatchError):
            cache_module.check_cached_batch(cached, **self._kwargs())

    def test_cache_mismatch_block_ids_stop(self):
        cached = self._valid_cached_payload()
        cached["block_ids"] = ["FRB9999"]

        with pytest.raises(CacheSignatureMismatchError):
            cache_module.check_cached_batch(cached, **self._kwargs())

    def test_cache_avec_resultats_invalides_stop(self):
        cached = self._valid_cached_payload()
        cached["results"] = []  # aucun résultat -> invalide contre le contrat local

        with pytest.raises(CacheSignatureMismatchError):
            cache_module.check_cached_batch(cached, **self._kwargs())


# ---------------------------------------------------------------------------
# TestWriter — écriture atomique et relecture (§18, §26)
# ---------------------------------------------------------------------------

class TestWriter:
    def test_ecriture_et_relecture_dun_lot(self, tmp_path):
        path = writer_module.batch_path("proj", "BATCH001", sortie_dir=tmp_path)
        payload = {"batch_id": "BATCH001", "results": []}

        written = writer_module.write_batch_atomic(path, payload)
        assert written == path
        assert path.exists()
        assert not path.with_name(path.name + ".partial").exists()

        reread = writer_module.read_batch_payload(path)
        assert reread == payload

    def test_relecture_fichier_absent_retourne_none(self, tmp_path):
        path = writer_module.batch_path("proj", "BATCH999", sortie_dir=tmp_path)
        assert writer_module.read_batch_payload(path) is None

    def test_relecture_json_invalide_retourne_none(self, tmp_path):
        path = writer_module.batch_path("proj", "BATCH001", sortie_dir=tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ceci n'est pas du json", encoding="utf-8")

        assert writer_module.read_batch_payload(path) is None

    def test_artefact_final_atomique(self, tmp_path):
        path = writer_module.classification_artifact_path("proj", sortie_dir=tmp_path)
        payload = {"schema_version": "1.0", "results": []}

        writer_module.write_classification_artifact(path, payload)

        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == payload


# ---------------------------------------------------------------------------
# TestAggregator — blocs longs (§33), liste de risque (§32), distributions
# ---------------------------------------------------------------------------

class TestAggregator:
    def _entry(self, selected_block, result):
        return aggregator_module.build_result_entry(selected_block, result)

    def test_confidence_range_label_bornes(self):
        cases = [
            (0.10, "<0.70"),
            (0.69, "<0.70"),
            (0.70, "0.70-0.79"),
            (0.79, "0.70-0.79"),
            (0.80, "0.80-0.89"),
            (0.89, "0.80-0.89"),
            (0.90, "0.90-0.94"),
            (0.94, "0.90-0.94"),
            (0.95, ">=0.95"),
            (1.00, ">=0.95"),
        ]
        for confidence, expected in cases:
            assert aggregator_module.confidence_range_label(confidence) == expected

    def test_bloc_long_translation_requiert_revue_humaine(self):
        block = _make_block(
            "FRB_LONG",
            semantic_review_status="NEEDED",
            word_count=61,
            english_before=_ctx(["E1"], "before"),
        )
        selected = SelectedBlock(
            block_id="FRB_LONG", selection_group="G", selection_reason="r", raw_block=block
        )
        result = _classification(
            "FRB_LONG", classification="TRANSLATION_BEFORE", matched_direction="BEFORE",
            confidence=0.97,
        )

        entry = self._entry(selected, result)

        assert entry["requires_human_review"] is True

    def test_bloc_long_not_translation_ne_requiert_pas_revue(self):
        block = _make_block(
            "FRB_LONG2",
            semantic_review_status="NEEDED",
            word_count=200,
            english_before=_ctx(["E1"], "before"),
        )
        selected = SelectedBlock(
            block_id="FRB_LONG2", selection_group="G", selection_reason="r", raw_block=block
        )
        result = _classification("FRB_LONG2", classification="NOT_TRANSLATION", confidence=0.8)

        entry = self._entry(selected, result)

        assert entry["requires_human_review"] is False
        # Toujours listé dans long_blocks (§33 : "lister TOUS les blocs > 60 mots").
        long_blocks = aggregator_module.build_long_blocks_section([entry])
        assert long_blocks[0]["block_id"] == "FRB_LONG2"

    def test_risque_confidence_basse_translation(self):
        block = _make_block("FRB_A", semantic_review_status="NEEDED", word_count=10)
        selected = SelectedBlock(
            block_id="FRB_A", selection_group="G", selection_reason="r", raw_block=block
        )
        result = _classification(
            "FRB_A", classification="TRANSLATION_AFTER", matched_direction="AFTER",
            confidence=0.60,
        )

        entry = self._entry(selected, result)

        assert entry["is_high_risk_for_deletion_review"] is True
        assert any("confidence" in reason for reason in entry["risk_reasons"])

    def test_risque_bloc_multi_src_important(self):
        block = _make_block(
            "FRB_B", semantic_review_status="NEEDED", word_count=10, fr_segment_count=5
        )
        selected = SelectedBlock(
            block_id="FRB_B", selection_group="G", selection_reason="r", raw_block=block
        )
        result = _classification("FRB_B", classification="NOT_TRANSLATION", confidence=0.99)

        entry = self._entry(selected, result)

        assert entry["is_high_risk_for_deletion_review"] is True
        assert any("multi-SRC" in reason for reason in entry["risk_reasons"])

    def test_risque_bloc_long_translation_plus_de_30_mots(self):
        block = _make_block("FRB_C", semantic_review_status="NEEDED", word_count=35)
        selected = SelectedBlock(
            block_id="FRB_C", selection_group="G", selection_reason="r", raw_block=block
        )
        result = _classification(
            "FRB_C", classification="TRANSLATION_BEFORE", matched_direction="BEFORE",
            confidence=0.99,
        )

        entry = self._entry(selected, result)

        assert entry["is_high_risk_for_deletion_review"] is True
        assert any("30 mots" in reason for reason in entry["risk_reasons"])

    def test_risque_bridge_source_refs(self):
        block = _make_block(
            "FRB_D", semantic_review_status="NEEDED", word_count=10,
            bridge_source_refs=["SRC_BRIDGE"],
        )
        selected = SelectedBlock(
            block_id="FRB_D", selection_group="G", selection_reason="r", raw_block=block
        )
        result = _classification("FRB_D", classification="NOT_TRANSLATION", confidence=0.99)

        entry = self._entry(selected, result)

        assert entry["is_high_risk_for_deletion_review"] is True
        assert any("bridge_source_refs" in reason for reason in entry["risk_reasons"])

    def test_risque_mot_cle_dans_la_justification(self):
        block = _make_block("FRB_E", semantic_review_status="NEEDED", word_count=10)
        selected = SelectedBlock(
            block_id="FRB_E", selection_group="G", selection_reason="r", raw_block=block
        )
        result = _classification(
            "FRB_E", classification="NOT_TRANSLATION", confidence=0.99,
            reason="Le FR ajoute un contenu supplémentaire substantiel.",
        )

        entry = self._entry(selected, result)

        assert entry["is_high_risk_for_deletion_review"] is True

    def test_bloc_sans_risque_absent_de_la_liste(self):
        block = _make_block("FRB_SAFE", semantic_review_status="NEEDED", word_count=5)
        selected = SelectedBlock(
            block_id="FRB_SAFE", selection_group="G", selection_reason="r", raw_block=block
        )
        result = _classification(
            "FRB_SAFE", classification="TRANSLATION_BEFORE", matched_direction="BEFORE",
            confidence=0.99, reason="Correspondance directe et complète.",
        )

        entry = self._entry(selected, result)

        assert entry["is_high_risk_for_deletion_review"] is False
        assert aggregator_module.build_risk_list([entry]) == []

    def test_distribution_et_totaux(self):
        blocks = [
            _make_block("FRB0001", semantic_review_status="NEEDED", audio_id="AUDIO001"),
            _make_block("FRB0002", semantic_review_status="NEEDED", audio_id="AUDIO002"),
        ]
        selected = [
            SelectedBlock(block_id=b["block_id"], selection_group="G", selection_reason="r", raw_block=b)
            for b in blocks
        ]
        entries = [
            self._entry(selected[0], _classification("FRB0001", classification="TRANSLATION_BEFORE", matched_direction="BEFORE")),
            self._entry(selected[1], _classification("FRB0002", classification="NOT_TRANSLATION")),
        ]

        totals = aggregator_module.build_classification_totals(entries)
        assert totals["TRANSLATION_BEFORE"] == 1
        assert totals["NOT_TRANSLATION"] == 1

        by_audio = aggregator_module.build_distribution(entries, "audio_id")
        assert by_audio["AUDIO001"]["TRANSLATION_BEFORE"] == 1
        assert by_audio["AUDIO002"]["NOT_TRANSLATION"] == 1

    def test_previously_resolved_et_no_english_context_sections(self):
        blocks = [
            _make_block("FRB0001", semantic_review_status="ALREADY_RESOLVED"),
            _make_block(
                "FRB0002", semantic_review_status="NO_ENGLISH_CONTEXT",
                candidate_direction="NONE", english_before=None, english_after=None,
            ),
        ]

        resolved = aggregator_module.build_previously_resolved_section(blocks)
        no_context = aggregator_module.build_no_english_context_section(blocks)

        assert resolved == [{"block_id": "FRB0001", "existing_status": "ALREADY_RESOLVED"}]
        assert no_context == [{"block_id": "FRB0002", "status": "NO_ENGLISH_CONTEXT"}]

    def test_divergence_report_highlights(self):
        blocks = [_make_block("FRB0001", semantic_review_status="NEEDED", phase_3a1_status="ALL_KEEP")]
        selected = SelectedBlock(
            block_id="FRB0001", selection_group="G", selection_reason="r", raw_block=blocks[0]
        )
        entry = self._entry(
            selected, _classification("FRB0001", classification="TRANSLATION_BEFORE", matched_direction="BEFORE")
        )

        report = aggregator_module.build_divergence_report([entry])

        assert report["highlights"]["ALL_KEEP_to_TRANSLATION"] == 1

    def test_aggregate_usage_and_cost_cache_et_appel_reel(self):
        from app.semantic_batch.runner import BatchOutcome

        outcomes = [
            BatchOutcome(
                batch_id="BATCH001", block_ids=["FRB0001"], source="REAL_CALL",
                results=[], usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
                cost={"total_cost": 0.01, "currency": "USD"}, latency_ms=500,
                finish_reason="end_turn", request_id="req1",
            ),
            BatchOutcome(
                batch_id="BATCH002", block_ids=["FRB0002"], source="CACHE_HIT",
                results=[], usage={"input_tokens": 80, "output_tokens": 40, "total_tokens": 120},
                cost={"total_cost": 0.008, "currency": "USD"}, latency_ms=300,
                finish_reason="end_turn", request_id="req2",
            ),
        ]

        usage_summary, cost_summary = aggregator_module.aggregate_usage_and_cost(outcomes)

        assert usage_summary["total_real_calls"] == 1
        assert usage_summary["total_cache_hits"] == 1
        assert usage_summary["total_input_tokens"] == 180
        assert usage_summary["total_output_tokens"] == 90
        assert cost_summary["cost_status"] == "known"
        assert cost_summary["total_cost"] == pytest.approx(0.018)

    def test_aggregate_usage_and_cost_statut_partiel(self):
        from app.semantic_batch.runner import BatchOutcome

        outcomes = [
            BatchOutcome(
                batch_id="BATCH001", block_ids=["FRB0001"], source="REAL_CALL",
                results=[], usage={}, cost={"total_cost": 0.01, "currency": "USD"},
                latency_ms=0, finish_reason=None, request_id=None,
            ),
            BatchOutcome(
                batch_id="BATCH002", block_ids=["FRB0002"], source="REAL_CALL",
                results=[], usage={}, cost={"total_cost": None}, latency_ms=0,
                finish_reason=None, request_id=None,
            ),
        ]

        _, cost_summary = aggregator_module.aggregate_usage_and_cost(outcomes)

        assert cost_summary["cost_status"] == "partial"


# ---------------------------------------------------------------------------
# TestIntegrity — 4 artefacts protégés (§9, §41)
# ---------------------------------------------------------------------------

class TestIntegrity:
    def test_source_paths_contient_les_quatre_cles(self, tmp_path):
        paths = integrity_module.source_paths("proj", sortie_dir=tmp_path)

        assert set(paths.keys()) == {
            "transcript_data",
            "language_cleanup",
            "language_blocks",
            "semantic_translation_canary",
        }

    def test_ensure_unchanged_detecte_le_canary_modifie(self):
        before = integrity_module.IntegritySnapshot(
            hashes={
                "transcript_data": "a",
                "language_cleanup": "b",
                "language_blocks": "c",
                "semantic_translation_canary": "d",
            }
        )
        after = integrity_module.IntegritySnapshot(
            hashes={**before.hashes, "semantic_translation_canary": "CHANGED"}
        )

        with pytest.raises(Exception):
            integrity_module.ensure_unchanged(before, after)

    def test_ensure_unchanged_ok_si_identique(self):
        snapshot = integrity_module.IntegritySnapshot(
            hashes={
                "transcript_data": "a",
                "language_cleanup": "b",
                "language_blocks": "c",
                "semantic_translation_canary": "d",
            }
        )
        integrity_module.ensure_unchanged(snapshot, snapshot)  # ne lève pas


# ---------------------------------------------------------------------------
# TestRunnerIntegration — FakeAIEngine bout en bout (§18-23, §37-38)
# ---------------------------------------------------------------------------

class TestRunnerIntegration:
    def _build_project(self, tmp_path):
        from app.tests.semantic_batch_fixtures import PROJECT, build_full_fixture_project

        sortie_dir = tmp_path / "sortie"
        build_full_fixture_project(sortie_dir)
        return PROJECT, sortie_dir

    def _snapshot_bytes(self, project_name, sortie_dir):
        paths = integrity_module.source_paths(project_name, sortie_dir=sortie_dir)
        return {key: path.read_bytes() for key, path in paths.items()}

    def _reply_for_batch(self, block_ids: list[str], **overrides) -> FakeReply:
        results = [
            {
                "block_id": bid,
                "classification": "UNCERTAIN",
                "matched_direction": "NONE",
                "confidence": 0.4,
                "reason": "Réponse simulée neutre pour le test.",
            }
            for bid in block_ids
        ]
        payload = {"schema_version": "1.0", "results": results}
        kwargs = dict(text=json.dumps(payload, ensure_ascii=False))
        kwargs.update(overrides)
        return FakeReply(**kwargs)

    def _plan_for_project(self, project_name, sortie_dir, *, max_batch_size):
        sources = load_and_validate_sources(project_name, sortie_dir=sortie_dir)
        selected = selection_module.select_needed_blocks(sources["blocks"])
        plan = planner_module.build_batch_plan(selected, max_batch_size=max_batch_size)
        return sources, selected, plan

    def test_execution_complete_multi_lots_reussit(self, tmp_path, no_ai_network):
        project_name, sortie_dir = self._build_project(tmp_path)
        _, _, plan = self._plan_for_project(project_name, sortie_dir, max_batch_size=5)
        assert len(plan) > 1  # exercer réellement la boucle multi-lots

        engine = FakeAIEngine(
            script=[self._reply_for_batch(item.block_ids) for item in plan]
        )

        result = run_semantic_batch_classification(
            project_name,
            engine=engine,
            sortie_dir=sortie_dir,
            expected_provider="fake",
            expected_model=engine.resolve_model(),
            max_batch_size=5,
        )

        assert result.success is True
        assert result.real_call_count == len(plan)
        assert result.cache_hit_count == 0
        assert engine.call_count == len(plan)
        assert result.artifact_path is not None
        assert result.artifact_path.exists()

        published = json.loads(result.artifact_path.read_text(encoding="utf-8"))
        expected_needed = sum(item.block_count for item in plan)
        assert published["stats"]["total_classified"] == expected_needed
        assert len(published["results"]) == expected_needed

    def test_aucune_source_protegee_nest_modifiee(self, tmp_path, no_ai_network):
        project_name, sortie_dir = self._build_project(tmp_path)
        before = self._snapshot_bytes(project_name, sortie_dir)

        _, _, plan = self._plan_for_project(project_name, sortie_dir, max_batch_size=5)
        engine = FakeAIEngine(
            script=[self._reply_for_batch(item.block_ids) for item in plan]
        )

        result = run_semantic_batch_classification(
            project_name, engine=engine, sortie_dir=sortie_dir,
            expected_provider="fake", expected_model=engine.resolve_model(),
            max_batch_size=5,
        )

        assert result.success is True

        after = self._snapshot_bytes(project_name, sortie_dir)
        assert before.keys() == after.keys()
        for key in before:
            assert before[key] == after[key], f"{key} a changé de contenu (octets)"

    def test_reprise_apres_run_complet_est_tout_en_cache(self, tmp_path, no_ai_network):
        """§18 : une seconde exécution ne doit produire AUCUN appel réel."""
        project_name, sortie_dir = self._build_project(tmp_path)
        _, _, plan = self._plan_for_project(project_name, sortie_dir, max_batch_size=5)

        first_engine = FakeAIEngine(
            script=[self._reply_for_batch(item.block_ids) for item in plan]
        )
        first = run_semantic_batch_classification(
            project_name, engine=first_engine, sortie_dir=sortie_dir,
            expected_provider="fake", expected_model=first_engine.resolve_model(),
            max_batch_size=5,
        )
        assert first.success is True
        assert first.real_call_count == len(plan)

        # Un moteur qui échouerait au moindre appel : la reprise ne doit
        # JAMAIS le solliciter puisque tout est déjà en cache.
        poisoned_engine = FakeAIEngine(script=[RuntimeError("ne doit jamais être appelé")])

        second = run_semantic_batch_classification(
            project_name, engine=poisoned_engine, sortie_dir=sortie_dir,
            expected_provider="fake", expected_model=poisoned_engine.resolve_model(),
            max_batch_size=5,
        )

        assert second.success is True
        assert second.real_call_count == 0
        assert second.cache_hit_count == len(plan)
        assert poisoned_engine.call_count == 0

    def test_reponse_invalide_stop_sans_reparation_ni_second_appel(
        self, tmp_path, no_ai_network
    ):
        """§21, §23 : max_attempts=1, aucune réparation — un FAIL reste un FAIL."""
        project_name, sortie_dir = self._build_project(tmp_path)
        _, _, plan = self._plan_for_project(project_name, sortie_dir, max_batch_size=5)

        # Le premier lot répond correctement, le second omet un block_id.
        first_batch = plan[0]
        second_batch = plan[1]
        bad_results = [
            {
                "block_id": bid,
                "classification": "UNCERTAIN",
                "matched_direction": "NONE",
                "confidence": 0.4,
                "reason": "Réponse volontairement incomplète.",
            }
            for bid in second_batch.block_ids[:-1]
        ]
        script = [
            self._reply_for_batch(first_batch.block_ids),
            FakeReply(text=json.dumps({"schema_version": "1.0", "results": bad_results})),
        ]
        engine = FakeAIEngine(script=script)

        result = run_semantic_batch_classification(
            project_name, engine=engine, sortie_dir=sortie_dir,
            expected_provider="fake", expected_model=engine.resolve_model(),
            max_batch_size=5,
        )

        assert result.success is False
        assert result.stopped_at_batch == second_batch.batch_id
        assert engine.call_count == 2  # jamais un troisième appel de réparation
        assert "CanaryResponseValidationError" in result.error["error_type"]

        # Le premier lot, réussi, est bien resté sur disque (repris tel quel).
        first_batch_path = writer_module.batch_path(
            project_name, first_batch.batch_id, sortie_dir=sortie_dir
        )
        assert first_batch_path.exists()

        # Le second lot, en échec, n'a RIEN écrit : une prochaine exécution
        # le retentera, elle ne le considérera jamais comme résolu.
        second_batch_path = writer_module.batch_path(
            project_name, second_batch.batch_id, sortie_dir=sortie_dir
        )
        assert not second_batch_path.exists()

    def test_cache_incompatible_stop_avant_tout_appel_reseau(self, tmp_path, no_ai_network):
        """§19 : un lot en cache incompatible arrête tout AVANT le premier appel."""
        project_name, sortie_dir = self._build_project(tmp_path)
        _, _, plan = self._plan_for_project(project_name, sortie_dir, max_batch_size=5)
        first_batch = plan[0]

        # Écrit un faux checkpoint incompatible (prompt_version différente).
        poisoned_path = writer_module.batch_path(
            project_name, first_batch.batch_id, sortie_dir=sortie_dir
        )
        writer_module.write_batch_atomic(
            poisoned_path,
            {
                "batch_id": first_batch.batch_id,
                "prompt_version": "0.0-incompatible",
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "source_hashes": {"language_blocks": "wrong"},
                "block_ids": first_batch.block_ids,
                "signature": "wrong",
                "results": [],
            },
        )

        engine = FakeAIEngine(script=[RuntimeError("ne doit jamais être appelé")])

        result = run_semantic_batch_classification(
            project_name, engine=engine, sortie_dir=sortie_dir,
            expected_provider="fake", expected_model=engine.resolve_model(),
            max_batch_size=5,
        )

        assert result.success is False
        assert result.stopped_at_batch == first_batch.batch_id
        assert "CacheSignatureMismatchError" in result.error["error_type"]
        assert engine.call_count == 0  # STOP avant tout appel réseau

    def test_semantic_translation_canary_manquant_stop_avant_reseau(self, tmp_path):
        from app.tests.semantic_canary_fixtures import build_fixture_project, PROJECT

        sortie_dir = tmp_path / "sortie"
        build_fixture_project(sortie_dir)  # sans le stub canary (§9)

        with pytest.raises(SourceIntegrityError):
            load_and_validate_sources(PROJECT, sortie_dir=sortie_dir)

    def test_exclusion_already_resolved_et_no_english_context_de_la_selection(
        self, tmp_path, no_ai_network
    ):
        project_name, sortie_dir = self._build_project(tmp_path)
        sources = load_and_validate_sources(project_name, sortie_dir=sortie_dir)
        selected = selection_module.select_needed_blocks(sources["blocks"])

        selected_ids = {b.block_id for b in selected}
        already_resolved_ids = {
            b["block_id"]
            for b in sources["blocks"]
            if b.get("semantic_review_status") == "ALREADY_RESOLVED"
        }

        assert already_resolved_ids  # le fixture en contient bien (§13.A)
        assert selected_ids.isdisjoint(already_resolved_ids)
        assert all(b.semantic_review_status == "NEEDED" for b in selected)
