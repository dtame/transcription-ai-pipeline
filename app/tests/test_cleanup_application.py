"""
Tests de la Phase 3A.2B — application déterministe de POLICY_B_PLUS_V1.

Aucun test de ce fichier ne touche au réseau. Le paquet n'importe aucun
module capable d'émettre une requête ; le test d'intégration utilise en
plus `no_ai_network`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.cleanup_application.constants import (
    DECISION_AUTO_REMOVE,
    DECISION_HUMAN_REVIEW,
    DECISION_KEEP,
    POLICY_B_PLUS,
    REASON_AUTO_REMOVE,
    REASON_BRIDGE,
    REASON_EXTRA_CONTENT,
    REASON_HIGH_RISK,
    REASON_LANGUAGE_NOT_FR,
    REASON_LEGACY,
    REASON_LOW_CONFIDENCE,
    REASON_MULTI_SRC,
    REASON_NO_ENGLISH,
    REASON_NOT_TRANSLATION,
    REASON_TEXT_MISMATCH,
    REASON_TRANSLATION_AFTER,
    REASON_UNCERTAIN,
    REASON_WORD_COUNT,
)
from app.cleanup_application.errors import ApplicationValidationError, PreflightError
from app.cleanup_application.models import ApplicationPlan, PlannedBlock, RemovalSnapshot
from app.cleanup_application.planner import plan_application
from app.cleanup_application.restore import assert_reversible, restore_segments
from app.cleanup_application.transformer import render_clean_text, transform_document
from app.cleanup_application.validator import (
    validate_clean_transcript,
    validate_original_still_rejects_gaps,
    validate_removal_set,
)
from app.cleanup_application.writer import dumps_canonical, publish_outputs, sha256_of_text
from app.cleanup_policy.constants import ORIGIN_NO_ENGLISH_CONTEXT, ORIGIN_PHASE_3A1_RESOLVED
from app.cleanup_policy.risk import compute_risk_flags
from app.tests.cleanup_application_fixtures import (
    PROJECT,
    decide_for,
    make_context,
    make_document,
    make_record,
)
from app.transcript_models import TranscriptSegment
from app.transcript_validator import validate_transcript_document


def _auto_record(**kwargs):
    defaults = dict(
        block_id="FRB0001",
        fr_source_refs=("SRC000002",),
        word_count=4,
        confidence=0.96,
        classification="TRANSLATION_BEFORE",
        text="bonjour le monde ici",
        semantic_origin="SEMANTIC_BATCH",
        bridge_source_refs=(),
        is_high_risk_existing=False,
        reason="Correspondance directe et complete.",
    )
    defaults.update(kwargs)
    record = make_record(**defaults)
    # word_count du record doit coller au texte pour les checks SRC.
    if "word_count" not in kwargs:
        object.__setattr__(record, "word_count", len(record.text.split()))
    return record


def _plan_for(document, records, languages=None, extras=None):
    language_by_src = {}
    for rec in records:
        for ref in rec.fr_source_refs:
            language_by_src[ref] = (languages or {}).get(ref, "FR")
        for ref in rec.bridge_source_refs:
            language_by_src.setdefault(ref, "UNKNOWN")
    for seg in document.segments:
        language_by_src.setdefault(seg.id, "EN")
    if languages:
        language_by_src.update(languages)
    extras = extras or {
        rec.block_id: {
            "english_before_source_refs": (),
            "english_after_source_refs": (),
            "english_after_text": rec.english_after_text,
        }
        for rec in records
    }
    return plan_application(
        project_name=document.project_name,
        records=records,
        document=document,
        language_by_src=language_by_src,
        block_extras=extras,
    )


# ---------------------------------------------------------------------------
# 1-12 — Règles POLICY_B_PLUS_V1
# ---------------------------------------------------------------------------

class TestPolicyBPlusRules:
    def test_translation_before_high_confidence_single_src_is_auto_remove(self):
        record = _auto_record(confidence=0.90)
        decision = decide_for(record)
        assert decision.decision == DECISION_AUTO_REMOVE
        assert decision.reasons == (REASON_AUTO_REMOVE,)
        assert decision.candidate_removed_source_refs == ("SRC000002",)

    def test_confidence_089_is_human_review(self):
        record = _auto_record(confidence=0.89)
        decision = decide_for(record)
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_LOW_CONFIDENCE in decision.reasons

    def test_translation_after_is_human_review_even_at_1(self):
        record = _auto_record(classification="TRANSLATION_AFTER", confidence=1.0)
        decision = decide_for(record)
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_TRANSLATION_AFTER in decision.reasons
        assert decision.candidate_removed_source_refs == ()

    def test_multi_src_is_human_review(self):
        record = _auto_record(fr_source_refs=("SRC000002", "SRC000003"), word_count=8)
        decision = decide_for(record)
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_MULTI_SRC in decision.reasons

    def test_high_risk_is_human_review(self):
        record = _auto_record(is_high_risk_existing=True, confidence=0.99)
        decision = decide_for(record)
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_HIGH_RISK in decision.reasons

    def test_bridge_is_human_review(self):
        record = _auto_record(bridge_source_refs=("SRC000099",))
        decision = decide_for(record)
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_BRIDGE in decision.reasons

    def test_extra_content_is_human_review(self):
        record = _auto_record(reason="Le FR ajoute un commentaire absent de l'anglais.")
        decision = decide_for(record)
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_EXTRA_CONTENT in decision.reasons

    def test_more_than_30_words_is_human_review(self):
        text = " ".join(f"mot{i}" for i in range(31))
        record = _auto_record(text=text, word_count=31)
        decision = decide_for(record)
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_WORD_COUNT in decision.reasons

    def test_not_translation_is_keep(self):
        record = _auto_record(classification="NOT_TRANSLATION")
        decision = decide_for(record)
        assert decision.decision == DECISION_KEEP
        assert decision.reasons == (REASON_NOT_TRANSLATION,)

    def test_uncertain_is_keep(self):
        record = _auto_record(classification="UNCERTAIN")
        decision = decide_for(record)
        assert decision.decision == DECISION_KEEP
        assert decision.reasons == (REASON_UNCERTAIN,)

    def test_no_english_context_is_keep(self):
        record = _auto_record(
            semantic_origin=ORIGIN_NO_ENGLISH_CONTEXT,
            classification=None,
            confidence=None,
            reason=None,
        )
        decision = decide_for(record)
        assert decision.decision == DECISION_KEEP
        assert decision.reasons == (REASON_NO_ENGLISH,)

    def test_legacy_resolved_is_human_review(self):
        record = _auto_record(
            semantic_origin=ORIGIN_PHASE_3A1_RESOLVED,
            classification=None,
            confidence=None,
            phase_3a1_status="ALL_REMOVE",
        )
        decision = decide_for(record)
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert decision.reasons == (REASON_LEGACY,)

    def test_all_applicable_reasons_are_kept(self):
        record = _auto_record(
            confidence=0.5,
            fr_source_refs=("SRC000002", "SRC000003"),
            word_count=8,
        )
        decision = decide_for(record)
        assert REASON_LOW_CONFIDENCE in decision.reasons
        assert REASON_MULTI_SRC in decision.reasons


# ---------------------------------------------------------------------------
# 13-14 — Une SRC par AUTO_REMOVE, aucun bridge retiré
# ---------------------------------------------------------------------------

class TestRemovalUnit:
    def test_exactly_one_src_removed_per_auto_block(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        # SRC000002 text in document is "bonjour le monde"
        plan = _plan_for(document, [record])
        auto = plan.blocks_with(DECISION_AUTO_REMOVE)
        assert len(auto) == 1
        assert auto[0].decision.candidate_removed_source_refs == ("SRC000002",)
        assert plan.removal_set == frozenset({"SRC000002"})

    def test_bridge_never_removed(self):
        document = make_document(
            segments=[
                TranscriptSegment("SRC000001", "AUDIO001", 1, 0.0, 1.0, "en"),
                TranscriptSegment("SRC000002", "AUDIO001", 1, 1.0, 2.0, "bonjour le monde"),
                TranscriptSegment("SRC000003", "AUDIO001", 1, 2.0, 2.4, "bridge token"),
            ]
        )
        record = _auto_record(
            text="bonjour le monde",
            bridge_source_refs=("SRC000003",),
        )
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        assert "SRC000003" not in plan.removal_set
        assert plan.removal_set == frozenset()


# ---------------------------------------------------------------------------
# 15-21 — Stabilité IDs / texte / timestamps / audio / ordre
# ---------------------------------------------------------------------------

class TestSurvivorIntegrity:
    def _transformed(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        return document, plan, clean

    def test_surviving_src_ids_unchanged(self):
        original, plan, clean = self._transformed()
        assert [s.id for s in clean.segments] == ["SRC000001", "SRC000003"]

    def test_gaps_allowed_on_clean(self):
        original, plan, clean = self._transformed()
        assert validate_transcript_document(clean, allow_source_id_gaps=True) == []

    def test_original_validator_still_rejects_gaps(self):
        original, plan, clean = self._transformed()
        errors = validate_original_still_rejects_gaps(clean)
        assert any("identifiant SRC non continu" in err for err in errors)
        assert validate_transcript_document(original) == []

    def test_original_src_order_preserved(self):
        original, plan, clean = self._transformed()
        original_ids = [s.id for s in original.segments]
        clean_ids = [s.id for s in clean.segments]
        assert clean_ids == [src for src in original_ids if src not in plan.removal_set]

    def test_survivor_text_exact(self):
        original, plan, clean = self._transformed()
        by_id = {s.id: s for s in original.segments}
        for segment in clean.segments:
            assert segment.text == by_id[segment.id].text

    def test_timestamps_exact(self):
        original, plan, clean = self._transformed()
        by_id = {s.id: s for s in original.segments}
        for segment in clean.segments:
            assert (segment.start, segment.end) == (by_id[segment.id].start, by_id[segment.id].end)

    def test_audio_ids_exact(self):
        original, plan, clean = self._transformed()
        assert [s.to_dict() for s in clean.sources] == [s.to_dict() for s in original.sources]
        by_id = {s.id: s for s in original.segments}
        for segment in clean.segments:
            assert segment.source_id == by_id[segment.id].source_id


# ---------------------------------------------------------------------------
# 22-28 — Jeux KEEP / HUMAN_REVIEW / flags retenus
# ---------------------------------------------------------------------------

class TestRetention:
    def test_removal_set_exact(self):
        document = make_document()
        auto = _auto_record(text="bonjour le monde")
        object.__setattr__(auto, "word_count", 3)
        keep = _auto_record(
            block_id="FRB0002",
            classification="NOT_TRANSLATION",
            fr_source_refs=("SRC000001",),
            text="english one",
        )
        plan = _plan_for(document, [auto, keep])
        validate_removal_set(plan, document, {s.id: "FR" if s.id == "SRC000002" else "EN" for s in document.segments})
        assert plan.removal_set == frozenset({"SRC000002"})

    def test_human_review_retained(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde", confidence=0.5)
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        assert "SRC000002" in {s.id for s in clean.segments}

    def test_keep_retained(self):
        document = make_document()
        record = _auto_record(
            classification="NOT_TRANSLATION",
            text="bonjour le monde",
        )
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        assert len(clean.segments) == len(document.segments)

    def test_translation_after_retained(self):
        document = make_document()
        record = _auto_record(
            classification="TRANSLATION_AFTER",
            text="bonjour le monde",
            confidence=1.0,
        )
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        assert "SRC000002" in {s.id for s in clean.segments}

    def test_multi_src_retained(self):
        document = make_document()
        record = _auto_record(
            fr_source_refs=("SRC000001", "SRC000002"),
            text="english one bonjour le monde",
        )
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        assert {s.id for s in clean.segments} == {s.id for s in document.segments}

    def test_high_risk_retained(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde", is_high_risk_existing=True, confidence=0.99)
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        assert "SRC000002" not in plan.removal_set

    def test_extra_content_retained(self):
        document = make_document()
        record = _auto_record(
            text="bonjour le monde",
            reason="Le bloc ajoute une idee personnelle.",
            confidence=0.99,
        )
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        assert "SRC000002" not in plan.removal_set


# ---------------------------------------------------------------------------
# 29-31 — Stats, durée, TXT/JSON
# ---------------------------------------------------------------------------

class TestCleanStatsAndTxt:
    def test_clean_stats_exact(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        assert clean.stats.segment_count == 2
        assert clean.stats.word_count == len("english one".split()) + len("english two".split())
        assert clean.stats.source_count == 2

    def test_original_duration_preserved(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        assert clean.stats.duration_seconds == document.stats.duration_seconds

    def test_clean_txt_matches_clean_json(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        txt = render_clean_text(clean)
        from app.transcript_models import TranscriptDocument
        reloaded_like = TranscriptDocument(
            project_name=clean.project_name,
            sources=clean.sources,
            segments=clean.segments,
            stats=clean.stats,
            primary_language=clean.primary_language,
            detected_languages=clean.detected_languages,
            transcript_id=clean.transcript_id,
            schema_version=clean.schema_version,
        )
        assert render_clean_text(reloaded_like) == txt
        assert "bonjour le monde" not in txt
        assert "english one" in txt


# ---------------------------------------------------------------------------
# 32-33 — Réversibilité / original_index 0-based
# ---------------------------------------------------------------------------

class TestReversibility:
    def test_restore_equals_original(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        assert_reversible(document, clean, plan.removal_snapshots)
        restored = restore_segments(document, clean, plan.removal_snapshots)
        assert [s.id for s in restored] == [s.id for s in document.segments]
        assert [s.text for s in restored] == [s.text for s in document.segments]

    def test_original_index_is_zero_based(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        assert plan.removal_snapshots[0].original_index == 1
        assert document.segments[1].id == "SRC000002"


# ---------------------------------------------------------------------------
# 34-36 — Déterminisme
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic_clean_json_txt_and_audit_payload(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan_1 = _plan_for(document, [record])
        plan_2 = _plan_for(document, [record])
        clean_1 = transform_document(document, plan_1)
        clean_2 = transform_document(document, plan_2)
        json_1 = dumps_canonical(clean_1.to_dict())
        json_2 = dumps_canonical(clean_2.to_dict())
        txt_1 = render_clean_text(clean_1)
        txt_2 = render_clean_text(clean_2)
        assert json_1 == json_2
        assert txt_1 == txt_2
        assert sha256_of_text(json_1) == sha256_of_text(json_2)
        snap_1 = [s.to_dict() for s in plan_1.removal_snapshots]
        snap_2 = [s.to_dict() for s in plan_2.removal_snapshots]
        assert snap_1 == snap_2


# ---------------------------------------------------------------------------
# 37 — Échec d'écriture atomique
# ---------------------------------------------------------------------------

class TestAtomicWriter:
    def test_partial_write_failure_leaves_no_final(self, tmp_path, monkeypatch):
        real_write = Path.write_bytes

        def _write(self, data):
            if self.name == "cleanup_application.json.partial":
                real_write(self, data[:10])
                raise OSError("disque plein")
            return real_write(self, data)

        monkeypatch.setattr(Path, "write_bytes", _write)

        with pytest.raises(OSError):
            publish_outputs(
                project_name="demo",
                clean_json_payload={"ok": True},
                clean_txt="hello\n",
                audit_payload={"schema_version": "1.0"},
                sortie_dir=tmp_path,
            )

        clean_dir = tmp_path / "demo" / "transcripts" / "clean"
        audit_dir = tmp_path / "demo" / "audit"
        assert not (clean_dir / "transcript_data.json").exists()
        assert not (clean_dir / "transcript.txt").exists()
        assert not (audit_dir / "cleanup_application.json").exists()
        leftovers = list(clean_dir.glob("*.partial")) + list(audit_dir.glob("*.partial")) if audit_dir.exists() else list(clean_dir.glob("*.partial"))
        assert leftovers == []

    def test_published_sha256_matches_in_memory_canonical_bytes(self, tmp_path):
        from app.semantic_canary.integrity import sha256_of_file

        payload = {"schema_version": "1.0", "ok": True}
        txt = "hello\n"
        audit = {"schema_version": "1.0", "n": 1}
        paths = publish_outputs(
            project_name="demo",
            clean_json_payload=payload,
            clean_txt=txt,
            audit_payload=audit,
            sortie_dir=tmp_path,
        )
        assert sha256_of_file(paths["clean_json"]) == sha256_of_text(dumps_canonical(payload))
        assert sha256_of_file(paths["clean_txt"]) == sha256_of_text(txt)
        assert sha256_of_file(paths["audit"]) == sha256_of_text(dumps_canonical(audit))
        assert b"\r\n" not in paths["clean_json"].read_bytes()
        assert b"\r\n" not in paths["clean_txt"].read_bytes()
        assert b"\r\n" not in paths["audit"].read_bytes()
        leftovers = list(paths["clean_json"].parent.glob("*.partial")) + list(
            paths["audit"].parent.glob("*.partial")
        )
        assert leftovers == []


# ---------------------------------------------------------------------------
# 38-39 — Hashes sources / zéro réseau
# ---------------------------------------------------------------------------

class TestIsolation:
    def test_package_does_not_import_ai_or_network(self):
        root = Path(__file__).resolve().parents[1] / "cleanup_application"
        forbidden = (
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
                    if any(module == p or module.startswith(p + ".") for p in forbidden):
                        violations.append(f"{path.name}: {module}")
        assert violations == []

    def test_text_mismatch_blocks_auto_remove(self):
        record = _auto_record(text="bonjour le monde")
        decision = decide_for(record, src_text="autre texte")
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_TEXT_MISMATCH in decision.reasons

    def test_non_fr_language_blocks_auto_remove(self):
        record = _auto_record(text="bonjour le monde")
        decision = decide_for(record, language="EN")
        assert decision.decision == DECISION_HUMAN_REVIEW
        assert REASON_LANGUAGE_NOT_FR in decision.reasons


# ---------------------------------------------------------------------------
# 40-45 — Comparaisons, pas de renumérotage, pas d'anglais retiré
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    def test_no_renumbering_after_removal(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        clean = transform_document(document, plan)
        assert "SRC000002" not in {s.id for s in clean.segments}
        assert clean.segments[1].id == "SRC000003"

    def test_no_accidental_english_removal(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        languages = {"SRC000001": "EN", "SRC000002": "FR", "SRC000003": "EN"}
        plan = _plan_for(document, [record], languages=languages)
        clean = transform_document(document, plan)
        remaining = {s.id for s in clean.segments}
        assert "SRC000001" in remaining and "SRC000003" in remaining
        assert plan.removal_set == frozenset({"SRC000002"})

    def test_unknown_mixed_bridge_not_removed(self):
        document = make_document(
            segments=[
                TranscriptSegment("SRC000001", "AUDIO001", 1, 0.0, 1.0, "en"),
                TranscriptSegment("SRC000002", "AUDIO001", 1, 1.0, 2.0, "bonjour le monde"),
                TranscriptSegment("SRC000003", "AUDIO001", 1, 2.0, 2.5, "amen"),
            ]
        )
        record = _auto_record(text="bonjour le monde", bridge_source_refs=("SRC000003",))
        object.__setattr__(record, "word_count", 3)
        languages = {"SRC000001": "EN", "SRC000002": "FR", "SRC000003": "UNKNOWN"}
        plan = _plan_for(document, [record], languages=languages)
        assert "SRC000003" not in plan.removal_set
        assert "SRC000002" not in plan.removal_set

    def test_preflight_stops_on_incoherent_auto_remove(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        plan = _plan_for(document, [record])
        bad = ApplicationPlan(
            project_name=plan.project_name,
            blocks=plan.blocks,
            removal_snapshots=plan.removal_snapshots,
            removal_set=plan.removal_set | frozenset({"SRC000001"}),
        )
        with pytest.raises(PreflightError):
            validate_removal_set(bad, document, {"SRC000001": "EN", "SRC000002": "FR", "SRC000003": "EN"})

    def test_b_plus_excludes_high_risk_that_policy_b_would_auto_remove(self):
        from app.cleanup_policy.policies import decide_policy_b

        record = _auto_record(text="bonjour le monde", is_high_risk_existing=True, confidence=0.99)
        object.__setattr__(record, "word_count", 3)
        flags = compute_risk_flags(record)
        policy_b = decide_policy_b(record, flags)
        policy_b_plus = decide_for(record)
        assert policy_b.decision == DECISION_AUTO_REMOVE
        assert policy_b_plus.decision == DECISION_HUMAN_REVIEW
        assert REASON_HIGH_RISK in policy_b_plus.reasons

    def test_validate_clean_transcript_accepts_filtered_view(self):
        document = make_document()
        record = _auto_record(text="bonjour le monde")
        object.__setattr__(record, "word_count", 3)
        languages = {"SRC000001": "EN", "SRC000002": "FR", "SRC000003": "EN"}
        plan = _plan_for(document, [record], languages=languages)
        clean = transform_document(document, plan)
        validate_removal_set(plan, document, languages)
        validate_clean_transcript(document, clean, plan, languages)


# ---------------------------------------------------------------------------
# Corpus / intégration sur le petit projet fixture
# ---------------------------------------------------------------------------

class TestCorpusIntegration:
    def _prepare(self, tmp_path):
        from app.tests.cleanup_application_fixtures import prepare_fixture_project
        from app.language_blocks.writer import manifest_path, read_manifest_payload
        from app.language_cleanup.writer import manifest_path as cleanup_path
        from app.language_cleanup.writer import read_manifest_payload as read_cleanup

        sortie_dir = tmp_path / "sortie"
        built = prepare_fixture_project(sortie_dir)
        blocks = list(read_manifest_payload(manifest_path(PROJECT, sortie_dir=sortie_dir))["blocks"])
        cleanup = read_cleanup(cleanup_path(PROJECT, sortie_dir=sortie_dir))
        language_by_src = {
            str(s["source_ref"]): str(s.get("language") or "")
            for s in (cleanup or {}).get("segments") or []
        }
        overrides = {}
        eligible = None
        after = None
        for block in blocks:
            refs = list(block.get("fr_source_refs") or [])
            if (
                eligible is None
                and block.get("semantic_review_status") == "NEEDED"
                and len(refs) == 1
                and not block.get("bridge_source_refs")
                and int(block.get("word_count") or 0) <= 30
                and language_by_src.get(refs[0]) == "FR"
            ):
                eligible = str(block["block_id"])
                overrides[eligible] = {"classification": "TRANSLATION_BEFORE", "confidence": 0.97}
            if (
                after is None
                and block.get("semantic_review_status") == "NEEDED"
                and str(block["block_id"]) != eligible
                and len(refs) == 1
                and int(block.get("word_count") or 0) <= 30
            ):
                after = str(block["block_id"])
                overrides[after] = {"classification": "TRANSLATION_AFTER", "confidence": 1.0}

        prepare_fixture_project(sortie_dir, overrides=overrides)
        return PROJECT, sortie_dir, built

    def test_original_minus_removed_equals_clean_and_restore(
        self, tmp_path, no_ai_network
    ):
        from app.cleanup_application.integrity import snapshot_sources
        from app.cleanup_application.runner import run_cleanup_application

        project_name, sortie_dir, _ = self._prepare(tmp_path)
        before = snapshot_sources(project_name, sortie_dir=sortie_dir)

        result = run_cleanup_application(
            project_name, apply=True, sortie_dir=sortie_dir
        )

        original_n = len(result.original.segments)
        removed_n = len(result.plan.removal_set)
        clean_n = len(result.clean.segments)
        assert original_n - removed_n == clean_n
        assert_reversible(result.original, result.clean, result.plan.removal_snapshots)

        after = snapshot_sources(project_name, sortie_dir=sortie_dir)
        assert before.hashes == after.hashes

        assert result.paths["clean_json"].exists()
        assert result.paths["clean_txt"].exists()
        assert result.paths["audit"].exists()

        second = run_cleanup_application(
            project_name, apply=True, sortie_dir=sortie_dir
        )
        assert result.paths["clean_json"].read_bytes() == second.paths["clean_json"].read_bytes()
        assert result.paths["clean_txt"].read_bytes() == second.paths["clean_txt"].read_bytes()
        assert result.paths["audit"].read_bytes() == second.paths["audit"].read_bytes()

        audit = json.loads(result.paths["audit"].read_text(encoding="utf-8"))
        assert audit["network"]["anthropic_calls"] == 0
        assert audit["policy"]["policy_id"] == POLICY_B_PLUS
        assert audit["translation_after"]["all_retained"] is True
        assert result.clean.transcript_id == result.original.transcript_id
        assert result.clean.stats.duration_seconds == result.original.stats.duration_seconds

    def test_dry_run_writes_nothing(self, tmp_path, no_ai_network):
        from app.cleanup_application.runner import run_cleanup_application
        from app.cleanup_application.writer import output_paths

        project_name, sortie_dir, _ = self._prepare(tmp_path)
        result = run_cleanup_application(
            project_name, apply=False, sortie_dir=sortie_dir
        )
        assert result.dry_run is True
        assert result.published is False
        paths = output_paths(project_name, sortie_dir=sortie_dir)
        assert not paths["clean_json"].exists()
        assert not paths["audit"].exists()

    def test_cli_default_is_dry_run(self, tmp_path, no_ai_network, monkeypatch):
        from app.cleanup_application import cli as cli_module
        from app.cleanup_application.writer import output_paths

        project_name, sortie_dir, _ = self._prepare(tmp_path)

        def _run(name, apply=False, sortie_dir=None):
            from app.cleanup_application.runner import run_cleanup_application
            return run_cleanup_application(name, apply=apply, sortie_dir=sortie_dir)

        # Inject sortie_dir by wrapping runner used by CLI.
        import app.cleanup_application.cli as cli

        def fake_run(name, apply=False, sortie_dir=None):
            return _run(name, apply=apply, sortie_dir=tmp_path / "sortie")

        monkeypatch.setattr(cli, "run_cleanup_application", fake_run)
        code = cli.main([project_name])
        assert code == 0
        paths = output_paths(project_name, sortie_dir=tmp_path / "sortie")
        assert not paths["audit"].exists()
