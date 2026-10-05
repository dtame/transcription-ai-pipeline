"""
Synthetic offline scenarios.

These are controlled fixtures. They are not Terra validations and they
are not a generated chapter of the pastoral corpus.
"""

from __future__ import annotations

from typing import Any

from app.book_editorial_alignment_4b216.constants import (
    HISTORICAL_H11_STATUS,
    HISTORICAL_SEMANTIC_CONTRACT,
    PHASE,
)
from app.book_editorial_alignment_4b216.coverage import assess_coverage
from app.book_editorial_alignment_4b216.human_resolution import (
    DECISION_CONFIRM_FALSE_REJECTION,
    DECISION_CONFIRM_INVENTION,
    DECISION_MAINTAIN_BLOCK,
    build_resolution,
)
from app.book_editorial_alignment_4b216.policy import allowed_ids, forbidden_ids
from app.book_semantic_gate_4b28.constants import H11_HUMAN_LABEL
from app.file_utils import content_hash

_SOURCE = (
    "Prayer is a conversation, and the speaker said it helps when a person is tired."
)
_NUANCE = "The help is described as refreshment, not as a guarantee of victory."
_RESERVATION = "The speaker was unsure whether the verse was Isaiah 26 or Isaiah 28."
_PEDAGOGICAL = "Prayer is a conversation. Prayer is a conversation, said again so the hearer would remember."
_ACCIDENTAL = "Prayer is a conversation. Prayer is a conversation."


def _scenario(**kwargs: Any) -> dict[str, Any]:
    kwargs["simulated"] = True
    kwargs["not_a_terra_validation"] = True
    kwargs["not_a_generated_chapter"] = True
    return kwargs


