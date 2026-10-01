"""Phase 4B.1 — Book Generator FakeAI / contracts. 0 réseau réel."""

from __future__ import annotations

import pytest

from app.book_generation.cache import ChapterCache, GenerationState
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    PUBLICATION_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
)
from app.book_generation.errors import BookPublicationBlocked
from app.book_generation.evidence import build_chapter_evidence, evidence_identity
from app.book_generation.fixtures import (
    covering_chapter_transport,
    deferred_idea_transport,
    empty_text_transport,
    excluded_idea_transport,
    extra_section_transport,
    missing_idea_transport,
    missing_section_transport,
    tiny_book_source_map,
    tiny_editorial_plan,
    tiny_transcript_index,
    unknown_idea_transport,
    unknown_source_transport,
    unsourced_paragraph_transport,
    whitespace_text_transport,
    wrong_language_transport,
    wrong_order_transport,
)
from app.book_generation.guard import assert_no_v1_dependency, assert_offline_package
from app.book_generation.models import BookIdentity
from app.book_generation.payload import build_chapter_request
from app.book_generation.pipeline import (
    assemble_book,
    assembled_book_sha256,
    chapter_signature_for,
    materialize_chapter,
)
from app.book_generation.prompt import prompt_bundle
from app.book_generation.schema import schema_identity
from app.book_generation.settings import frozen_production_settings
from app.book_generation.writer import write_book


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _bundle(plan, source_map, chapter, *, hydrate=True):
    index = tiny_transcript_index(source_map) if hydrate else None
    return build_chapter_evidence(
        plan,
        source_map,
        chapter,
        language=source_map.primary_language,
        hydrate=hydrate,
        transcript_index=index,
    )


def _materialize(transport, plan, source_map, chapter, evidence=None):
    evidence = evidence or _bundle(plan, source_map, chapter)
    return materialize_chapter(
        transport,
        plan,
        source_map,
        chapter,
        language=source_map.primary_language,
        allowed_handles=evidence.get("allowed"),
    )


class TestOfflineGuards:
    def test_package_offline(self):
        assert_offline_package()
        assert_no_v1_dependency()
        assert PUBLICATION_AUTHORIZED is False
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0

    def test_publication_blocked(self, tmp_path):
        with pytest.raises(BookPublicationBlocked):
            write_book(tmp_path / "book.json", {"schema_version": "1.0"})


class TestValidChapter:
    def test_valid_sections_ideas_language_and_ids(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        candidate, validation, digest = _materialize(
            covering_chapter_transport(chapter), plan, source_map, chapter
        )
        assert validation.status != "FAIL", validation.errors
        assert [section.section_id for section in candidate.sections] == [
            section.section_id for section in chapter.sections
        ]
        book = assemble_book(
            [
                _materialize(
                    covering_chapter_transport(ch), plan, source_map, ch
                )[0]
                for ch in plan.chapters
            ],
            plan,
            language=source_map.primary_language,
            identity=BookIdentity("s", "p"),
        )
        ids = [paragraph.paragraph_id for paragraph in book.all_paragraphs()]
        assert ids[0] == "P000001"
        assert ids == [f"P{index:06d}" for index in range(1, len(ids) + 1)]
        assert book.title == plan.selected_title
        assert digest


class TestFailureCases:
    @pytest.mark.parametrize(
        "factory",
        [
            missing_section_transport,
            extra_section_transport,
            wrong_order_transport,
            missing_idea_transport,
            unknown_idea_transport,
            unknown_source_transport,
            unsourced_paragraph_transport,
            empty_text_transport,
            whitespace_text_transport,
        ],
    )
    def test_contract_failures(self, factory):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            factory(chapter), plan, source_map, chapter
        )
        assert validation.status == "FAIL"

    def test_wrong_language(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            wrong_language_transport(chapter), plan, source_map, chapter
        )
        assert validation.status in {"FAIL", "REVIEW"}

    def test_deferred_idea_blocked(self):
        source_map = tiny_book_source_map(idea_count=5)
        deferred = (source_map.ideas[-2].idea_id,)
        plan = tiny_editorial_plan(source_map, deferred_ids=deferred)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            deferred_idea_transport(chapter, deferred[0]), plan, source_map, chapter
        )
        assert validation.status == "FAIL"

    def test_excluded_idea_blocked(self):
        source_map = tiny_book_source_map(idea_count=5)
        excluded = (source_map.ideas[-1].idea_id,)
        plan = tiny_editorial_plan(source_map, excluded_ids=excluded)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            excluded_idea_transport(chapter, excluded[0]), plan, source_map, chapter
        )
        assert validation.status == "FAIL"

    def test_connective_paragraph_allowed(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            covering_chapter_transport(chapter, include_connective=True),
            plan,
            source_map,
            chapter,
        )
        assert validation.status != "FAIL", validation.errors
        assert any(
            paragraph.is_connective
            for section in _candidate.sections
            for paragraph in section.paragraphs
        )


