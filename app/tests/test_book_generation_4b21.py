"""Phase 4B.2.1 — FakeAI / prompt / validator / replay. 0 réseau."""

from __future__ import annotations

import json

import pytest

from app.book_generation.cache import ChapterSignatureInputs, build_chapter_signature
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION_V10,
    BOOK_GENERATOR_VALIDATOR_VERSION,
)
from app.book_generation.fixtures import (
    connective_new_claim_transport,
    covering_chapter_transport,
    empty_text_transport,
    extra_section_transport,
    invented_example_transport,
    invented_hypothetical_transport,
    invented_reference_transport,
    missing_idea_transport,
    missing_section_transport,
    supported_example_transport,
    tiny_book_source_map,
    tiny_editorial_plan,
    valid_connective_transport,
    whitespace_text_transport,
    wrong_order_transport,
)
from app.book_generation.payload import build_chapter_request, payload_audit
from app.book_generation.pipeline import materialize_chapter
from app.book_generation.prompt import (
    FROZEN_PROMPT_SHA256,
    prompt_bundle as prompt_bundle_v10,
)
from app.book_generation.prompt_v101 import prompt_bundle as prompt_bundle_v101
from app.book_generation.schema import schema_identity
from app.book_generation.semantic_review import review_semantic_fixture
from app.book_generation.settings import frozen_production_settings
from app.book_generation.writer import candidate_sha256
from app.book_generator_canary_4b2.constants import (
    PHASE_4B1_CH016_REQUEST_SHA256,
    PHASE_4B1_RAW_SCHEMA_BYTES,
    PHASE_4B1_RAW_SCHEMA_SHA256,
    PROJECT_NAME,
    TARGET_CHAPTER_ID,
)
from app.book_generator_canary_4b2.paths import canary_audit_dir
from app.book_generator_canary_4b2.validate import interpret_production_response
from app.book_generator_forensics_4b21.guard import assert_offline_package
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _bundle(plan, source_map, chapter):
    from app.book_generation.evidence import build_chapter_evidence
    from app.book_generation.fixtures import tiny_transcript_index

    return build_chapter_evidence(
        plan,
        source_map,
        chapter,
        language=source_map.primary_language,
        hydrate=True,
        transcript_index=tiny_transcript_index(source_map),
    )


def _materialize(transport, plan, source_map, chapter):
    evidence = _bundle(plan, source_map, chapter)
    return materialize_chapter(
        transport,
        plan,
        source_map,
        chapter,
        language=source_map.primary_language,
        allowed_handles=evidence.get("allowed"),
    )


class TestOfflineAndVersions:
    def test_package_offline_and_versions(self):
        assert_offline_package()
        assert BOOK_GENERATOR_PROMPT_VERSION_V10 == "book-generator-1.0"
        assert BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
        assert BOOK_GENERATION_TRANSPORT_VERSION == "book-generation-transport-1.0"
        assert BOOK_GENERATOR_VALIDATOR_VERSION == "book-generation-validator-1.0.1"
        historical = prompt_bundle_v10()
        successor = prompt_bundle_v101()
        assert historical["prompt_sha256"] == FROZEN_PROMPT_SHA256
        assert historical["version"] == "book-generator-1.0"
        assert successor["version"] == "book-generator-1.0.1"
        assert successor["prompt_sha256"] != historical["prompt_sha256"]
        assert "p9b" not in successor["system"]
        assert "funeral" not in successor["system"].lower()
        assert "CH016" not in successor["system"]
        schema = schema_identity()
        assert schema["raw_schema_bytes"] == PHASE_4B1_RAW_SCHEMA_BYTES
        assert schema["raw_schema_sha256"] == PHASE_4B1_RAW_SCHEMA_SHA256


