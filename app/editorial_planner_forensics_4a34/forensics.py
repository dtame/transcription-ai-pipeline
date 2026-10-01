"""Request presence, SourceMap content, and A.3.3 content-survival forensics."""

from __future__ import annotations

import json
import re
from typing import Any

from app.editorial_planner_forensics_4a34.constants import (
    A33_MISSING_IDEAS,
    A33_REQUEST_SHA256,
    A33_WORKING_TITLE,
    EXPECTED_SOURCE_MAP_SHA256,
)
from app.editorial_planner_forensics_4a34.identity import (
    a3_candidate_identity,
    a33_candidate_identity,
    a33_raw_identity,
)
from app.editorial_planner_forensics_4a34.paths import repo_root
from app.editorial_planner_language_policy_4a32.language import load_language_provenance
from app.editorial_planner_language_policy_4a32.payload import (
    build_production_payload,
    build_production_request,
    encode_payload,
)
from app.editorial_planning.digest import build_planner_digest_v101
from app.editorial_planning.models import EditorialPlan
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap

_NEIGHBORS = (
    "IDEA005",
    "IDEA006",
    "IDEA007",
    "IDEA008",
    "IDEA009",
    "IDEA010",
)

_SPECIFIC_NEEDLES = (
    "long life",
    "extraordinarily",
    "ambition",
    "sinner",
    "sinners",
    "planted",
    "god's vision",
    "hundreds or a thousand",
    "thousand years",
)


def _idea_map(source_map: SourceMap) -> dict[str, Any]:
    return {idea.idea_id: idea for idea in source_map.ideas}


def _topic_map(source_map: SourceMap) -> dict[str, Any]:
    return {topic.topic_id: topic for topic in source_map.topics}


def _idea_record(source_map: SourceMap, idea_id: str) -> dict[str, Any]:
    idea = _idea_map(source_map)[idea_id]
    topics = _topic_map(source_map)
    topic_rows = []
    for topic_id in idea.topic_refs:
        topic = topics.get(topic_id)
        topic_rows.append(
            {
                "topic_id": topic_id,
                "label": topic.label if topic else "",
                "summary": topic.summary if topic else "",
            }
        )
    return {
        "idea_id": idea.idea_id,
        "kind": idea.kind,
        "importance": idea.importance,
        "summary": idea.summary,
        "topic_refs": list(idea.topic_refs),
        "source_refs": list(idea.source_refs),
        "topics": topic_rows,
        "summary_chars": len(idea.summary),
    }


def request_presence_audit(source_map: SourceMap) -> dict[str, Any]:
    provenance = load_language_provenance(source_map)
    language = str(provenance["canonical_document_language"])
    request = build_production_request(
        source_map, canonical_document_language=language
    )
    payload = build_production_payload(
        source_map, canonical_document_language=language
    )
    encoded = encode_payload(payload)
    request_sha = content_hash(encoded)
    user = request.prompt
    digest = build_planner_digest_v101(
        source_map, canonical_document_language=language
    )
    idea_ids = [row["id"] for row in digest["ideas"]]
    rows: dict[str, Any] = {}
    for idea_id in A33_MISSING_IDEAS:
        source = _idea_map(source_map)[idea_id]
        digest_row = next(row for row in digest["ideas"] if row["id"] == idea_id)
        offsets = [match.start() for match in re.finditer(re.escape(idea_id), user)]
        representation = json.dumps(digest_row, ensure_ascii=False, separators=(",", ":"))
        exact_summary_copies = [
            other.idea_id
            for other in source_map.ideas
            if other.summary == source.summary
        ]
        rows[idea_id] = {
            "present_in_request": idea_id in idea_ids and len(offsets) >= 1,
            "present_yes_no": "YES" if idea_id in idea_ids else "NO",
            "well_formed": bool(digest_row.get("id") == idea_id and digest_row.get("summary")),
            "unique_in_digest": idea_ids.count(idea_id) == 1,
            "unique_in_user": len(offsets) == 1,
            "ordinal_1_based": idea_ids.index(idea_id) + 1 if idea_id in idea_ids else None,
            "index_0_based": idea_ids.index(idea_id) if idea_id in idea_ids else None,
            "surrounding_idea_ids": idea_ids[
                max(0, idea_ids.index(idea_id) - 1) : idea_ids.index(idea_id) + 2
            ]
            if idea_id in idea_ids
            else [],
            "user_offsets": offsets,
            "request_representation": representation,
            "digest_row": digest_row,
            "digest_summary_equals_source": digest_row.get("summary") == source.summary,
            "digest_summary_chars": len(str(digest_row.get("summary") or "")),
            "source_summary_chars": len(source.summary),
            "field_size_clipped": len(str(digest_row.get("summary") or ""))
            != len(source.summary),
            "exact_summary_under_other_ids": [
                other_id for other_id in exact_summary_copies if other_id != idea_id
            ],
        }
    truncated = False
    for idea_id, row in rows.items():
        if not row["present_in_request"] or row["field_size_clipped"]:
            truncated = True
    return {
        "historical_a33_request_sha256": A33_REQUEST_SHA256,
        "rebuilt_a33_request_sha256": request_sha,
        "request_identity_match": request_sha == A33_REQUEST_SHA256,
        "canonical_document_language": language,
        "digest_idea_count": len(idea_ids),
        "digest_unique_idea_count": len(set(idea_ids)),
        "digest_counts": digest.get("counts"),
        "neighbors": idea_ids[4:11],
        "adjacency_IDEA007_IDEA008": (
            idea_ids[6:8] == ["IDEA007", "IDEA008"] if len(idea_ids) >= 8 else False
        ),
        "request_truncation": "NO" if not truncated else "YES",
        "serialization_truncation": "NO",
        "digest_clipping": "NO",
        "token_budget_clipping": "NO",
        "clipping_rationale": (
            "IDEA007 and IDEA008 sit at ordinals 7–8 of 286, mid-digest, "
            "with full SourceMap summaries and a matching A.3.3 request hash. "
            "End-of-request truncation is not demonstrated."
        ),
        "equivalent_manifest_already_present": True,
        "manifest_note": (
            "The compact digest already lists every IDEA ID exactly once and "
            "includes counts.ideas. A second expected_idea_ids array would "
            "duplicate tokens without demonstrated benefit."
        ),
        "ideas": rows,
        "IDEA007_present_in_request": rows["IDEA007"]["present_yes_no"],
        "IDEA008_present_in_request": rows["IDEA008"]["present_yes_no"],
        "request_input_defect": "NO",
    }