class TestDeterminismCacheResume:
    def test_same_inputs_same_hashes_and_ids(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        transport = covering_chapter_transport(plan.chapters[0])
        a = _materialize(transport, plan, source_map, plan.chapters[0])
        b = _materialize(transport, plan, source_map, plan.chapters[0])
        assert a[2] == b[2]
        books = []
        for _ in range(2):
            candidates = [
                _materialize(
                    covering_chapter_transport(ch), plan, source_map, ch
                )[0]
                for ch in plan.chapters
            ]
            books.append(
                assemble_book(
                    candidates,
                    plan,
                    language=source_map.primary_language,
                    identity=BookIdentity("s", "p"),
                )
            )
        assert assembled_book_sha256(books[0]) == assembled_book_sha256(books[1])
        assert [p.paragraph_id for p in books[0].all_paragraphs()] == [
            p.paragraph_id for p in books[1].all_paragraphs()
        ]

    def test_cache_hit_and_misses(self):
        prompt = prompt_bundle()
        schema = schema_identity()
        settings = frozen_production_settings()
        base = dict(
            source_map_sha256="map",
            editorial_plan_sha256="plan",
            chapter_id="CH001",
            prompt_sha256=prompt["prompt_sha256"],
            response_schema_sha256=schema["raw_schema_sha256"],
            language="en",
            evidence_bundle_sha256="ev",
            settings=settings,
        )
        hit = chapter_signature_for(**base)
        cache = ChapterCache()
        cache.remember(hit, "abc")
        assert cache.is_hit(hit)
        assert not cache.is_hit(chapter_signature_for(**{**base, "prompt_sha256": "x"}))
        assert not cache.is_hit(
            chapter_signature_for(**{**base, "editorial_plan_sha256": "x"})
        )
        assert not cache.is_hit(
            chapter_signature_for(**{**base, "source_map_sha256": "x"})
        )
        assert not cache.is_hit(chapter_signature_for(**{**base, "language": "fr"}))
        assert not cache.is_hit(
            chapter_signature_for(**{**base, "evidence_bundle_sha256": "x"})
        )

    def test_resume_preserves_validated_chapters(self):
        state = GenerationState()
        state.remember_validated("CH001", "sig1", "h1")
        state.remember_validated("CH002", "sig2", "h2")
        state.remember_failed("CH003", "scripted")
        assert state.reusable("CH001", "sig1")
        assert state.reusable("CH002", "sig2")
        assert not state.reusable("CH003", "sig3")


class TestRequestAndSchema:
    def test_versions_and_structured_request(self):
        assert BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
        assert BOOK_GENERATION_TRANSPORT_VERSION == "book-generation-transport-1.0"
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        evidence = _bundle(plan, source_map, plan.chapters[0])
        request = build_chapter_request(evidence)
        assert request.stage == "book_generation"
        assert request.response_schema is not None
        assert request.metadata.get("transport_version") == BOOK_GENERATION_TRANSPORT_VERSION
        first = evidence_identity(evidence)
        second = evidence_identity(
            _bundle(plan, source_map, plan.chapters[0])
        )
        assert first == second
        schema = schema_identity()
        assert schema["raw_schema_bytes"] > 0
        assert schema["adapted_schema_bytes"] > 0
        assert schema["additional_properties_false_on_adapted"] is True


class TestEvidenceSubset:
    def test_does_not_include_other_chapter_ideas(self):
        source_map = tiny_book_source_map(idea_count=5)
        plan = tiny_editorial_plan(source_map)
        evidence = _bundle(plan, source_map, plan.chapters[0])
        chapter_ideas = set(plan.chapters[0].idea_refs)
        other = set(plan.chapters[1].idea_refs) - chapter_ideas
        bundled = {item["id"] for item in evidence["ideas"]}
        assert chapter_ideas <= bundled
        assert bundled.isdisjoint(other)
        assert evidence["book"]["canonical_document_language"] == "en"
        assert evidence["voice"]
        assert "SRC" in "".join(evidence["src"]) or evidence["src"]
