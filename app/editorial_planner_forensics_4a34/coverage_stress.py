"""FakeAI exhaustive IDEA-accountability stress. 0 provider calls."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.editorial_planning.fixtures import covering_transport, unknown_idea_transport
from app.editorial_planning.models import IdeaDisposition
from app.editorial_planning.pipeline import materialize_plan
from app.editorial_planning.schema import schema_identity
from app.editorial_planning.validator import validate_editorial_plan
from app.source_analysis.models import SourceMap


def _ids() -> tuple[str, str]:
    from app.editorial_planning.prompt import prompt_bundle

    prompt = prompt_bundle()
    schema = schema_identity()
    return prompt["prompt_sha256"], schema["raw_schema_sha256"]


def _materialize(source_map: SourceMap, transport: dict[str, Any]):
    prompt_sha, schema_sha = _ids()
    return materialize_plan(
        transport,
        source_map,
        source_map_sha256="offline-4a34-coverage-stress",
        source_map_bytes=10,
        prompt_sha256=prompt_sha,
        response_schema_sha256=schema_sha,
        source_map_path_value="analysis/source_map.json",
    )


def _omit_ids_transport(source_map: SourceMap, omit_ids: tuple[str, ...]) -> dict[str, Any]:
    omitted = set(omit_ids)
    transport = covering_transport(source_map)
    for chapter in transport.get("chapters") or []:
        for section in chapter.get("sections") or []:
            section["i"] = [
                idea_id for idea_id in section.get("i") or [] if idea_id not in omitted
            ]
    return transport


def _duplicate_disposition_case(source_map: SourceMap) -> tuple[Any, Any]:
    """Reconstruct cannot emit two primary rows; inject a duplicate for the gate."""
    plan, _validation, _digest = _materialize(
        source_map, covering_transport(source_map)
    )
    first = plan.idea_coverage[0]
    duplicate = IdeaDisposition(
        idea_id=first.idea_id,
        disposition="DEFERRED",
        reason="insufficient_support",
        note="injected duplicate primary disposition",
    )
    mutated = replace(plan, idea_coverage=plan.idea_coverage + (duplicate,))
    return mutated, validate_editorial_plan(mutated, source_map)


def run_coverage_stress(source_map: SourceMap) -> dict[str, Any]:
    idea_ids = [idea.idea_id for idea in source_map.ideas]
    last = idea_ids[-1]
    reuse = idea_ids[0]
    omit = ("IDEA007", "IDEA008") if "IDEA007" in idea_ids else tuple(idea_ids[:2])

    scenarios = [
        (
            "286_assigned",
            covering_transport(source_map),
            "PASS",
        ),
        (
            "285_assigned_1_deferred",
            covering_transport(source_map, defer_ids=(last,)),
            "PASS",
        ),
        (
            "285_assigned_1_excluded",
            covering_transport(source_map, exclude_ids=(last,)),
            "PASS",
        ),
        (
            "284_assigned_2_omitted",
            _omit_ids_transport(source_map, omit),
            "FAIL",
        ),
        (
            "unknown_idea",
            unknown_idea_transport(source_map),
            "FAIL",
        ),
        (
            "reuse_plus_primary",
            covering_transport(source_map, reuse_idea=reuse),
            "PASS",
        ),
        (
            "shuffled_complete_coverage",
            covering_transport(source_map, reverse_ideas=True),
            "PASS",
        ),
    ]
    rows: list[dict[str, Any]] = []
    failures = 0
    for name, transport, expected in scenarios:
        plan, validation, _digest = _materialize(source_map, transport)
        status = validation.status
        ok = (expected == "FAIL" and status == "FAIL") or (
            expected == "PASS" and status != "FAIL"
        )
        if not ok:
            failures += 1
        assigned = sum(1 for item in plan.idea_coverage if item.disposition == "ASSIGNED")
        deferred = sum(1 for item in plan.idea_coverage if item.disposition == "DEFERRED")
        excluded = sum(1 for item in plan.idea_coverage if item.disposition == "EXCLUDED")
        empty = [
            item.idea_id for item in plan.idea_coverage if not item.disposition
        ]
        rows.append(
            {
                "scenario": name,
                "expected": expected,
                "validation_status": status,
                "pass": ok,
                "assigned": assigned,
                "deferred": deferred,
                "excluded": excluded,
                "empty_disposition_ids": empty,
                "errors": list(validation.errors)[:8],
            }
        )
    dup_plan, dup_validation = _duplicate_disposition_case(source_map)
    dup_ok = dup_validation.status == "FAIL"
    if not dup_ok:
        failures += 1
    rows.insert(
        4,
        {
            "scenario": "duplicate_disposition",
            "expected": "FAIL",
            "validation_status": dup_validation.status,
            "pass": dup_ok,
            "assigned": sum(
                1 for item in dup_plan.idea_coverage if item.disposition == "ASSIGNED"
            ),
            "deferred": sum(
                1 for item in dup_plan.idea_coverage if item.disposition == "DEFERRED"
            ),
            "excluded": sum(
                1 for item in dup_plan.idea_coverage if item.disposition == "EXCLUDED"
            ),
            "empty_disposition_ids": [
                item.idea_id for item in dup_plan.idea_coverage if not item.disposition
            ],
            "errors": list(dup_validation.errors)[:8],
        },
    )
    return {
        "idea_count": len(idea_ids),
        "scenarios": rows,
        "failures": failures,
        "status": "PASS" if failures == 0 else "FAIL",
        "expected_results": {
            "286 assigned": "PASS",
            "285 + 1 deferred": "PASS",
            "285 + 1 excluded": "PASS",
            "284 + 2 omitted": "FAIL",
            "duplicate disposition": "FAIL",
            "unknown IDEA": "FAIL",
            "reuse + primary": "PASS",
            "shuffled complete coverage": "PASS",
        },
    }


__all__ = ["run_coverage_stress"]
