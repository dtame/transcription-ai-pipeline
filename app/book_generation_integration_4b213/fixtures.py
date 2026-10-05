"""Synthetic offline chapter fixtures. Explicitly FakeAI. Not Sonnet output."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
)
from app.book_generation_integration_4b213.constants import (
    FAKEAI_SOURCE,
    FIXTURE_KIND,
    INTEGRATION_CONTRACT_VERSION,
    PHASE,
    PROMPT_VERSION_202_CANDIDATE,
    SYNTHETIC_EDITORIAL_PLAN_HASH,
    SYNTHETIC_PREFIX,
    SYNTHETIC_SOURCE_MAP_HASH,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.file_utils import content_hash

SYN_IDEA = f"{SYNTHETIC_PREFIX}IDEA001"
SYN_SRC = f"{SYNTHETIC_PREFIX}SRC001"
SYN_ALLOWED = (SYN_IDEA, SYN_SRC)

TEXTS = {
    "fully_supported": (
        "The teaching already given is that fear does not calculate or bargain "
        "with the person who belongs to the truth."
    ),
    "invented_causality": (
        "Fear still governs the room because it still works wherever it is not "
        "resisted by truth."
    ),
    "invented_implication": (
        "The silence of the congregation which means that every doubt has already "
        "been answered in advance."
    ),
    "universal_guarantee": (
        "Every believer is guaranteed a fearless death under this teaching."
    ),
    "unsupported_reference": (
        "The remainder of the citation is completed as Habakkuk 3:4 without the "
        "supplied evidence."
    ),
    "legitimate_paraphrase": (
        "Fear cannot calculate, and it cannot bargain with the person who already "
        "belongs to the truth."
    ),
    "questionable": (
        "The speaker may have intended a broader pastoral application than the "
        "supplied evidence records."
    ),
    "invalid_json": (
        "The teaching already given is that fear does not calculate or bargain "
        "with the person who belongs to the truth."
    ),
    "missing_response": (
        "The teaching already given is that fear does not calculate or bargain "
        "with the person who belongs to the truth."
    ),
    "interruption": (
        "The teaching already given is that fear does not calculate or bargain "
        "with the person who belongs to the truth."
    ),
    "invalid_evidence_handle": (
        "A generated sentence cites a handle that is not in the authorized bundle."
    ),
    "missing_evidence": (
        "A substantive paragraph states a claim without any evidence handle."
    ),
}


def _paragraph(
    *,
    paragraph_id: str,
    text: str,
    kind: str,
    evidence: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
    idea_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "paragraph_id": paragraph_id,
        "kind": kind,
        "text": text,
        "evidence_handles": list(evidence),
        "source_refs": list(source_refs),
        "idea_refs": list(idea_refs),
        "synthetic": True,
        "fixture_kind": FIXTURE_KIND,
    }


def build_synthetic_chapter(
    scenario: str,
    *,
    chapter_id: str | None = None,
    extra_paragraphs: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    cid = chapter_id or f"{SYNTHETIC_PREFIX}CH001"
    if scenario == "invalid_evidence_handle":
        evidence = (f"{SYNTHETIC_PREFIX}SRC999",)
        source_refs = evidence
        idea_refs: tuple[str, ...] = ()
        text = TEXTS[scenario]
        kind = PARAGRAPH_KIND_SUBSTANTIVE
    elif scenario == "missing_evidence":
        evidence = ()
        source_refs = ()
        idea_refs = ()
        text = TEXTS[scenario]
        kind = PARAGRAPH_KIND_SUBSTANTIVE
    else:
        evidence = SYN_ALLOWED
        source_refs = (SYN_SRC,)
        idea_refs = (SYN_IDEA,)
        text = TEXTS[scenario]
        kind = PARAGRAPH_KIND_SUBSTANTIVE
    connective = _paragraph(
        paragraph_id=f"{cid}-P000001",
        text="The next movement of the book now turns to this subject.",
        kind=PARAGRAPH_KIND_CONNECTIVE,
    )
    substantive = _paragraph(
        paragraph_id=f"{cid}-P000002",
        text=text,
        kind=kind,
        evidence=evidence,
        source_refs=source_refs,
        idea_refs=idea_refs,
    )
    paragraphs = [connective, substantive]
    if extra_paragraphs:
        paragraphs.extend(dict(item) for item in extra_paragraphs)
    chapter = {
        "chapter_id": cid,
        "title": "Synthetic offline chapter",
        "synthetic": True,
        "fixture_kind": FIXTURE_KIND,
        "source": FAKEAI_SOURCE,
        "not_sonnet": True,
        "not_terra": True,
        "scenario": scenario,
        "source_map_sha256": SYNTHETIC_SOURCE_MAP_HASH,
        "editorial_plan_sha256": SYNTHETIC_EDITORIAL_PLAN_HASH,
        "generator_prompt_version": BOOK_GENERATOR_PROMPT_VERSION,
        "generator_transport_version": BOOK_GENERATION_TRANSPORT_VERSION,
        "semantic_contract_version": PROMPT_VERSION_202_CANDIDATE,
        "semantic_transport_version": TRANSPORT_VERSION_20_CANDIDATE,
        "integration_contract_version": INTEGRATION_CONTRACT_VERSION,
        "allowed_evidence_handles": list(SYN_ALLOWED),
        "sections": [
            {
                "section_id": f"{cid}-SEC001",
                "title": "Synthetic section",
                "synthetic": True,
                "paragraphs": paragraphs,
            }
        ],
    }
    chapter["generated_text_sha256"] = content_hash(
        "\n".join(str(para.get("text") or "") for para in paragraphs)
    )
    return chapter


GENERATION_SCENARIO_NAMES = tuple(TEXTS.keys())


def generation_scenario_catalog() -> dict[str, Any]:
    rows = []
    for name in GENERATION_SCENARIO_NAMES:
        chapter = build_synthetic_chapter(name)
        rows.append(
            {
                "scenario": name,
                "source": FAKEAI_SOURCE,
                "not_sonnet": True,
                "not_terra": True,
                "fixture_kind": FIXTURE_KIND,
                "chapter_id": chapter["chapter_id"],
                "paragraph_count": sum(
                    len(section["paragraphs"]) for section in chapter["sections"]
                ),
                "synthetic_handles_only": all(
                    str(handle).startswith(SYNTHETIC_PREFIX)
                    for section in chapter["sections"]
                    for para in section["paragraphs"]
                    for handle in para.get("evidence_handles") or []
                ),
            }
        )
    return {
        "phase": PHASE,
        "source": FAKEAI_SOURCE,
        "role": "simulated_book_generator",
        "not_sonnet": True,
        "not_a_real_chapter": True,
        "scenario_count": len(rows),
        "scenarios": rows,
        "secrets_included": False,
    }


__all__ = [
    "GENERATION_SCENARIO_NAMES",
    "SYN_ALLOWED",
    "SYN_IDEA",
    "SYN_SRC",
    "TEXTS",
    "build_synthetic_chapter",
    "generation_scenario_catalog",
]
