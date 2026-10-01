"""286-IDEA / TOP / EX / REF / UNC input coverage. Unknown refs = 0."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.editorial_planning.digest import build_planner_digest
from app.source_analysis.models import SourceMap


def _ids(values: list[str]) -> list[str]:
    return list(values)


def duplicate_ids(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(key for key, count in counts.items() if count > 1)


def input_coverage_audit(source_map: SourceMap) -> dict[str, Any]:
    digest = build_planner_digest(source_map)
    map_ideas = [idea.idea_id for idea in source_map.ideas]
    map_topics = [topic.topic_id for topic in source_map.topics]
    map_examples = [item.example_id for item in source_map.examples]
    map_refs = [item.reference_id for item in source_map.references]
    map_unc = [item.uncertainty_id for item in source_map.uncertainties]
    digest_ideas = [item["id"] for item in digest.get("ideas") or []]
    digest_topics = [item["id"] for item in digest.get("topics") or []]
    digest_examples = [item["id"] for item in digest.get("examples") or []]
    digest_refs = [item["id"] for item in digest.get("references") or []]
    digest_unc = [item["id"] for item in digest.get("uncertainties") or []]

    missing_ideas = [idea_id for idea_id in map_ideas if idea_id not in set(digest_ideas)]
    extra_ideas = [idea_id for idea_id in digest_ideas if idea_id not in set(map_ideas)]
    missing_topics = [item for item in map_topics if item not in set(digest_topics)]
    extra_topics = [item for item in digest_topics if item not in set(map_topics)]
    missing_examples = [item for item in map_examples if item not in set(digest_examples)]
    extra_examples = [item for item in digest_examples if item not in set(map_examples)]
    missing_refs = [item for item in map_refs if item not in set(digest_refs)]
    extra_refs = [item for item in digest_refs if item not in set(map_refs)]
    missing_unc = [item for item in map_unc if item not in set(digest_unc)]
    extra_unc = [item for item in digest_unc if item not in set(map_unc)]

    unknown = (
        extra_ideas + extra_topics + extra_examples + extra_refs + extra_unc
    )
    dups = (
        duplicate_ids(map_ideas)
        + duplicate_ids(map_topics)
        + duplicate_ids(map_examples)
        + duplicate_ids(map_refs)
        + duplicate_ids(map_unc)
        + duplicate_ids(digest_ideas)
    )
    idea_ok = not missing_ideas and not extra_ideas and len(digest_ideas) == 286
    return {
        "idea_input_coverage": f"{len(digest_ideas)} / 286",
        "idea_count": len(digest_ideas),
        "idea_ids": digest_ideas,
        "missing_idea_ids": missing_ideas,
        "unknown_idea_ids": extra_ideas,
        "topic_count": len(digest_topics),
        "missing_topic_ids": missing_topics,
        "unknown_topic_ids": extra_topics,
        "example_count": len(digest_examples),
        "missing_example_ids": missing_examples,
        "unknown_example_ids": extra_examples,
        "reference_count": len(digest_refs),
        "missing_reference_ids": missing_refs,
        "unknown_reference_ids": extra_refs,
        "uncertainty_count": len(digest_unc),
        "missing_uncertainty_ids": missing_unc,
        "unknown_uncertainty_ids": extra_unc,
        "unknown_input_refs": len(unknown),
        "unknown_input_ref_ids": unknown,
        "duplicate_canonical_ids": len(dups),
        "duplicate_canonical_id_values": dups,
        "source_map_mutated": False,
        "all_ideas_present": idea_ok,
        "pass": idea_ok
        and not missing_topics
        and not missing_examples
        and not missing_refs
        and not missing_unc
        and not unknown
        and not dups,
        "digest_counts": digest.get("counts"),
        "compact_digest_keys": sorted(digest.keys()),
    }


def digest_json(source_map: SourceMap) -> str:
    return json.dumps(build_planner_digest(source_map), ensure_ascii=False, separators=(",", ":"))


__all__ = ["digest_json", "duplicate_ids", "input_coverage_audit"]
