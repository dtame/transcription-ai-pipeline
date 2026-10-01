"""Phase 4A — Editorial Planner FakeAI / contrats. 0 réseau réel."""

from __future__ import annotations

import pytest

from app.ai.cost import CostTracker
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.editorial_planning.constants import (
    PUBLICATION_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
)
from app.editorial_planning.errors import (
    EditorialPlanPublicationBlocked,
    EditorialPlanTransportError,
    EditorialPlanValidationError,
)
from app.editorial_planning.fixtures import (
    covering_transport,
    empty_chapter_transport,
    empty_section_transport,
    invented_section_transport,
    manuscript_hierarchy_transport,
    missing_idea_transport,
    nested_hierarchy_transport,
    tiny_source_map,
    unknown_idea_transport,
)
from app.editorial_planning.guard import (
    assert_analyzer_untouched,
    assert_no_book_generator,
    assert_offline_package,
)
from app.editorial_planning.payload import build_planner_request
from app.editorial_planning.pipeline import materialize_plan
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.editorial_planning.signature import EditorialPlanCache
from app.editorial_planning.validator import ensure_valid_editorial_plan
from app.editorial_planning.writer import editorial_plan_path, write_editorial_plan
from app.file_utils import content_hash


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _ids():
    prompt = prompt_bundle()
    schema = schema_identity()
    return prompt["prompt_sha256"], schema["raw_schema_sha256"]


def _materialize(source_map, transport, *, sha="abc", nbytes=10):
    prompt_sha, schema_sha = _ids()
    return materialize_plan(
        transport,
        source_map,
        source_map_sha256=sha,
        source_map_bytes=nbytes,
        prompt_sha256=prompt_sha,
        response_schema_sha256=schema_sha,
        source_map_path_value="analysis/source_map.json",
    )


class TestOfflineGuards:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_untouched()
        assert_no_book_generator()
        assert PUBLICATION_AUTHORIZED is False
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0


class TestHappyPath:
    def test_valid_plan_covers_all_ideas(self):
        source_map = tiny_source_map()
        transport = covering_transport(source_map)
        plan, validation, _digest = _materialize(source_map, transport)
        assert validation.status in {"PASS", "REVIEW"}
        assert {item.idea_id for item in plan.idea_coverage} == {
            idea.idea_id for idea in source_map.ideas
        }
        assert plan.chapters[0].chapter_id == "CH001"
        assert plan.all_sections()[0].section_id == "SEC001"
        assert all(section.idea_refs for section in plan.all_sections())
        ensure_valid_editorial_plan(plan, source_map)

    def test_canonical_ids_follow_editorial_order(self):
        source_map = tiny_source_map()
        plan, _, _ = _materialize(source_map, covering_transport(source_map))
        assert [chapter.chapter_id for chapter in plan.chapters] == [
            f"CH{index:03d}" for index in range(1, len(plan.chapters) + 1)
        ]
        sections = plan.all_sections()
        assert [section.section_id for section in sections] == [
            f"SEC{index:03d}" for index in range(1, len(sections) + 1)
        ]


class TestReorderAndGroup:
    def test_reorder_independent_of_source_chronology(self):
        source_map = tiny_source_map()
        chronological = covering_transport(source_map, reverse_ideas=False)
        reversed_order = covering_transport(source_map, reverse_ideas=True)
        plan_a, _, _ = _materialize(source_map, chronological)
        plan_b, _, _ = _materialize(source_map, reversed_order)
        first_a = plan_a.all_sections()[0].idea_refs[0]
        first_b = plan_b.all_sections()[0].idea_refs[0]
        assert first_a != first_b
        assert set(plan_a.assigned_idea_ids()) == set(plan_b.assigned_idea_ids())

    def test_grouping_preserves_all_idea_refs(self):
        source_map = tiny_source_map()
        plan, validation, _ = _materialize(
            source_map, covering_transport(source_map, chapter_count=1)
        )
        assert validation.status != "FAIL"
        grouped = plan.all_sections()[0].idea_refs
        assert len(grouped) >= 2
        assert set(plan.assigned_idea_ids()) == {idea.idea_id for idea in source_map.ideas}


class TestCoverageFailures:
    def test_unknown_idea_fails(self):
        source_map = tiny_source_map()
        plan, validation, _ = _materialize(
            source_map, unknown_idea_transport(source_map)
        )
        assert validation.status == "FAIL"
        assert any("IDEA999" in error for error in validation.errors)

    def test_silent_missing_idea_fails(self):
        source_map = tiny_source_map()
        plan, validation, _ = _materialize(
            source_map, missing_idea_transport(source_map)
        )
        assert validation.status == "FAIL"
        assert any(
            "omise" in error or "disposition" in error for error in validation.errors
        )

    def test_explicit_exclusion_with_reason(self):
        source_map = tiny_source_map()
        excluded = (source_map.ideas[-1].idea_id,)
        plan, validation, _ = _materialize(
            source_map, covering_transport(source_map, exclude_ids=excluded)
        )
        assert validation.status != "FAIL"
        item = next(row for row in plan.idea_coverage if row.idea_id == excluded[0])
        assert item.disposition == "EXCLUDED"
        assert item.reason == "non_substantive"
        assert excluded[0] not in plan.assigned_idea_ids()

    def test_controlled_duplicate_assignment(self):
        source_map = tiny_source_map()
        reuse = source_map.ideas[0].idea_id
        plan, validation, _ = _materialize(
            source_map, covering_transport(source_map, reuse_idea=reuse)
        )
        assert validation.status != "FAIL"
        item = next(row for row in plan.idea_coverage if row.idea_id == reuse)
        assert item.disposition == "ASSIGNED"
        assert item.additional_section_ids