def scenario_catalog() -> list[dict[str, Any]]:
    return [
        _scenario(
            id="S01",
            title="Legitimate grammatical correction",
            transformation="grammatical_correction",
            expected="ALLOW",
            sources=[{"id": "IDEA-S01", "kind": "idea", "text": "Prayer are a conversation."}],
            prose="Prayer is a conversation.",
            metadata_ids=["IDEA-S01"],
            must_appear=["conversation"],
            must_not_appear=[],
        ),
        _scenario(
            id="S02",
            title="Light reformulation",
            transformation="light_reformulation",
            expected="ALLOW",
            sources=[
                {
                    "id": "IDEA-S02",
                    "kind": "idea",
                    "text": "Prayer is a conversation with God.",
                }
            ],
            prose="Prayer is a conversation with God.",
            metadata_ids=["IDEA-S02"],
            must_appear=["conversation"],
            must_not_appear=["guarantee"],
        ),
        _scenario(
            id="S03",
            title="Faithful thematic reorganization",
            transformation="thematic_reorganization",
            expected="ALLOW",
            sources=[
                {
                    "id": "IDEA-S03A",
                    "kind": "idea",
                    "text": "Prayer is a conversation.",
                },
                {
                    "id": "IDEA-S03B",
                    "kind": "idea",
                    "text": "Another teaching about prayer says it can refresh a tired person.",
                },
            ],
            prose=(
                "Prayer is a conversation. Another teaching about prayer says "
                "it can refresh a tired person."
            ),
            metadata_ids=["IDEA-S03A", "IDEA-S03B"],
            must_appear=["conversation", "refresh"],
            must_not_appear=["therefore", "causes"],
        ),
        _scenario(
            id="S04",
            title="Fusion of redundant passages",
            transformation="controlled_redundant_fusion",
            expected="ALLOW",
            sources=[
                {
                    "id": "IDEA-S04",
                    "kind": "idea",
                    "text": "Prayer is a conversation. Prayer is a conversation.",
                }
            ],
            prose="Prayer is a conversation.",
            metadata_ids=["IDEA-S04"],
            must_appear=["conversation"],
            must_not_appear=["victory"],
        ),
        _scenario(
            id="S05",
            title="Nuance conserved",
            transformation="light_reformulation",
            expected="ALLOW",
            sources=[{"id": "IDEA-S05", "kind": "reasoning", "text": _NUANCE}],
            prose=_NUANCE,
            metadata_ids=["IDEA-S05"],
            must_appear=["refreshment", "guarantee"],
            must_not_appear=[],
        ),
        _scenario(
            id="S06",
            title="Reservation conserved",
            transformation="light_reformulation",
            expected="ALLOW",
            sources=[{"id": "UNC-S06", "kind": "reservation", "text": _RESERVATION}],
            prose=_RESERVATION,
            metadata_ids=["UNC-S06"],
            must_appear=["unsure", "Isaiah"],
            must_not_appear=[],
        ),
        _scenario(
            id="S07",
            title="Pedagogical repetition conserved",
            transformation="light_reformulation",
            expected="ALLOW",
            sources=[{"id": "IDEA-S07", "kind": "idea", "text": _PEDAGOGICAL}],
            prose=_PEDAGOGICAL,
            metadata_ids=["IDEA-S07"],
            must_appear=["remember"],
            must_not_appear=[],
        ),
        _scenario(
            id="S08",
            title="Accidental repetition removed",
            transformation="accidental_repetition_removal",
            expected="ALLOW",
            sources=[{"id": "IDEA-S08", "kind": "idea", "text": _ACCIDENTAL}],
            prose="Prayer is a conversation.",
            metadata_ids=["IDEA-S08"],
            must_appear=["conversation"],
            must_not_appear=["victory"],
        ),
        _scenario(
            id="S09",
            title="Neutral transition",
            transformation="neutral_transition",
            expected="ALLOW",
            sources=[
                {"id": "IDEA-S09", "kind": "idea", "text": "Prayer is a conversation."}
            ],
            prose=(
                "Prayer is a conversation. Another aspect of this teaching concerns prayer."
            ),
            metadata_ids=["IDEA-S09"],
            must_appear=["Another aspect of this teaching concerns prayer."],
            must_not_appear=["necessarily proves"],
        ),
        _scenario(
            id="S10",
            title="Invented causality",
            transformation="new_causality",
            expected="REJECT",
            sources=[
                {"id": "IDEA-S10", "kind": "idea", "text": "Prayer is a conversation."}
            ],
            prose=(
                "Prayer is a conversation. This necessarily proves that prayer "
                "is the cause of every spiritual victory."
            ),
            metadata_ids=["IDEA-S10"],
            must_appear=["cause of every spiritual victory"],
            must_not_appear=[],
            invented_marker="cause of every spiritual victory",
        ),
        _scenario(
            id="S11",
            title="New implication",
            transformation="new_implication",
            expected="REJECT",
            sources=[
                {"id": "IDEA-S11", "kind": "idea", "text": "Prayer is a conversation."}
            ],
            prose=(
                "Prayer is a conversation, which means that every listener "
                "receives the same answer."
            ),
            metadata_ids=["IDEA-S11"],
            must_appear=["receives the same answer"],
            must_not_appear=[],
            invented_marker="receives the same answer",
        ),
        _scenario(
            id="S12",
            title="Universal guarantee",
            transformation="new_guarantee",
            expected="REJECT",
            sources=[
                {"id": "IDEA-S12", "kind": "idea", "text": "Prayer can refresh a tired person."}
            ],
            prose="Prayer always guarantees victory in every circumstance.",
            metadata_ids=["IDEA-S12"],
            must_appear=["always guarantees victory"],
            must_not_appear=[],
            invented_marker="always guarantees victory",
        ),
        _scenario(
            id="S13",
            title="Invented example",
            transformation="new_example",
            expected="REJECT",
            sources=[
                {"id": "IDEA-S13", "kind": "idea", "text": "Prayer is a conversation."}
            ],
            prose=(
                "Prayer is a conversation. For example, a merchant in a distant "
                "city prayed once and his shop was saved that night."
            ),
            metadata_ids=["IDEA-S13"],
            must_appear=["merchant in a distant city"],
            must_not_appear=[],
            invented_marker="merchant in a distant city",
        ),
        _scenario(
            id="S14",
            title="Invented reference",
            transformation="new_reference",
            expected="REJECT",
            sources=[
                {"id": "IDEA-S14", "kind": "idea", "text": "Prayer is a conversation."}
            ],
            prose="Prayer is a conversation, as Romans 8:28 demonstrates.",
            metadata_ids=["IDEA-S14"],
            must_appear=["Romans 8:28"],
            must_not_appear=[],
            invented_marker="Romans 8:28",
        ),
        _scenario(
            id="S15",
            title="Omission of an idea",
            transformation="important_idea_omitted",
            expected="REJECT",
            sources=[
                {"id": "IDEA-S15A", "kind": "idea", "text": "Prayer is a conversation."},
                {
                    "id": "IDEA-S15B",
                    "kind": "idea",
                    "text": "Fasting has a different purpose from prayer.",
                },
            ],
            prose="Prayer is a conversation.",
            metadata_ids=["IDEA-S15A", "IDEA-S15B"],
            must_appear=["conversation"],
            must_not_appear=["Fasting has a different purpose"],
            omitted_id="IDEA-S15B",
        ),
        _scenario(
            id="S16",
            title="Omission of a condition",
            transformation="important_reservation_removed",
            expected="REJECT",
            sources=[
                {
                    "id": "IDEA-S16",
                    "kind": "idea",
                    "text": "Prayer refreshes a tired person.",
                },
                {"id": "UNC-S16", "kind": "reservation", "text": _RESERVATION},
            ],
            prose="Prayer refreshes a tired person.",
            metadata_ids=["IDEA-S16", "UNC-S16"],
            must_appear=["refreshes"],
            must_not_appear=["unsure whether the verse"],
            omitted_id="UNC-S16",
        ),
        _scenario(
            id="S17",
            title="Incorrect attribution",
            transformation="incorrect_attribution",
            expected="REJECT",
            sources=[
                {
                    "id": "IDEA-S17",
                    "kind": "idea",
                    "text": "One speaker said prayer is a conversation. A second speaker disagreed.",
                }
            ],
            prose="Both speakers agreed that prayer is a conversation.",
            metadata_ids=["IDEA-S17"],
            must_appear=["Both speakers agreed"],
            must_not_appear=[],
            invented_marker="Both speakers agreed",
        ),
        _scenario(
            id="S18",
            title="Fusion of incompatible reasonings",
            transformation="incompatible_reasoning_fusion",
            expected="REJECT",
            sources=[
                {
                    "id": "IDEA-S18A",
                    "kind": "reasoning",
                    "text": "The speaker said healing is already accomplished.",
                },
                {
                    "id": "IDEA-S18B",
                    "kind": "reasoning",
                    "text": "The same recording also said that sometimes it does not happen.",
                },
            ],
            prose=(
                "Healing is already accomplished, and therefore it always happens."
            ),
            metadata_ids=["IDEA-S18A", "IDEA-S18B"],
            must_appear=["always happens"],
            must_not_appear=["sometimes it does not happen"],
            invented_marker="always happens",
            cited_rules=["B", "C"],
        ),
        _scenario(
            id="S19",
            title="Simulated historical false rejection",
            transformation="simulated_false_rejection",
            expected="HUMAN_REVIEW",
            sources=[
                {
                    "id": "IDEA-S19",
                    "kind": "idea",
                    "text": "Prayer is a conversation.",
                }
            ],
            prose="Prayer is a conversation.",
            metadata_ids=["IDEA-S19"],
            must_appear=["conversation"],
            must_not_appear=[],
            terra_verdict="UNSUPPORTED",
            terra_reasons=["NEW_CONCLUSION"],
            human_label_must_remain=H11_HUMAN_LABEL,
            historical_status_must_remain=HISTORICAL_H11_STATUS,
            automatic_conversion_forbidden=True,
            models_historical_pattern=(
                "Synthetic stand-in for the documented h11 pattern in which "
                "some clauses were rejected while a universal guarantee was "
                "rightly rejected. This fixture does not replay Terra and "
                "does not change the historical h11 label."
            ),
        ),
        _scenario(
            id="S20",
            title="Documented human review",
            transformation="human_resolution_recorded",
            expected="HUMAN_REVIEW",
            sources=[
                {
                    "id": "IDEA-S20",
                    "kind": "idea",
                    "text": "Prayer is a conversation.",
                }
            ],
            prose="Prayer is a conversation.",
            metadata_ids=["IDEA-S20"],
            must_appear=["conversation"],
            must_not_appear=[],
            terra_verdict="UNSUPPORTED",
            terra_reasons=["NEW_CONCLUSION"],
            human_decision=DECISION_CONFIRM_FALSE_REJECTION,
            justification=(
                "The sentence repeats the supplied source and adds no fact, "
                "cause, implication, or guarantee."
            ),
        ),
    ]


