"""
Tests de la Phase 3A.1.2A — canary sémantique FR <-> EN (app.semantic_canary).

Organisation, alignée sur le §30 du cahier des charges :

    TestSelection            items 1, 2, 4          (sélection déterministe,
                                                       catégories, exclusion
                                                       NO_ENGLISH_CONTEXT)
    TestPayloadSanitization  items 3, 5              (aucune fuite Phase 3A.1,
                                                       refs valides)
    TestPrompt               items 6, 7              (règle de sécurité,
                                                       règle de traduction
                                                       partielle, pas de
                                                       troncature §26)
    TestSchema               items 8, 9              (schéma canonique,
                                                       adaptateur Anthropic)
    TestValidator            items 10-16             (contrat strict de la
                                                       réponse)
    TestRealCallGuard        item 21                 (MAX_REAL_CALLS)
    TestRunnerIntegration    items 17, 18, 19, 20, 22 (FakeAIEngine bout en
                                                       bout, aucune source
                                                       modifiée, retry réel
                                                       désactivé)

Aucun test de ce fichier ne touche au réseau (fixture `no_ai_network` +
`_isolated_ai_credentials` déjà autouse, voir app/tests/conftest.py) : seul
FakeAIEngine simule un appel Anthropic.
"""

from __future__ import annotations

import copy
import json

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import RetryPolicy
from app.semantic_canary import payload as payload_module
from app.semantic_canary import prompt as prompt_module
from app.semantic_canary import runner as runner_module
from app.semantic_canary import schema as schema_module
from app.semantic_canary import selection as selection_module
from app.semantic_canary.errors import (
    CanaryResponseValidationError,
    MaxRealCallsExceededError,
    SelectionError,
)
from app.semantic_canary.guard import RealCallGuard
from app.semantic_canary.models import (
    GROUP_ATYPICAL,
    GROUP_CONTROL_RESOLVED,
    GROUP_KEEP,
    GROUP_REVIEW,
)
from app.semantic_canary.validator import validate_canary_response
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)


# ---------------------------------------------------------------------------
# Fabrique de blocs synthétiques (dicts bruts language_blocks.json)
# ---------------------------------------------------------------------------

