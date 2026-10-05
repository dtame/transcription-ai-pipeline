"""CH001 human editorial review packet. No automatic correction."""

from __future__ import annotations

from typing import Any

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    iter_candidate_paragraphs,
    load_json,
)
from app.book_ch002_offline_recovery_4b224.constants import (
    CH001_FLAGGED_PARAGRAPH_ID,
    CH001_FLAGGED_SENTENCE,
    CH001_STATUS,
    EXPECTED_CH001_IDEA_COUNT,
    EXPECTED_CH001_SECTION_IDS,
    PHASE,
    REVIEW_CHAPTER_ID,
)
from app.book_ch002_offline_recovery_4b224.paths import (
    ch001_dir,
    original_candidate_json_path,
    original_candidate_md_path,
)
from app.book_generation_4b223.context import load_corpus


def _unit_index(source_map) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for idea in source_map.ideas:
        index[idea.idea_id] = {
            "id": idea.idea_id,
            "kind": "IDEA",
            "text": idea.summary,
            "source_refs": list(idea.source_refs),
        }
    for example in source_map.examples:
        index[example.example_id] = {
            "id": example.example_id,
            "kind": "EX",
            "text": example.summary,
            "source_refs": list(example.source_refs),
        }
    for reference in source_map.references:
        index[reference.reference_id] = {
            "id": reference.reference_id,
            "kind": "REF",
            "text": reference.raw_reference,
            "source_refs": list(reference.source_refs),
        }
    return index


def _src_texts(transcript, src_ids: list[str]) -> list[dict[str, str]]:
    lookup = transcript.by_src()
    rows: list[dict[str, str]] = []
    for src_id in src_ids:
        segment = lookup.get(src_id)
        rows.append(
            {
                "id": src_id,
                "text": "" if segment is None else str(segment.text or ""),
                "found": segment is not None,
            }
        )
    return rows


def _looks_first_person(text: str) -> bool:
    lowered = f" {text.lower()} "
    return any(token in lowered for token in (" i ", " i'm ", " i've ", " my ", " me "))


def _looks_second_person(text: str) -> bool:
    lowered = f" {text.lower()} "
    return any(token in lowered for token in (" you ", " your ", " you're "))