def _source_blob(scenario: dict[str, Any]) -> str:
    return "\n".join(str(item.get("text") or "") for item in scenario["sources"])


def evaluate_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    prose = str(scenario.get("prose") or "")
    sources = _source_blob(scenario)
    missing_required = [
        phrase for phrase in scenario.get("must_appear") or [] if phrase not in prose
    ]
    unexpected = [
        phrase for phrase in scenario.get("must_not_appear") or [] if phrase and phrase in prose
    ]
    invented = str(scenario.get("invented_marker") or "")
    invented_ok = True
    if invented:
        invented_ok = invented in prose and invented not in sources
    coverage = assess_coverage(
        scenario["sources"],
        prose,
        scenario.get("metadata_ids") or [],
    )
    transformation = str(scenario.get("transformation") or "")
    expected = scenario.get("expected")
    policy_known = transformation in set(allowed_ids()) or transformation in {
        "important_idea_omitted",
        "incompatible_reasoning_fusion",
        "simulated_false_rejection",
        "human_resolution_recorded",
    } or transformation in set(forbidden_ids())
    resolution = None
    terra_unchanged = True
    publication_blocked = True
    if expected == "HUMAN_REVIEW":
        terra_verdict = str(scenario.get("terra_verdict") or "")
        terra_unchanged = terra_verdict == "UNSUPPORTED"
        if scenario.get("human_decision"):
            resolution = build_resolution(
                {
                    "exact_text": prose,
                    "unit_id": scenario["id"],
                    "terra_verdict": terra_verdict,
                    "reasons": scenario.get("terra_reasons") or [],
                    "evidence": [item["id"] for item in scenario["sources"]],
                    "sources": [item["text"] for item in scenario["sources"]],
                    "contract_version": HISTORICAL_SEMANTIC_CONTRACT,
                    "hashes": {"prose_sha256": content_hash(prose)},
                    "human_decision": scenario["human_decision"],
                    "justification": scenario.get("justification") or "",
                }
            )
            publication_blocked = resolution["publication_authorized"] is False
            terra_unchanged = resolution["terra_verdict"] == terra_verdict
        label_ok = scenario.get("human_label_must_remain", H11_HUMAN_LABEL) == H11_HUMAN_LABEL
        status_ok = (
            scenario.get("historical_status_must_remain", HISTORICAL_H11_STATUS)
            == HISTORICAL_H11_STATUS
        )
        passed = (
            not missing_required
            and not unexpected
            and terra_unchanged
            and publication_blocked
            and label_ok
            and status_ok
            and scenario.get("automatic_conversion_forbidden", True) is True
        )
    elif expected == "ALLOW":
        passed = (
            transformation in set(allowed_ids())
            and not missing_required
            and not unexpected
            and coverage["pass"]
            and not invented
        )
    else:
        omitted = scenario.get("omitted_id")
        omission_detected = True
        if omitted:
            omission_detected = omitted in coverage["important_missing"]
        passed = (
            transformation in set(forbidden_ids())
            or transformation in {"important_idea_omitted", "incompatible_reasoning_fusion"}
        ) and invented_ok and omission_detected and not missing_required and not unexpected
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "transformation": transformation,
        "expected": expected,
        "policy_known": policy_known,
        "passed": passed,
        "missing_required_phrases": missing_required,
        "unexpected_phrases": unexpected,
        "invented_marker_proven_absent_from_sources": invented_ok if invented else None,
        "coverage_pass": coverage["pass"],
        "coverage_missing": coverage["important_missing"],
        "identifier_only_is_not_coverage": any(
            row["status"] == "IDENTIFIER_ONLY" for row in coverage["units"]
        ),
        "terra_verdict_unchanged": terra_unchanged,
        "publication_authorized": False if publication_blocked else True,
        "human_resolution": resolution,
        "simulated": True,
        "not_a_terra_validation": True,
        "not_a_generated_chapter": True,
    }


def evaluate_offline_scenarios() -> dict[str, Any]:
    rows = [evaluate_scenario(item) for item in scenario_catalog()]
    failed = [row["id"] for row in rows if not row["passed"]]
    return {
        "phase": PHASE,
        "simulated": True,
        "not_a_terra_validation": True,
        "not_a_sonnet_validation": True,
        "not_presented_as_real_terra_quality": True,
        "scenario_count": len(rows),
        "passed": len(rows) - len(failed),
        "failed": len(failed),
        "failed_ids": failed,
        "historical_h11_status": HISTORICAL_H11_STATUS,
        "historical_h11_human_label": H11_HUMAN_LABEL,
        "historical_labels_modified": False,
        "automatic_unsupported_to_supported": False,
        "automatic_block_to_pass": False,
        "scenarios": rows,
        "decisions_available": [
            DECISION_CONFIRM_INVENTION,
            DECISION_CONFIRM_FALSE_REJECTION,
            DECISION_MAINTAIN_BLOCK,
        ],
        "secrets_included": False,
    }


__all__ = [
    "evaluate_offline_scenarios",
    "evaluate_scenario",
    "scenario_catalog",
]