class TestParagraphInvariants:
    def test_empty_text_fails(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            empty_text_transport(chapter), plan, source_map, chapter
        )
        assert validation.status == "FAIL"
        assert any("empty text" in item for item in validation.errors)

    def test_whitespace_text_fails(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            whitespace_text_transport(chapter), plan, source_map, chapter
        )
        assert validation.status == "FAIL"
        assert any("empty text" in item for item in validation.errors)

    def test_empty_substantive_evidence_fails(self):
        from app.book_generation.fixtures import unsourced_paragraph_transport

        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            unsourced_paragraph_transport(chapter), plan, source_map, chapter
        )
        assert validation.status == "FAIL"
        assert any("no evidence handles" in item for item in validation.errors)

    def test_valid_connective_passes_validator(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            valid_connective_transport(chapter), plan, source_map, chapter
        )
        assert validation.status != "FAIL", validation.errors
        semantic = review_semantic_fixture(
            valid_connective_transport(chapter),
            _bundle(plan, source_map, chapter),
            fixture_name="valid_connective",
        )
        assert semantic["status"] == "PASS"


class TestSemanticFixtures:
    def test_connective_new_claim_is_semantic_fail_not_dropped(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        transport = connective_new_claim_transport(chapter)
        candidate, validation, _digest = _materialize(
            transport, plan, source_map, chapter
        )
        assert any(paragraph.provider_handle == "con-new-claim" for section in candidate.sections for paragraph in section.paragraphs)
        semantic = review_semantic_fixture(
            transport,
            _bundle(plan, source_map, chapter),
            fixture_name="connective_new_claim",
        )
        assert semantic["status"] == "FAIL"
        assert semantic["findings"][0]["class"] == "SUBSTANTIVE_UNSUPPORTED"
        assert "cannot infer" in semantic["findings"][0]["reason"]

    def test_invented_example_semantic_fail(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        transport = invented_example_transport(chapter)
        semantic = review_semantic_fixture(
            transport,
            _bundle(plan, source_map, chapter),
            fixture_name="invented_example",
        )
        assert semantic["status"] == "FAIL"
        assert semantic["findings"][0]["class"] == "INVENTED_EXAMPLE"

    def test_supported_example_semantic_pass(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        transport = supported_example_transport(chapter)
        _candidate, validation, _digest = _materialize(
            transport, plan, source_map, chapter
        )
        assert validation.status != "FAIL", validation.errors
        semantic = review_semantic_fixture(
            transport,
            _bundle(plan, source_map, chapter),
            fixture_name="supported_example",
        )
        assert semantic["status"] == "PASS"

    def test_invented_hypothetical_semantic_fail(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        semantic = review_semantic_fixture(
            invented_hypothetical_transport(chapter),
            _bundle(plan, source_map, chapter),
            fixture_name="invented_hypothetical",
        )
        assert semantic["status"] == "FAIL"

    def test_invented_reference_semantic_fail(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        semantic = review_semantic_fixture(
            invented_reference_transport(chapter),
            _bundle(plan, source_map, chapter),
            fixture_name="invented_reference",
        )
        assert semantic["status"] == "FAIL"


class TestCoverageAndSectionsPreserved:
    @pytest.mark.parametrize(
        "factory",
        [
            missing_section_transport,
            extra_section_transport,
            wrong_order_transport,
            missing_idea_transport,
        ],
    )
    def test_section_and_idea_contracts(self, factory):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            factory(chapter), plan, source_map, chapter
        )
        assert validation.status == "FAIL"

    def test_covering_transport_still_passes(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        chapter = plan.chapters[0]
        _candidate, validation, _digest = _materialize(
            covering_chapter_transport(chapter), plan, source_map, chapter
        )
        assert validation.status != "FAIL", validation.errors


class TestRequestVersioningAndCache:
    def test_prompt_version_changes_request_and_cache(self):
        source_map = tiny_book_source_map()
        plan = tiny_editorial_plan(source_map)
        evidence = _bundle(plan, source_map, plan.chapters[0])
        settings = frozen_production_settings()
        v10 = payload_audit(
            evidence,
            settings=settings,
            prompt_version=BOOK_GENERATOR_PROMPT_VERSION_V10,
        )
        v101 = payload_audit(
            evidence,
            settings=settings,
            prompt_version=BOOK_GENERATOR_PROMPT_VERSION,
        )
        assert v10["payload_sha256"] != v101["payload_sha256"]
        assert v10["prompt_version"] == "book-generator-1.0"
        assert v101["prompt_version"] == "book-generator-1.0.1"
        request = build_chapter_request(evidence)
        assert request.metadata["prompt_version"] == "book-generator-1.0.1"
        schema = schema_identity()
        sig_a = build_chapter_signature(
            ChapterSignatureInputs(
                source_map_sha256="map",
                editorial_plan_sha256="plan",
                chapter_id="CH001",
                prompt_version="book-generator-1.0",
                prompt_sha256=v10["prompt"]["prompt_sha256"],
                transport_version=BOOK_GENERATION_TRANSPORT_VERSION,
                schema_version="1.0",
                response_schema_sha256=schema["raw_schema_sha256"],
                provider=settings.provider,
                model=settings.model,
                thinking_mode=settings.thinking_mode,
                effort="",
                max_output_tokens=16384,
                canonical_language="en",
                evidence_bundle_sha256="ev",
            )
        )
        sig_b = build_chapter_signature(
            ChapterSignatureInputs(
                source_map_sha256="map",
                editorial_plan_sha256="plan",
                chapter_id="CH001",
                prompt_version="book-generator-1.0.1",
                prompt_sha256=v101["prompt"]["prompt_sha256"],
                transport_version=BOOK_GENERATION_TRANSPORT_VERSION,
                schema_version="1.0",
                response_schema_sha256=schema["raw_schema_sha256"],
                provider=settings.provider,
                model=settings.model,
                thinking_mode=settings.thinking_mode,
                effort="",
                max_output_tokens=16384,
                canonical_language="en",
                evidence_bundle_sha256="ev",
            )
        )
        assert sig_a != sig_b


class TestHistoricalReplay:
    def test_historical_candidate_still_fails_empty_paragraph(self):
        raw_path = canary_audit_dir() / "book_generator_4b2_raw_structured_response.json"
        if not raw_path.is_file():
            pytest.skip("real canary raw response not present")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        plan, *_rest = load_published_editorial_plan(PROJECT_NAME)
        source_map, *_map = load_published_source_map(PROJECT_NAME)
        chapter = next(
            item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID
        )
        from app.book_generation.evidence import build_chapter_evidence
        from app.book_generation.hydrate import load_clean_transcript_index
        from app.book_generation.language import resolve_canonical_language

        index = load_clean_transcript_index(PROJECT_NAME)
        language = resolve_canonical_language(
            source_map_primary_language=source_map.primary_language,
            transcript_primary_language=index.primary_language,
        )
        evidence = build_chapter_evidence(
            plan,
            source_map,
            chapter,
            language=language,
            hydrate=True,
            transcript_index=index,
        )
        first = interpret_production_response(
            raw.get("parsed"),
            plan=plan,
            source_map=source_map,
            chapter=chapter,
            language=language,
            allowed_handles=list(evidence.get("allowed") or []),
            provider_raw_sha256=str(raw.get("sha256") or ""),
        )
        second = interpret_production_response(
            raw.get("parsed"),
            plan=plan,
            source_map=source_map,
            chapter=chapter,
            language=language,
            allowed_handles=list(evidence.get("allowed") or []),
            provider_raw_sha256=str(raw.get("sha256") or ""),
        )
        assert first["candidate_sha256"] == second["candidate_sha256"]
        assert first["candidate_sha256"] == (
            "51635cedf7fee34b34fd80466c2361968494e2e98c15d861682401bddd2aaad5"
        )
        assert first["local_validator"]["status"] == "FAIL"
        assert any("empty text" in item for item in first["local_validator"]["errors"])
        candidate = first["candidate"]
        assert any(
            para.get("provider_handle") == "p9b" and para.get("text") == ""
            for section in candidate["sections"]
            for para in section["paragraphs"]
        )
        assert PHASE_4B1_CH016_REQUEST_SHA256
        assert candidate_sha256(candidate) == first["candidate_sha256"]