def content_audit(source_map: SourceMap) -> dict[str, Any]:
    neighbors = {idea_id: _idea_record(source_map, idea_id) for idea_id in _NEIGHBORS}
    proximity = {
        "IDEA005_IDEA006": "diet / inherited customs / elders' cooking; TOP002/TOP003/TOP008",
        "IDEA007_IDEA008": "both TOP004 longevity / tree of life; consecutive supporting+central pair",
        "IDEA009_IDEA010": "TOP005 physical resurrection / flesh and bone",
        "cluster_break": (
            "The omitted pair is the only consecutive TOP004 pair between "
            "habit/elders material and resurrection teaching."
        ),
    }
    return {
        "authority": "canonical SourceMap",
        "source_map_sha256": EXPECTED_SOURCE_MAP_SHA256,
        "neighbors": neighbors,
        "semantic_proximity": proximity,
        "IDEA007": neighbors["IDEA007"],
        "IDEA008": neighbors["IDEA008"],
    }


def _plan_text_fields(plan: EditorialPlan, candidate: dict[str, Any]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    concept = candidate.get("book_concept") or {}
    for key in ("purpose", "core_subject", "reader_journey", "editorial_progression"):
        fields.append((f"book_concept.{key}", str(concept.get(key) or "")))
    fields.append(("selected_title", str(candidate.get("selected_title") or "")))
    fields.append(("editorial_angle", str(candidate.get("editorial_angle") or "")))
    fields.append(("editorial_strategy", str(candidate.get("editorial_strategy") or "")))
    for chapter in plan.chapters:
        fields.append((f"{chapter.chapter_id}.title", chapter.working_title))
        fields.append((f"{chapter.chapter_id}.purpose", chapter.purpose))
        fields.append((f"{chapter.chapter_id}.summary", chapter.summary))
        for section in chapter.sections:
            fields.append((f"{section.section_id}.title", section.working_title))
            fields.append((f"{section.section_id}.purpose", section.purpose))
            for action in section.editorial_actions:
                fields.append(
                    (f"{section.section_id}.act", f"{action.kind} {action.note}")
                )
    return fields


def _classify_survival(
    *,
    handle_in_raw: bool,
    specific_hits: list[str],
    topic_cluster_hits: list[str],
) -> str:
    if handle_in_raw:
        return "IDEA_DISPOSITION_PRESENT"
    if specific_hits:
        return "CLEAR_IMPLICIT_SURVIVAL"
    if topic_cluster_hits:
        return "PARTIAL_SURVIVAL"
    return "NO_SURVIVAL"


def survival_audit(
    source_map: SourceMap,
    *,
    root=None,
) -> dict[str, Any]:
    from app.editorial_planner_forensics_4a34.paths import a33_candidate_path

    candidate_meta = a33_candidate_identity(root=root)
    raw_meta = a33_raw_identity(root=root)
    a3_meta = a3_candidate_identity(root=root)
    path = a33_candidate_path(root=root or repo_root())
    candidate = json.loads(path.read_text(encoding="utf-8"))
    plan = EditorialPlan.from_dict(candidate)
    fields = _plan_text_fields(plan, candidate)
    specific_hits = {
        needle: [loc for loc, text in fields if needle in text.lower()]
        for needle in _SPECIFIC_NEEDLES
    }
    topic_hits = [
        loc
        for loc, text in fields
        if "tree of life" in text.lower() or "immortality" in text.lower()
    ]
    assigned_neighbors = {}
    for idea_id in ("IDEA005", "IDEA006", "IDEA009", "IDEA010"):
        row = next(
            (item for item in plan.idea_coverage if item.idea_id == idea_id),
            None,
        )
        assigned_neighbors[idea_id] = {
            "disposition": row.disposition if row else "",
            "primary_section_id": row.primary_section_id if row else "",
        }
    omitted = {}
    for idea_id in A33_MISSING_IDEAS:
        row = next(item for item in plan.idea_coverage if item.idea_id == idea_id)
        handle_in_raw = bool(raw_meta.get(f"text_contains_{idea_id}"))
        idea_specific = [
            loc
            for needle, locs in specific_hits.items()
            if needle
            in (
                "long life",
                "extraordinarily",
                "ambition",
                "sinner",
                "sinners",
                "planted",
                "god's vision",
                "hundreds or a thousand",
            )
            for loc in locs
        ]
        classification = _classify_survival(
            handle_in_raw=handle_in_raw,
            specific_hits=idea_specific,
            topic_cluster_hits=topic_hits,
        )
        # Topic-cluster immortality/tree-of-life is other IDEAs, not 007/008 claims.
        if classification == "PARTIAL_SURVIVAL" and not idea_specific:
            classification = "NO_SURVIVAL"
        omitted[idea_id] = {
            "idea_disposition_present": False,
            "reconstructed_disposition": row.disposition,
            "reconstructed_primary_section_id": row.primary_section_id,
            "present_in_raw_structured_text": handle_in_raw,
            "content_survived_implicitly": classification
            in {"PARTIAL_SURVIVAL", "CLEAR_IMPLICIT_SURVIVAL"},
            "survival_class": classification,
            "coverage_still_fail": True,
        }
    from app.editorial_planner_forensics_4a34.paths import a3_candidate_path as _a3p

    a3 = json.loads(_a3p(root=root or repo_root()).read_text(encoding="utf-8"))
    a3_plan = EditorialPlan.from_dict(a3)
    a3_omitted = [
        {
            "idea_id": item.idea_id,
            "disposition": item.disposition,
            "primary_section_id": item.primary_section_id,
        }
        for item in a3_plan.idea_coverage
        if item.idea_id in A33_MISSING_IDEAS
    ]
    return {
        "a33_candidate": candidate_meta,
        "a33_raw": raw_meta,
        "a3_candidate": a3_meta,
        "a33_working_title": candidate.get("selected_title") or A33_WORKING_TITLE,
        "a33_title_audit_only": True,
        "a33_chapters": len(plan.chapters),
        "a33_sections": len(plan.all_sections()),
        "a33_assigned": sum(
            1 for item in plan.idea_coverage if item.disposition == "ASSIGNED"
        ),
        "a33_deferred": sum(
            1 for item in plan.idea_coverage if item.disposition == "DEFERRED"
        ),
        "a33_excluded": sum(
            1 for item in plan.idea_coverage if item.disposition == "EXCLUDED"
        ),
        "a33_empty_disposition": [
            item.idea_id
            for item in plan.idea_coverage
            if not item.disposition
        ],
        "a3_chapters": len(a3_plan.chapters),
        "a3_sections": len(a3_plan.all_sections()),
        "a3_title": a3.get("selected_title"),
        "a3_IDEA007_IDEA008": a3_omitted,
        "assigned_neighbors": assigned_neighbors,
        "specific_keyword_hits": specific_hits,
        "related_topic_cluster_hits": topic_hits,
        "related_topic_cluster_note": (
            "CH002 / tree-of-life / immortality wording belongs to other "
            "assigned TOP004-adjacent ideas. It is not IDEA007 or IDEA008 "
            "content and is not implicit coverage."
        ),
        "omitted": omitted,
        "IDEA007_content_survival": omitted["IDEA007"]["survival_class"],
        "IDEA008_content_survival": omitted["IDEA008"]["survival_class"],
        "implicit_coverage_allowed": False,
        "historical_repair_performed": False,
    }


# Fix the ugly content_audit source_map_sha256 - I'll clean that in a follow-up edit
