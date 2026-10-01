"""FakeAI catalog for Book Generator. Scripted parsed transports only."""

from __future__ import annotations

from typing import Any, Callable

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.book_generation.constants import STAGE_BOOK_GENERATION
from app.book_generation.fixtures import covering_chapter_transport
from app.book_generation.payload import build_chapter_request
from app.book_generation.pipeline import materialize_chapter
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


def fake_engine_for(transport: dict[str, Any]) -> FakeAIEngine:
    return FakeAIEngine(
        script=[
            FakeReply(
                parsed=transport,
                input_tokens=100,
                output_tokens=200,
                model="claude-sonnet-5",
            )
        ]
    )


def run_fake_chapter(
    transport: dict[str, Any],
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    *,
    language: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = build_chapter_request(evidence or {"chapter": {"id": chapter.chapter_id}, "book": {"canonical_document_language": language}, "sections": [], "ideas": [], "allowed": [], "blocked": [], "voice": {}, "continuity": {}, "src": [], "src_text": [], "examples": [], "references": [], "uncertainties": {}, "rules": {}})
    # Minimal evidence may fail AIRequest if prompt empty — build_chapter_request
    # always has instruction+json. Use provided evidence when present.
    if evidence is not None:
        request = build_chapter_request(evidence)
    engine = fake_engine_for(transport)
    response = engine.generate(request)
    try:
        candidate, validation, digest = materialize_chapter(
            response.parsed,
            plan,
            source_map,
            chapter,
            language=language,
            allowed_handles=list((evidence or {}).get("allowed") or []),
        )
    except Exception as exc:  # transport/schema contract failures are FAIL
        from app.book_generation.validator import BookGenerationValidation

        return {
            "engine_calls": engine.call_count,
            "stage": request.stage,
            "parsed_is_mapping": isinstance(response.parsed, dict),
            "validation": BookGenerationValidation(
                status="FAIL", errors=(str(exc),), warnings=()
            ).to_dict(),
            "candidate": None,
            "candidate_sha256": "",
            "expected_stage": STAGE_BOOK_GENERATION,
        }
    return {
        "engine_calls": engine.call_count,
        "stage": request.stage,
        "parsed_is_mapping": isinstance(response.parsed, dict),
        "validation": validation.to_dict(),
        "candidate": candidate,
        "candidate_sha256": digest,
        "expected_stage": STAGE_BOOK_GENERATION,
    }


def scripted_replies(
    factory: Callable[[EditorialChapter], dict[str, Any]],
    chapter: EditorialChapter,
    count: int = 1,
) -> FakeAIEngine:
    transport = factory(chapter)
    return FakeAIEngine(
        script=[FakeReply(parsed=transport, model="claude-sonnet-5")] * count
    )


def valid_transport(chapter: EditorialChapter) -> dict[str, Any]:
    return covering_chapter_transport(chapter)