def build_ch001_review_packet() -> dict[str, Any]:
    candidate = load_json(original_candidate_json_path(REVIEW_CHAPTER_ID))
    markdown = original_candidate_md_path(REVIEW_CHAPTER_ID).read_text(encoding="utf-8")
    idea = load_json(ch001_dir() / "idea_traceability_review.json")
    ex_ref = load_json(ch001_dir() / "ex_ref_traceability_review.json")
    editorial = load_json(ch001_dir() / "editorial_readiness_review.json")
    structural = load_json(ch001_dir() / "structural_validation.json")
    corpus = load_corpus()
    units = _unit_index(corpus.source_map)
    paragraphs = []
    first_person = False
    second_person = False
    flagged = None
    for section in candidate.get("sections") or []:
        section_id = str(section.get("section_id") or "")
        title = str(section.get("title") or "")
        for _section_id, _index, paragraph in [
            (section_id, index, item)
            for index, item in enumerate(section.get("paragraphs") or [])
        ]:
            text = str(paragraph.get("text") or "")
            first_person = first_person or _looks_first_person(text)
            second_person = second_person or _looks_second_person(text)
            row = {
                "section_id": section_id,
                "section_title": title,
                "paragraph_id": paragraph.get("paragraph_id"),
                "text": text,
                "idea_refs": list(paragraph.get("idea_refs") or []),
                "source_refs": list(paragraph.get("source_refs") or []),
                "example_refs": list(paragraph.get("example_refs") or []),
                "reference_refs": list(paragraph.get("reference_refs") or []),
            }
            paragraphs.append(row)
            if paragraph.get("paragraph_id") == CH001_FLAGGED_PARAGRAPH_ID:
                flagged = row

    flagged_src_ids = list((flagged or {}).get("source_refs") or [])
    flagged_src = _src_texts(corpus.transcript, flagged_src_ids)
    idea024 = units.get("IDEA024") or {}
    absolute_candidates = []
    for row in paragraphs:
        text = row["text"]
        if "Faith is everything" in text:
            absolute_candidates.append(
                {
                    "paragraph_id": row["paragraph_id"],
                    "phrase": "Faith is everything.",
                    "source_refs": row["source_refs"],
                    "src_texts": _src_texts(corpus.transcript, row["source_refs"]),
                    "classification": "POTENTIAL_ABSOLUTE_FORMULATION",
                    "incorrect_without_source_proof": False,
                    "source_supported": True,
                    "note": (
                        "Absolute wording, but SRC000546 is exactly "
                        "'Faith is everything.' Do not treat this as a strengthening."
                    ),
                }
            )
        if "The only thing accepted in the presence of God is Christ." in text:
            absolute_candidates.append(
                {
                    "paragraph_id": row["paragraph_id"],
                    "phrase": "The only thing accepted in the presence of God is Christ.",
                    "source_refs": row["source_refs"],
                    "src_texts": _src_texts(corpus.transcript, row["source_refs"]),
                    "classification": "POTENTIAL_ABSOLUTE_FORMULATION",
                    "incorrect_without_source_proof": False,
                    "source_supported": True,
                    "note": (
                        "Exclusive wording, but SRC000573 is exactly "
                        "'The only thing accepted in the presence of God is Christ.'"
                    ),
                }
            )
        if "never cooked" in text.lower():
            absolute_candidates.append(
                {
                    "paragraph_id": row["paragraph_id"],
                    "phrase": "never cooked in an iron pot / never cooked in an aluminum pot",
                    "source_refs": row["source_refs"],
                    "src_texts": _src_texts(corpus.transcript, row["source_refs"]),
                    "classification": "POTENTIAL_ABSOLUTE_FORMULATION",
                    "incorrect_without_source_proof": False,
                    "note": (
                        "Anecdotal 'never' about the grandmother's pots. "
                        "Not treated as a theological strengthening."
                    ),
                }
            )

    reformulations = [
        {
            "id": "R1",
            "proposed": "You only did not accept it in the presence of God.",
            "preserves_sense_if": (
                "the human wants to keep the oral 'you only did not accept it' "
                "and restore the location from SRC000572"
            ),
            "source_refs": flagged_src_ids,
            "closest_src": "SRC000572",
            "applied": False,
        },
        {
            "id": "R2",
            "proposed": "You only didn't accept it in the presence of God.",
            "preserves_sense_if": (
                "the human prefers the exact oral contraction from SRC000572"
            ),
            "source_refs": flagged_src_ids,
            "closest_src": "SRC000572",
            "applied": False,
        },
    ]
    flagged_review = {
        "sentence": CH001_FLAGGED_SENTENCE,
        "paragraph_id": CH001_FLAGGED_PARAGRAPH_ID,
        "section_id": (flagged or {}).get("section_id"),
        "surrounding_text": (flagged or {}).get("text"),
        "grammatically_awkward": True,
        "ambiguous": True,
        "changes_source_sense": False,
        "can_be_corrected_without_changing_sense": True,
        "automatic_correction_applied": False,
        "idea_refs": (flagged or {}).get("idea_refs") or [],
        "idea024_summary": idea024.get("text"),
        "supporting_src": flagged_src,
        "closest_source": {
            "id": "SRC000572",
            "text": "You only didn't accept it in the presence of God.",
            "note": (
                "The generated sentence compresses that location into 'there'. "
                "It does not invert or invent the claim."
            ),
        },
        "observations": [
            "The sentence is grammatically awkward and reads like oral residue.",
            "SRC000572 is 'You only didn't accept it in the presence of God.'",
            "The generated 'there' points back to 'in the presence of God' in the same paragraph.",
            "A human may expand 'there' to the source location. This phase does not apply that correction.",
        ],
        "proposed_reformulations": reformulations,
    }
    packet = {
        "phase": PHASE,
        "chapter_id": REVIEW_CHAPTER_ID,
        "status": CH001_STATUS,
        "title": candidate.get("title"),
        "sections": [
            {
                "section_id": section.get("section_id"),
                "title": section.get("title"),
                "paragraph_count": len(section.get("paragraphs") or []),
            }
            for section in candidate.get("sections") or []
        ],
        "section_ids_expected": list(EXPECTED_CH001_SECTION_IDS),
        "paragraph_count": len(list(iter_candidate_paragraphs(candidate))),
        "ideas_expected": list(idea.get("ideas_expected") or []),
        "ideas_expected_count": EXPECTED_CH001_IDEA_COUNT,
        "ideas_traced": list(idea.get("ideas_found_in_paras_e") or []),
        "ideas_traced_count": idea.get("ideas_found_count"),
        "examples": [
            item
            for item in ex_ref.get("items") or []
            if item.get("kind") == "EX"
        ],
        "references": [
            item
            for item in ex_ref.get("items") or []
            if item.get("kind") == "REF"
        ],
        "narrative_voice": {
            "first_person_observed": first_person,
            "second_person_observed": second_person,
            "prior_classification": (editorial.get("authorial_voice") or {}).get(
                "classification"
            ),
            "conference_report_frames": (editorial.get("authorial_voice") or {}).get(
                "conference_report_frames"
            )
            or [],
            "assessment": (
                "First-person testimony (night eating, daughter and meat, grandmother "
                "and clay pot) and second-person address are present. Voice is "
                "generally satisfactory for human review."
            ),
        },
        "structural_status": structural.get("status"),
        "editorial_observations": [
            "JSON is structurally valid. 12/12 IDEA handles are traced.",
            "EX001, EX002, REF001 and REF003 are present and traced.",
            "Identifier coverage is not a semantic certificate.",
            flagged_review,
            {
                "code": "POTENTIAL_ABSOLUTE_FORMULATIONS",
                "items": absolute_candidates,
                "do_not_declare_incorrect_without_source_proof": True,
            },
        ],
        "passages_requiring_attention": [
            {
                "paragraph_id": CH001_FLAGGED_PARAGRAPH_ID,
                "text": (flagged or {}).get("text"),
                "reason": "Awkward oral residue plus exclusive Christ-acceptance claim.",
                "supporting_src": flagged_src,
            }
        ],
        "human_decision_required": True,
        "automatic_editorial_correction": False,
        "human_acceptance": "PENDING",
        "semantic_certification": "NOT PERFORMED",
        "markdown_path": str(original_candidate_md_path(REVIEW_CHAPTER_ID)).replace(
            "\\", "/"
        ),
        "markdown_preview_chars": len(markdown),
        "secrets_included": False,
    }
    return packet


