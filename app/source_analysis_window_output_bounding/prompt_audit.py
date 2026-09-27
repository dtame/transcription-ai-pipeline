"""Audit de granularité de window-analysis-1.0. Ne cite pas le prompt en entier."""

from __future__ import annotations

from typing import Any

from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt_v10,
    build_window_user_prompt_v10,
)
from app.source_analysis.window_fixtures import make_transcript, window_for


def _classify(name: str, status: str, evidence: str) -> dict[str, str]:
    return {"dimension": name, "status": status, "evidence": evidence}


def audit_window_analysis_10() -> dict[str, Any]:
    system = build_window_system_prompt_v10("en")
    transcript = make_transcript(("Faith changes the crossing.",))
    user = build_window_user_prompt_v10(transcript, window_for(transcript))
    combined = system + "\n" + user
    return {
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        "system_chars": len(system),
        "dimensions": [
            _classify(
                "topic_granularity",
                "UNBOUNDED",
                "No TOPIC count target or ceiling.",
            ),
            _classify(
                "idea_granularity",
                "AMBIGUOUS",
                "Task says one record per really distinct unit; no numeric budget.",
            ),
            _classify(
                "idea_completeness",
                "QUALITATIVELY_BOUNDED",
                "Fidelity forbids invention; does not cap how many true ideas.",
            ),
            _classify(
                "relations",
                "UNBOUNDED",
                "Allowed to relate; no ban on exhaustive pairwise graphs.",
            ),
            _classify(
                "examples",
                "QUALITATIVELY_BOUNDED",
                "May legitimately have none; no maximum.",
            ),
            _classify(
                "references",
                "QUALITATIVELY_BOUNDED",
                "May legitimately have none; no maximum.",
            ),
            _classify(
                "uncertainties",
                "QUALITATIVELY_BOUNDED",
                "Boundary cuts should be signaled; no grouping/count cap.",
            ),
            _classify(
                "repetitions",
                "UNBOUNDED",
                "No instruction to group repeated occurrences.",
            ),
            _classify(
                "voice",
                "QUALITATIVELY_BOUNDED",
                "Record-field contract: one VOICE record per list item / scalar.",
            ),
            _classify(
                "intent",
                "QUALITATIVELY_BOUNDED",
                "Window candidates only; INTENT_KIND may repeat per label.",
            ),
            _classify(
                "audience",
                "QUALITATIVELY_BOUNDED",
                "Window candidates only; AUDIENCE_KIND may repeat per label.",
            ),
            _classify(
                "coverage",
                "AMBIGUOUS",
                "Analyze this window; no rule that every SRC must appear.",
            ),
            _classify(
                "source_traceability",
                "EXPLICITLY_BOUNDED",
                "Substantive records must cite real owned SRC; no invented ranges.",
            ),
            _classify(
                "completeness",
                "AMBIGUOUS",
                "Sobriety asked; no overflow signal if capacity is insufficient.",
            ),
            _classify(
                "duplication",
                "AMBIGUOUS",
                "Distinct unit language; no explicit same-idea / multi-SRC grouping.",
            ),
            _classify(
                "semantic_grouping",
                "UNBOUNDED",
                "No instruction that one IDEA may carry several SRC statements.",
            ),
            _classify(
                "record_count",
                "UNBOUNDED",
                "records[] has no maxItems; only max_output bounds the list.",
            ),
        ],
        "unbounded": [
            "topic_granularity",
            "relations",
            "repetitions",
            "semantic_grouping",
            "record_count",
        ],
        "combinatorial_relations_possible": True,
        "duplicate_ideas_from_restatement_possible": True,
        "explicit_record_count_bound": False,
        "overflow_signal": False,
        "mentions_max_output": "32000" not in combined and "max_output" not in combined,
    }


def audit_transport_kinds() -> list[dict[str, Any]]:
    rows = [
        ("TOPIC", "topics[]", True, True, False, False, True),
        ("IDEA", "ideas[]", True, True, False, False, True),
        ("RELATION", "idea.relationships", True, False, False, True, False),
        ("EXAMPLE", "examples[]", True, True, False, True, True),
        ("REFERENCE", "references[]", True, True, False, False, True),
        ("UNCERTAINTY", "uncertainties[]", True, True, False, False, True),
        ("REPETITION", "repetitions[]", True, True, False, True, True),
        ("VOICE", "author_voice_profile", True, False, True, False, True),
        ("INTENT_KIND", "author_intent.kinds", False, False, True, False, False),
        ("AUDIENCE_KIND", "target_audience.kinds", False, False, True, False, False),
    ]
    return [
        {
            "kind": kind,
            "canonical_destination": dest,
            "potentially_many": many,
            "substantive": subst,
            "metadata_evidence": meta,
            "relation_or_evidence": rel,
            "semantic_grouping_possible": group,
        }
        for kind, dest, many, subst, meta, rel, group in rows
    ]


__all__ = ["audit_transport_kinds", "audit_window_analysis_10"]