def _ctx(refs: list[str], text: str) -> dict:
    """Contexte anglais minimal, valide pour selection.validate_selection."""
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
    phase_3a1_status: str,
    candidate_direction: str,
    structure: str = "EN_FR_EN",
    text: str = "Ceci est un bloc francais de test suffisamment long.",
    word_count: int | None = None,
    english_before: dict | None = None,
    english_after: dict | None = None,
    fr_source_refs: list[str] | None = None,
) -> dict:
    """Dict brut d'un bloc, au format language_blocks.json (LanguageBlock.to_dict)."""
    return {
        "block_id": block_id,
        "audio_id": audio_id,
        "start_seconds": 0.0,
        "end_seconds": 5.0,
        "all_source_refs": fr_source_refs or [f"SRC_{block_id}"],
        "fr_source_refs": fr_source_refs or [f"SRC_{block_id}"],
        "bridge_source_refs": [],
        "text": text,
        "word_count": word_count if word_count is not None else len(text.split()),
        "segment_count": 1,
        "fr_segment_count": 1,
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


def _build_full_pool() -> list[dict]:
    """
    23 blocs synthétiques couvrant précisément les 4 bassins du §13 :

        6 ALREADY_RESOLVED   (pool A, cible 5)
        6 ALL_REVIEW/NEEDED  (pool B, cible 5)
        6 ALL_KEEP/NEEDED    (pool C, cible 5)
        5 atypiques dédiés   (pool D : long, AUDIO003, BEFORE-only,
                               AFTER-only, BOTH riche)
    """
    blocks: list[dict] = []

    for index in range(1, 7):
        blocks.append(
            _make_block(
                f"BLOCK_A{index}",
                semantic_review_status="ALREADY_RESOLVED",
                phase_3a1_status="ALL_REMOVE",
                candidate_direction="BOTH",
                english_before=_ctx([f"EN_A{index}_BEFORE"], "English before context."),
                english_after=_ctx([f"EN_A{index}_AFTER"], "English after context."),
            )
        )

    for index in range(1, 7):
        blocks.append(
            _make_block(
                f"BLOCK_B{index}",
                audio_id="AUDIO002",
                semantic_review_status="NEEDED",
                phase_3a1_status="ALL_REVIEW",
                candidate_direction="BOTH",
                english_before=_ctx([f"EN_B{index}_BEFORE"], "English before context words."),
                english_after=_ctx([f"EN_B{index}_AFTER"], "English after context words."),
            )
        )

    for index in range(1, 7):
        blocks.append(
            _make_block(
                f"BLOCK_C{index}",
                audio_id="AUDIO002",
                semantic_review_status="NEEDED",
                phase_3a1_status="ALL_KEEP",
                candidate_direction="BOTH",
                english_before=_ctx([f"EN_C{index}_BEFORE"], "English before context words."),
                english_after=_ctx([f"EN_C{index}_AFTER"], "English after context words."),
            )
        )

    # D1 — bloc long : word_count largement supérieur à tout le reste.
    # phase_3a1_status="MIXED_DECISIONS" pour les 5 blocs D : ni ALL_REVIEW/
    # HAS_REVIEW (pool B) ni ALL_KEEP (pool C), pour qu'ils ne soient jamais
    # captés par les bassins B/C et restent disponibles pour le groupe D.
    blocks.append(
        _make_block(
            "BLOCK_D1_LONG",
            audio_id="AUDIO002",
            semantic_review_status="NEEDED",
            phase_3a1_status="MIXED_DECISIONS",
            candidate_direction="BOTH",
            text=" ".join(["mot"] * 500),
            word_count=500,
            english_before=_ctx(["EN_D1_BEFORE"], "English before context words."),
            english_after=_ctx(["EN_D1_AFTER"], "English after context words."),
        )
    )

    # D2 — unique bloc AUDIO003.
    blocks.append(
        _make_block(
            "BLOCK_D2_AUDIO003",
            audio_id="AUDIO003",
            semantic_review_status="NEEDED",
            phase_3a1_status="MIXED_DECISIONS",
            candidate_direction="BOTH",
            english_before=_ctx(["EN_D2_BEFORE"], "English before context words."),
            english_after=_ctx(["EN_D2_AFTER"], "English after context words."),
        )
    )

    # D3 — BEFORE-only (aucun contexte après).
    blocks.append(
        _make_block(
            "BLOCK_D3_BEFORE",
            audio_id="AUDIO002",
            semantic_review_status="NEEDED",
            phase_3a1_status="MIXED_DECISIONS",
            candidate_direction="BEFORE",
            english_before=_ctx(["EN_D3_BEFORE"], "English before context words."),
            english_after=None,
        )
    )

    # D4 — AFTER-only (aucun contexte avant).
    blocks.append(
        _make_block(
            "BLOCK_D4_AFTER",
            audio_id="AUDIO002",
            semantic_review_status="NEEDED",
            phase_3a1_status="MIXED_DECISIONS",
            candidate_direction="AFTER",
            english_before=None,
            english_after=_ctx(["EN_D4_AFTER"], "English after context words."),
        )
    )

    # D5 — BOTH riche : word_count FR >= 1.5x la somme des contextes EN adjacents.
    blocks.append(
        _make_block(
            "BLOCK_D5_RICH",
            audio_id="AUDIO002",
            semantic_review_status="NEEDED",
            phase_3a1_status="MIXED_DECISIONS",
            candidate_direction="BOTH",
            text=" ".join(["mot"] * 30),
            word_count=30,
            english_before=_ctx(["EN_D5_BEFORE"], "one two three four five"),
            english_after=_ctx(["EN_D5_AFTER"], "six seven eight nine ten"),
        )
    )

    return blocks


# ---------------------------------------------------------------------------
# 1, 2, 4 — Sélection déterministe (selection.py)
# ---------------------------------------------------------------------------

class TestSelection:
    def test_selection_est_deterministe_et_produit_20_blocs(self):
        blocks = _build_full_pool()

        first = selection_module.select_canary_blocks(blocks)
        second = selection_module.select_canary_blocks(copy.deepcopy(blocks))

        assert len(first) == 20
        assert [b.block_id for b in first] == [b.block_id for b in second]
        assert [b.selection_group for b in first] == [b.selection_group for b in second]

    def test_selection_couvre_les_quatre_groupes_attendus(self):
        blocks = _build_full_pool()
        selected = selection_module.select_canary_blocks(blocks)

        by_group: dict[str, list[str]] = {}
        for block in selected:
            by_group.setdefault(block.selection_group, []).append(block.block_id)

        assert len(by_group[GROUP_CONTROL_RESOLVED]) == 5
        assert len(by_group[GROUP_REVIEW]) == 5
        assert len(by_group[GROUP_KEEP]) == 5
        assert len(by_group[GROUP_ATYPICAL]) == 5

        atypical_ids = set(by_group[GROUP_ATYPICAL])
        assert "BLOCK_D1_LONG" in atypical_ids
        assert "BLOCK_D2_AUDIO003" in atypical_ids
        assert "BLOCK_D3_BEFORE" in atypical_ids
        assert "BLOCK_D4_AFTER" in atypical_ids
        assert "BLOCK_D5_RICH" in atypical_ids

        # Contrôle positif : uniquement des blocs déjà résolus (§13.A).
        for block in selected:
            if block.selection_group == GROUP_CONTROL_RESOLVED:
                assert block.semantic_review_status == "ALREADY_RESOLVED"
            else:
                assert block.semantic_review_status == "NEEDED"

    def test_no_english_context_jamais_selectionne(self):
        blocks = _build_full_pool()
        for index in range(1, 5):
            blocks.append(
                _make_block(
                    f"BLOCK_NOCTX{index}",
                    semantic_review_status="NO_ENGLISH_CONTEXT",
                    phase_3a1_status="ALL_KEEP",
                    candidate_direction="NONE",
                    english_before=None,
                    english_after=None,
                )
            )

        selected = selection_module.select_canary_blocks(blocks)
        selection_module.validate_selection(selected)

        assert len(selected) == 20
        assert all(
            block.semantic_review_status != "NO_ENGLISH_CONTEXT" for block in selected
        )
        assert all(not block_id.startswith("BLOCK_NOCTX") for block_id in (b.block_id for b in selected))

    def test_bassin_insuffisant_leve_selection_error_stop_avant_reseau(self):
        blocks = _build_full_pool()
        # Retire tout le pool A : moins de 5 ALREADY_RESOLVED disponibles.
        blocks = [b for b in blocks if not b["block_id"].startswith("BLOCK_A")]

        with pytest.raises(SelectionError):
            selection_module.select_canary_blocks(blocks)


# ---------------------------------------------------------------------------
# 3, 5 — Payload sanitisé (payload.py)
# ---------------------------------------------------------------------------

class TestPayloadSanitization:
    def test_aucune_decision_phase_3a1_envoyee_au_modele(self):
        blocks = _build_full_pool()
        selected = selection_module.select_canary_blocks(blocks)
        payloads = payload_module.build_canary_payloads(selected)

        for one_payload in payloads:
            payload_module.assert_no_forbidden_leak(one_payload)
            serialized = json.dumps(one_payload)
            for forbidden in payload_module.FORBIDDEN_FIELDS:
                assert forbidden not in serialized

        # Sanity : les blocs sélectionnés portaient bien ces champs en local.
        assert any(b.raw_block.get("phase_3a1_status") for b in selected)

    def test_assert_no_forbidden_leak_detecte_une_fuite(self):
        leaking_payload = {
            "block_id": "FRB0001",
            "french": {"source_refs": ["SRC1"], "text": "texte"},
            "english_before": None,
            "english_after": None,
            "phase_3a1_status": "ALL_REMOVE",
        }

        with pytest.raises(AssertionError):
            payload_module.assert_no_forbidden_leak(leaking_payload)

    def test_payload_refs_valides_et_texte_non_invente(self):
        blocks = _build_full_pool()
        selected = selection_module.select_canary_blocks(blocks)
        payloads = payload_module.build_canary_payloads(selected)

        by_id = {p["block_id"]: p for p in payloads}

        before_only = by_id["BLOCK_D3_BEFORE"]
        assert before_only["english_before"] is not None
        assert before_only["english_before"]["source_refs"] == ["EN_D3_BEFORE"]
        assert before_only["english_after"] is None  # jamais inventé (§16)

        after_only = by_id["BLOCK_D4_AFTER"]
        assert after_only["english_before"] is None
        assert after_only["english_after"] is not None
        assert after_only["english_after"]["source_refs"] == ["EN_D4_AFTER"]

        for one_payload in payloads:
            assert one_payload["french"]["source_refs"]
            assert one_payload["french"]["text"].strip()


# ---------------------------------------------------------------------------
# 6, 7 — Prompt (prompt.py)
# ---------------------------------------------------------------------------

class TestPrompt:
    def test_le_prompt_contient_la_regle_de_securite(self):
        system_prompt = prompt_module.build_system_prompt()

        assert "EN CAS DE DOUTE" in system_prompt
        assert "UNCERTAIN" in system_prompt
        assert "ASYMÉTRIQUE" in system_prompt

    def test_le_prompt_contient_la_regle_de_traduction_partielle(self):
        system_prompt = prompt_module.build_system_prompt()

        assert "TRADUCTION PARTIELLE" in system_prompt
        assert "peut être retiré dans son ensemble" in system_prompt
        assert "NOT_TRANSLATION" in system_prompt

    def test_le_prompt_interdit_edition_traduction_et_connaissances_externes(self):
        system_prompt = prompt_module.build_system_prompt()

        assert "ne pas traduire" in system_prompt
        assert "ne pas corriger" in system_prompt
        assert "connaissances externes" in system_prompt

    def test_user_prompt_ne_tronque_jamais_un_gros_bloc(self):
        long_text = "mot " * 3000
        payloads = [
            {
                "block_id": "FRB_LONG",
                "french": {"source_refs": ["SRC1"], "text": long_text},
                "english_before": None,
                "english_after": {"source_refs": ["SRC2"], "text": "short context"},
            }
        ]

        user_prompt = prompt_module.build_user_prompt(payloads)

        assert long_text.strip() in user_prompt
        assert "FRB_LONG" in user_prompt


# ---------------------------------------------------------------------------
# 8, 9 — Schéma structuré et adaptateur Anthropic (schema.py)
# ---------------------------------------------------------------------------

class TestSchema:
    def test_le_schema_canonique_est_structurellement_valide(self):
        schema = schema_module.build_response_schema()

        assert schema["type"] == "object"
        assert set(schema["required"]) == {"schema_version", "results"}

        item_schema = schema["properties"]["results"]["items"]
        assert set(item_schema["required"]) == {
            "block_id",
            "classification",
            "matched_direction",
            "confidence",
            "reason",
        }
        assert set(item_schema["properties"]["classification"]["enum"]) == {
            "TRANSLATION_BEFORE",
            "TRANSLATION_AFTER",
            "NOT_TRANSLATION",
            "UNCERTAIN",
        }
        assert set(item_schema["properties"]["matched_direction"]["enum"]) == {
            "BEFORE",
            "AFTER",
            "NONE",
        }
        # Anthropic ne supporte pas minimum/maximum (§28, corrigé en 3B.3.2) :
        # jamais exprimés dans le schéma canonique lui-même.
        assert "minimum" not in item_schema["properties"]["confidence"]
        assert "maximum" not in item_schema["properties"]["confidence"]

    def test_l_adaptateur_anthropic_accepte_le_schema_sans_incompatibilite(self):
        schema = schema_module.build_response_schema()
        provider_schema = prepare_anthropic_json_schema(schema)
        findings = audit_unsupported_features(provider_schema)

        assert all(occurrences == [] for occurrences in findings.values()), findings

    def test_schema_fingerprint_est_stable_et_deterministe(self):
        schema = schema_module.build_response_schema()

        first = schema_module.schema_fingerprint(schema)
        second = schema_module.schema_fingerprint(schema_module.build_response_schema())

        assert first == second
        assert isinstance(first, str) and first


# ---------------------------------------------------------------------------
# 10-16 — Validation locale stricte de la réponse (validator.py)
# ---------------------------------------------------------------------------

def _valid_entry(block_id: str, **overrides) -> dict:
    entry = {
        "block_id": block_id,
        "classification": "UNCERTAIN",
        "matched_direction": "NONE",
        "confidence": 0.5,
        "reason": "Justification factuelle courte.",
    }
    entry.update(overrides)
    return entry


class TestValidator:
    EXPECTED = ["FRB0001", "FRB0002", "FRB0003"]

    def test_reponse_valide_est_acceptee(self):
        payload = {
            "schema_version": "1.0",
            "results": [_valid_entry(bid) for bid in self.EXPECTED],
        }

        results = validate_canary_response(payload, self.EXPECTED)

        assert [r.block_id for r in results] == self.EXPECTED

    def test_nombre_de_resultats_incorrect_est_detecte(self):
        payload = {
            "schema_version": "1.0",
            "results": [_valid_entry(bid) for bid in self.EXPECTED[:2]],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("Nombre de résultats" in msg for msg in excinfo.value.errors)

    def test_block_id_duplique_est_detecte(self):
        payload = {
            "schema_version": "1.0",
            "results": [
                _valid_entry("FRB0001"),
                _valid_entry("FRB0001"),
                _valid_entry("FRB0003"),
            ],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("dupliqué" in msg for msg in excinfo.value.errors)

    def test_block_id_manquant_est_detecte(self):
        payload = {
            "schema_version": "1.0",
            "results": [
                _valid_entry("FRB0001"),
                _valid_entry("FRB0002"),
                _valid_entry("FRB0002"),
            ],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("manquant" in msg for msg in excinfo.value.errors)

    def test_block_id_invente_est_detecte(self):
        payload = {
            "schema_version": "1.0",
            "results": [
                _valid_entry("FRB0001"),
                _valid_entry("FRB0002"),
                _valid_entry("FRB9999"),
            ],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("jamais été soumis" in msg for msg in excinfo.value.errors)

    def test_classification_invalide_est_detectee(self):
        payload = {
            "schema_version": "1.0",
            "results": [
                _valid_entry("FRB0001", classification="MAYBE_TRANSLATION"),
                _valid_entry("FRB0002"),
                _valid_entry("FRB0003"),
            ],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("classification invalide" in msg for msg in excinfo.value.errors)

    def test_direction_incoherente_avec_la_classification_est_detectee(self):
        payload = {
            "schema_version": "1.0",
            "results": [
                _valid_entry(
                    "FRB0001",
                    classification="TRANSLATION_BEFORE",
                    matched_direction="AFTER",
                ),
                _valid_entry("FRB0002"),
                _valid_entry("FRB0003"),
            ],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("incohérent" in msg for msg in excinfo.value.errors)

    def test_confidence_hors_bornes_est_detectee(self):
        payload = {
            "schema_version": "1.0",
            "results": [
                _valid_entry("FRB0001", confidence=1.5),
                _valid_entry("FRB0002"),
                _valid_entry("FRB0003"),
            ],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("hors bornes" in msg for msg in excinfo.value.errors)

    def test_reason_vide_est_detectee(self):
        payload = {
            "schema_version": "1.0",
            "results": [
                _valid_entry("FRB0001", reason="   "),
                _valid_entry("FRB0002"),
                _valid_entry("FRB0003"),
            ],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("reason" in msg for msg in excinfo.value.errors)

    def test_cle_editoriale_supplementaire_est_detectee(self):
        entry = _valid_entry("FRB0001")
        entry["editorial_note"] = "ne devrait pas exister"
        payload = {
            "schema_version": "1.0",
            "results": [entry, _valid_entry("FRB0002"), _valid_entry("FRB0003")],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        assert any("non autorisées" in msg for msg in excinfo.value.errors)

    def test_toutes_les_violations_sont_rapportees_ensemble(self):
        """§19 : jamais seulement la première violation trouvée."""
        payload = {
            "schema_version": "1.0",
            "results": [
                _valid_entry("FRB0001", confidence=2.0),
                _valid_entry("FRB9999"),
            ],
        }

        with pytest.raises(CanaryResponseValidationError) as excinfo:
            validate_canary_response(payload, self.EXPECTED)

        errors = excinfo.value.errors
        assert len(errors) >= 3  # nombre incorrect + confidence + block inventé + manquants


# ---------------------------------------------------------------------------
# 21 — Garde-fou « un seul appel réel » (guard.py)
# ---------------------------------------------------------------------------

class TestRealCallGuard:
    def test_un_seul_appel_reel_est_autorise(self, no_ai_network):
        engine = FakeAIEngine(text=json.dumps({"schema_version": "1.0", "results": []}))
        guard = RealCallGuard(max_calls=1)

        from app.ai.contracts import AIRequest

        request = AIRequest(prompt="bloc de test")
        response = guard.guarded_generate(engine, request)

        assert response is not None
        assert engine.call_count == 1
        assert guard.call_count == 1

    def test_un_second_appel_est_refuse_sans_toucher_le_moteur(self, no_ai_network):
        engine = FakeAIEngine(text=json.dumps({"schema_version": "1.0", "results": []}))
        guard = RealCallGuard(max_calls=1)

        from app.ai.contracts import AIRequest

        request = AIRequest(prompt="bloc de test")
        guard.guarded_generate(engine, request)

        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(engine, request)

        # Le moteur n'a JAMAIS été contacté pour la seconde tentative (§32) :
        # le compteur est incrémenté avant l'appel, pas après.
        assert engine.call_count == 1

    def test_le_compteur_est_incremente_avant_l_appel_meme_en_cas_d_echec(
        self, no_ai_network
    ):
        engine = FakeAIEngine(script=[RuntimeError("panne simulée")])
        guard = RealCallGuard(max_calls=1)

        from app.ai.contracts import AIRequest

        request = AIRequest(prompt="bloc de test")

        with pytest.raises(RuntimeError):
            guard.guarded_generate(engine, request)

        assert guard.call_count == 1

        # Une tentative supplémentaire, même après l'échec, reste refusée.
        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(engine, request)


# ---------------------------------------------------------------------------
# 17-20, 22 — Runner bout en bout (FakeAIEngine) + intégrité + retry désactivé
# ---------------------------------------------------------------------------

class TestRunnerIntegration:
    """
    Exercice complet de run_semantic_canary() avec un vrai petit projet sur
    disque (semantic_canary_fixtures.build_fixture_project), un FakeAIEngine
    à la place d'Anthropic, et vérification des trois garanties
    d'intégrité (§9, §37) : aucun octet des trois sources ne doit changer.
    """

    def _build_project(self, tmp_path):
        from app.tests.semantic_canary_fixtures import build_fixture_project, PROJECT

        sortie_dir = tmp_path / "sortie"
        build_fixture_project(sortie_dir)
        return PROJECT, sortie_dir

    def _snapshot_bytes(self, project_name, sortie_dir):
        from app.semantic_canary.integrity import source_paths

        paths = source_paths(project_name, sortie_dir=sortie_dir)
        return {key: path.read_bytes() for key, path in paths.items()}

    def _fake_engine_for_selection(self, selected_blocks):
        results = [
            {
                "block_id": block.block_id,
                "classification": "UNCERTAIN",
                "matched_direction": "NONE",
                "confidence": 0.4,
                "reason": "Réponse simulée neutre pour le test.",
            }
            for block in selected_blocks
        ]
        payload = {"schema_version": "1.0", "results": results}
        return FakeAIEngine(text=json.dumps(payload, ensure_ascii=False))

    def test_fake_ai_engine_fonctionne_de_bout_en_bout(self, tmp_path, no_ai_network):
        project_name, sortie_dir = self._build_project(tmp_path)

        sources = runner_module.load_and_validate_sources(project_name, sortie_dir=sortie_dir)
        selected = selection_module.select_canary_blocks(sources["blocks"])
        engine = self._fake_engine_for_selection(selected)

        result = runner_module.run_semantic_canary(
            project_name,
            engine=engine,
            sortie_dir=sortie_dir,
            expected_provider="fake",
            expected_model=engine.resolve_model(),
        )

        assert result.success is True
        assert result.real_call_count == 1
        assert engine.call_count == 1
        assert result.artifact_path is not None
        assert result.artifact_path.exists()
        assert len(result.cases) == 20

    def test_aucun_transcript_ni_cleanup_ni_blocks_modifie(self, tmp_path, no_ai_network):
        project_name, sortie_dir = self._build_project(tmp_path)

        before = self._snapshot_bytes(project_name, sortie_dir)

        sources = runner_module.load_and_validate_sources(project_name, sortie_dir=sortie_dir)
        selected = selection_module.select_canary_blocks(sources["blocks"])
        engine = self._fake_engine_for_selection(selected)

        result = runner_module.run_semantic_canary(
            project_name,
            engine=engine,
            sortie_dir=sortie_dir,
            expected_provider="fake",
            expected_model=engine.resolve_model(),
        )

        assert result.success is True

        after = self._snapshot_bytes(project_name, sortie_dir)

        assert before.keys() == after.keys()
        for key in before:
            assert before[key] == after[key], f"{key} a changé de contenu (octets)"

    def test_artefact_publie_ne_touche_pas_les_trois_sources(self, tmp_path, no_ai_network):
        from app.semantic_canary.writer import artifact_path

        project_name, sortie_dir = self._build_project(tmp_path)

        sources = runner_module.load_and_validate_sources(project_name, sortie_dir=sortie_dir)
        selected = selection_module.select_canary_blocks(sources["blocks"])
        engine = self._fake_engine_for_selection(selected)

        runner_module.run_semantic_canary(
            project_name,
            engine=engine,
            sortie_dir=sortie_dir,
            expected_provider="fake",
            expected_model=engine.resolve_model(),
        )

        artefact = artifact_path(project_name, sortie_dir=sortie_dir)
        assert artefact.exists()
        assert artefact.name == "semantic_translation_canary.json"

        published = json.loads(artefact.read_text(encoding="utf-8"))
        assert published["schema_version"] == "1.0"
        assert len(published["results"]) == 20
        assert published["selection"]["total_selected"] == 20

    def test_reponse_invalide_ne_declenche_jamais_un_second_appel(
        self, tmp_path, no_ai_network
    ):
        """§19, §34 : un FAIL de validation locale reste un FAIL, pas un retry."""
        project_name, sortie_dir = self._build_project(tmp_path)

        sources = runner_module.load_and_validate_sources(project_name, sortie_dir=sortie_dir)
        selected = selection_module.select_canary_blocks(sources["blocks"])

        # Réponse structurellement valide contre le schéma JSON minimal, mais
        # avec un block_id manquant -> invalide contre le contrat LOCAL (§19).
        bad_results = [
            {
                "block_id": block.block_id,
                "classification": "UNCERTAIN",
                "matched_direction": "NONE",
                "confidence": 0.4,
                "reason": "Réponse volontairement incomplète.",
            }
            for block in selected[:-1]  # un block_id manquant
        ]
        engine = FakeAIEngine(
            text=json.dumps({"schema_version": "1.0", "results": bad_results})
        )

        result = runner_module.run_semantic_canary(
            project_name,
            engine=engine,
            sortie_dir=sortie_dir,
            expected_provider="fake",
            expected_model=engine.resolve_model(),
        )

        assert result.success is False
        assert result.real_call_count == 1
        assert engine.call_count == 1  # jamais un second appel
        assert result.error is not None
        assert "CanaryResponseValidationError" in result.error.error_type

    def test_le_retry_reel_est_desactive_pour_l_appel_construit_par_le_runner(
        self, tmp_path, no_ai_network, monkeypatch
    ):
        """
        §12, §22 : quand le runner construit lui-même le moteur (engine=None),
        il doit demander une politique de rejeu sans rejeu réel
        (max_attempts=1) au registre — jamais la politique par défaut.
        """
        project_name, sortie_dir = self._build_project(tmp_path)

        sources = runner_module.load_and_validate_sources(project_name, sortie_dir=sortie_dir)
        selected = selection_module.select_canary_blocks(sources["blocks"])
        fake = self._fake_engine_for_selection(selected)

        captured: dict = {}

        def _spy_get_ai_engine(provider, **kwargs):
            captured["provider"] = provider
            captured["kwargs"] = kwargs
            return fake

        monkeypatch.setattr(runner_module, "get_ai_engine", _spy_get_ai_engine)

        result = runner_module.run_semantic_canary(
            project_name,
            sortie_dir=sortie_dir,
            expected_provider="fake",
            expected_model=fake.resolve_model(),
        )

        assert captured["provider"] == "anthropic"
        retry_policy = captured["kwargs"]["retry_policy"]
        assert isinstance(retry_policy, RetryPolicy)
        assert retry_policy.max_attempts == 1

        assert result.success is True
        assert fake.call_count == 1