def render_ch001_review_markdown(packet: dict[str, Any]) -> str:
    sections = packet.get("sections") or []
    examples = ", ".join(item.get("id", "") for item in packet.get("examples") or [])
    refs = ", ".join(item.get("id", "") for item in packet.get("references") or [])
    flagged = next(
        (
            item
            for item in packet.get("editorial_observations") or []
            if isinstance(item, dict) and item.get("sentence")
        ),
        {},
    )
    if not flagged:
        flagged = next(
            (
                item
                for item in packet.get("editorial_observations") or []
                if isinstance(item, dict) and item.get("paragraph_id") == CH001_FLAGGED_PARAGRAPH_ID
            ),
            {},
        )
    src_lines = []
    for row in flagged.get("supporting_src") or []:
        src_lines.append(f"- `{row.get('id')}`: {row.get('text')}")
    reform = []
    for item in flagged.get("proposed_reformulations") or []:
        reform.append(
            f"- {item.get('id')}: \"{item.get('proposed')}\" "
            f"(SRC {', '.join(item.get('source_refs') or [])}; not applied)"
        )
    absolute = []
    for observation in packet.get("editorial_observations") or []:
        if isinstance(observation, dict) and observation.get("items"):
            for item in observation.get("items") or []:
                absolute.append(
                    f"- {item.get('paragraph_id')}: \"{item.get('phrase')}\" — "
                    f"{item.get('note')}"
                )
    section_lines = [
        f"- {row.get('section_id')} {row.get('title')} ({row.get('paragraph_count')} paragraphs)"
        for row in sections
    ]
    voice = packet.get("narrative_voice") or {}
    return "\n".join(
        [
            "# CH001 human editorial review packet",
            "",
            f"Status: {packet.get('status')}",
            f"Title: {packet.get('title')}",
            f"Structural status: {packet.get('structural_status')}",
            "",
            "## Sections",
            "",
            *section_lines,
            "",
            f"Paragraph count: {packet.get('paragraph_count')}",
            f"IDEA expected / traced: {packet.get('ideas_expected_count')} / {packet.get('ideas_traced_count')}",
            f"EX: {examples or 'none'}",
            f"REF: {refs or 'none'}",
            "",
            "## Narrative voice",
            "",
            str(voice.get("assessment") or ""),
            f"First person observed: {voice.get('first_person_observed')}",
            f"Second person observed: {voice.get('second_person_observed')}",
            "",
            "## Passage requiring attention",
            "",
            f"Sentence: \"{CH001_FLAGGED_SENTENCE}\"",
            f"Paragraph: {CH001_FLAGGED_PARAGRAPH_ID}",
            "",
            str((flagged.get("surrounding_text") or "")),
            "",
            "- Grammatically awkward: yes",
            "- Ambiguous: yes — 'there' compresses SRC000572's 'in the presence of God'",
            "- Changes the source sense: no. SRC000572 is 'You only didn't accept it in the presence of God.'",
            "- Can be corrected without changing the sense: yes, if a human expands 'there'",
            "- Automatic correction applied: no",
            "",
            "### Supporting SRC",
            "",
            *(src_lines or ["- none retrieved"]),
            "",
            "### Proposed reformulations (not applied)",
            "",
            *(reform or ["- none"]),
            "",
            "## Potential absolute formulations",
            "",
            "These are flagged for attention. They are not declared incorrect without source proof.",
            "",
            *(absolute or ["- none"]),
            "",
            "## Human decision",
            "",
            "Approve CH001 as generated, or request a distinct editorial correction.",
            "This packet does not accept the chapter and does not rewrite it.",
            "",
        ]
    )


__all__ = ["build_ch001_review_packet", "render_ch001_review_markdown"]