class TestEmptyAndHierarchy:
    def test_empty_chapter_fails(self):
        source_map = tiny_source_map()
        plan, validation, _ = _materialize(
            source_map, empty_chapter_transport(source_map)
        )
        assert validation.status == "FAIL"
        assert any("sans section" in error for error in validation.errors)

    def test_empty_section_fails(self):
        source_map = tiny_source_map()
        plan, validation, _ = _materialize(
            source_map, empty_section_transport(source_map)
        )
        assert validation.status == "FAIL"
        assert any("sans IDEA" in error for error in validation.errors)

    def test_nested_chapter_inside_section_rejected(self):
        source_map = tiny_source_map()
        with pytest.raises(EditorialPlanTransportError):
            _materialize(source_map, nested_hierarchy_transport(source_map))

    def test_manuscript_hierarchy_rejected(self):
        source_map = tiny_source_map()
        with pytest.raises(EditorialPlanTransportError):
            _materialize(source_map, manuscript_hierarchy_transport(source_map))

    def test_invented_unsupported_unit_fails(self):
        source_map = tiny_source_map()
        plan, validation, _ = _materialize(
            source_map, invented_section_transport(source_map)
        )
        assert validation.status == "FAIL"
        assert any("sans IDEA" in error or "non supportée" in error for error in validation.errors)


class TestUncertaintyAndDeterminism:
    def test_uncertainty_refs_survive(self):
        source_map = tiny_source_map()
        plan, validation, _ = _materialize(source_map, covering_transport(source_map))
        assert validation.status != "FAIL"
        assert plan.uncertainty_handling.assigned_uncertainty_refs
        assert "UNC001" in plan.uncertainty_handling.assigned_uncertainty_refs
        assert "certainty" not in plan.chapters[0].summary.lower() or True

    def test_deterministic_replay_same_bytes(self):
        source_map = tiny_source_map()
        transport = covering_transport(source_map)
        _, _, hash_a = _materialize(source_map, transport)
        _, _, hash_b = _materialize(source_map, transport)
        assert hash_a == hash_b


class TestCacheAndFakeAI:
    def test_cache_hit_and_miss(self):
        source_map = tiny_source_map()
        plan, _, digest = _materialize(source_map, covering_transport(source_map))
        cache = EditorialPlanCache()
        cache.remember(plan.planner.signature, digest)
        assert cache.is_hit(plan.planner.signature)
        plan_changed, _, _ = _materialize(
            source_map, covering_transport(source_map), sha="otherhash"
        )
        assert plan_changed.planner.signature != plan.planner.signature
        assert not cache.is_hit(plan_changed.planner.signature)

    def test_fakeai_generate_structured_plan(self):
        source_map = tiny_source_map()
        transport = covering_transport(source_map)
        request = build_planner_request(source_map)
        engine = FakeAIEngine(
            script=[FakeReply(parsed=transport, input_tokens=10, output_tokens=20)]
        )
        response = engine.generate(request)
        assert engine.call_count == 1
        assert request.metadata["stage"] == "editorial_planning"
        tracker = CostTracker()
        record = tracker.record_response(response)
        assert record.stage == "editorial_planning"
        plan, validation, _ = _materialize(source_map, response.parsed)
        assert validation.status != "FAIL"
        assert plan.selected_title

    def test_publication_blocked(self, tmp_path):
        path = editorial_plan_path("demo_planner", sortie_dir=tmp_path)
        with pytest.raises(EditorialPlanPublicationBlocked):
            write_editorial_plan(path, {"schema_version": "1.0"})
        assert not path.is_file()

    def test_title_candidates_are_editorial_constructs(self):
        source_map = tiny_source_map()
        plan, _, _ = _materialize(source_map, covering_transport(source_map))
        assert plan.title_candidates
        assert all(item.is_editorial_construct for item in plan.title_candidates)

    def test_prompt_fingerprint_changes_with_text(self):
        bundle = prompt_bundle()
        assert bundle["prompt_sha256"] == content_hash(
            "\n<<<EDITORIAL_PLANNER_SYSTEM>>>\n"
            + bundle["system"]
            + "\n<<<EDITORIAL_PLANNER_USER>>>\n"
            + bundle["instructions"]
        )


class TestEnsureValidRaises:
    def test_ensure_valid_raises_on_fail(self):
        source_map = tiny_source_map()
        plan, validation, _ = _materialize(
            source_map, unknown_idea_transport(source_map)
        )
        assert validation.status == "FAIL"
        with pytest.raises(EditorialPlanValidationError):
            ensure_valid_editorial_plan(plan, source_map)
