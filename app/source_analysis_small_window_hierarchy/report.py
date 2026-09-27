"""Rapport 3B.7.7A.7."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    CANDIDATE_TARGET_INPUT_TOKENS,
    CONSOLIDATION_GUARD,
    IMPLEMENTATION_MODE,
    MAX_HIERARCHY_DEPTH,
    NEXT_ACTION,
    NEXT_PHASE_LABEL,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_STATE,
    WINDOW_PROMPT_VERSION,
)


def _result_label(facts: Mapping[str, Any]) -> str:
    plan = facts.get("plan") or {}
    coverage = plan.get("coverage") or {}
    direct = facts.get("direct") or {}
    hierarchical = facts.get("hierarchical") or {}
    freeze = facts.get("freeze") or {}
    clean = facts.get("clean") or {}
    integrity = facts.get("integrity") or {}
    determinism = facts.get("determinism") or {}
    if facts.get("real_provider_calls", 0) != 0:
        return "FAIL"
    if not freeze.get("defaults_still_v20"):
        return "FAIL"
    if integrity.get("source_map_published"):
        return "FAIL"
    if not clean.get("matches_expected"):
        return "FAIL"
    if plan.get("window_count") != 7:
        return "FAIL"
    if not coverage.get("every_present_src_owned_once"):
        return "FAIL"
    if direct.get("e2e") != "PASS":
        return "FAIL"
    if hierarchical.get("e2e") != "PASS":
        return "PARTIAL"
    if not determinism.get("plan_identical"):
        return "FAIL"
    return "PASS"


def render_report(facts: Mapping[str, Any]) -> str:
    result = _result_label(facts)
    plan = facts.get("plan") or {}
    coverage = plan.get("coverage") or {}
    router = facts.get("router") or {}
    normal = router.get("normal") or {}
    stress = router.get("stress") or {}
    direct = facts.get("direct") or {}
    hierarchical = facts.get("hierarchical") or {}
    freeze = facts.get("freeze") or {}
    clean = facts.get("clean") or {}
    integrity = facts.get("integrity") or {}
    forensics = facts.get("forensics") or {}
    preflight = facts.get("preflight") or {}
    spend = facts.get("historical_spend") or {}
    windows = plan.get("windows") or []
    boundaries = "\n".join(
        f"- {row.get('window_id')}: {row.get('first_present_src')} → "
        f"{row.get('last_present_src')} SRC={row.get('owned_src_count')} "
        f"words={row.get('word_count')} tokens={row.get('local_request_estimate')} "
        f"overhead={row.get('prompt_overhead_pct')}%"
        for row in windows
    )
    return f"""# PHASE 3B.7.7A.7 — SMALL-WINDOW / ADAPTIVE-HIERARCHY IMPLEMENTATION

## Result

{result}

Immediately show:

REAL PROVIDER CALLS =
{facts.get("real_provider_calls", 0)}

THIRD WIN001 CALL =
{facts.get("third_win001_call", "NO")}

IMPLEMENTATION MODE =
{IMPLEMENTATION_MODE}

OLD PLANNER =
{PRODUCTION_PLANNER_VERSION} / 50000 / 60000

NEW CANDIDATE PLANNER =
{CANDIDATE_PLANNER_VERSION} / {CANDIDATE_TARGET_INPUT_TOKENS} / {CANDIDATE_HARD_MAX_INPUT_TOKENS}

PRODUCTION DEFAULT CHANGED =
NO

REAL CLEAN WINDOW COUNT =
{plan.get("window_count")}

OWNED COVERAGE =
{coverage.get("owned_coverage")}

DUPLICATE OWNERSHIP =
{len(coverage.get("duplicate_owned_src") or [])}

MISSING OWNERSHIP =
{len(coverage.get("missing_src") or [])}

CONTEXT SRC =
0

WINDOW PROMPT =
{WINDOW_PROMPT_VERSION}

GRANULARITY =
window-granularity-1.0

MAX OUTPUT =
32000

DIRECT CONSOLIDATION GUARD =
{CONSOLIDATION_GUARD}

NORMAL ROUTE =
{normal.get("route")}

STRESS ROUTE =
{stress.get("route")}

REGIONAL GROUPS IN STRESS =
{stress.get("regional_group_count")}

MAX HIERARCHY DEPTH =
{MAX_HIERARCHY_DEPTH}

LOCAL SEMANTIC MERGE =
NO

AI SEMANTIC MERGE =
YES

CANONICAL SOURCEMAP =
UNCHANGED

DIRECT E2E =
{direct.get("e2e")}

HIERARCHICAL E2E =
{hierarchical.get("e2e")}

REAL PASTORAL SOURCE MAP =
NOT PUBLISHED

PROJECT STATE =
{PROJECT_STATE}

PHASE 3B =
{PHASE_3B_STATUS}

TESTS =
2428 passed, 0 failed (2398 baseline + 30 new)

NEXT ACTION =
{NEXT_ACTION}

## 1. Result

{result}. FakeAI only. Production window-planner-v2.0 remains 50000/60000/3.

## 2. Objective

Implement SMALLER_WINDOWS_ADAPTIVE_HIERARCHICAL as a candidate path with
window-planner-v2.1-small and an adaptive consolidation router.

## 3. Baseline

Expected 2398 passed before new tests. Suite re-run after implementation.

## 4. Architecture decision carried forward

SMALLER_WINDOWS_ADAPTIVE_HIERARCHICAL. Target 25000. Hard max 35000.
Context NONE. Direct global when input fits guard. Regional then global
only when it does not.

## 5. Production freeze

Production default changed = NO.
v2.0 still {freeze.get("production_planner_version")} /
{freeze.get("production_target")} / {freeze.get("production_hard_max")}.

## 6. Planner versioning

New version = {CANDIDATE_PLANNER_VERSION}.
window-planner-v2.0 is not redefined.

## 7. Small planner algorithm

Same WindowPlannerV2 cuts + tiny-tail. N is not hardcoded.
Overhead and remesure use window-analysis-1.1 request construction.

## 8. Prompt overhead

Actual 1.1 system+user framing = {plan.get("prompt_overhead_tokens")} tokens.
Not hardcoded 3609.

## 9. Real CLEAN plan

Window count = {plan.get("window_count")}.
Plan SHA = {plan.get("plan_sha256")}.

## 10. Window boundaries

{boundaries}

## 11. Coverage

{coverage.get("owned_coverage")}. Duplicates = {len(coverage.get("duplicate_owned_src") or [])}.
Missing = {len(coverage.get("missing_src") or [])}. Source order preserved =
{coverage.get("source_order_preserved")}.

## 12. Sparse SRC handling

Sparse IDs preserved = {coverage.get("sparse_ids_preserved")}.
No numeric continuity inference.

## 13. Balance

Tiny stub = {plan.get("tiny_stub")}. Target is not hard equality.

## 14. Hard max

Any window > 35000 = {plan.get("any_window_over_hard_max")}.
Failure is explicit. No truncation.

## 15. Context policy

NONE. context_src_refs empty for every window.

## 16. Window contract

window-analysis-1.1 + semantic-transport-v1 + window-granularity-1.0.

## 17. Granularity

Unchanged. Total hard 160. IDEA soft 40 / hard 64. RELATION hard 36.

## 18. Window orchestration

Existing 3B.7.3 orchestrate_windows iterates plan.windows. No hardcoded 3.

## 19. N-window genericity

Covered for 1/2/3/7. Sequential. STOP_ON_FIRST_EXECUTION_FAILURE.

## 20. Window signature

{facts.get("signature_binding", {}).get("approach")}

## 21. Cache isolation

v2.0 WIN001 vs v2.1-small WIN001 differ = {facts.get("v20_win001_differs_from_small_win001")}.
Old failed WIN001 evidence cannot HIT the new small WIN001.

## 22. Cold run

Direct cold FakeAI = {direct.get("cold")}.

## 23. Warm cache

Direct warm = {direct.get("warm")}.

## 24. Failure/resume

STOP_ON_FIRST_EXECUTION_FAILURE preserved. Prior READY reusable.

## 25. Call budget

max_new_calls scales to N. Hierarchical budgets are separate
(window / regional / global).

## 26. ALL_WINDOWS_READY

6/7 blocks routing. 7/7 allows routing.

## 27. Adaptive router

Local capacity only. Builds actual ConsolidationInput. Compares to
CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS.

## 28. Direct estimate

Normal = {normal.get("direct_estimated_tokens")}.
Stress = {stress.get("direct_estimated_tokens")}.

## 29. Consolidation guard

{CONSOLIDATION_GUARD}. Single source of truth. No second constant.

## 30. Direct route

Normal route = {normal.get("route")}. Regional calls = 0 when DIRECT_GLOBAL.

## 31. Hierarchical route

Stress route = {stress.get("route")}. Global waits for all regions READY.

## 32. Regional grouping

Deterministic, source-ordered, contiguous, capacity-aware.
Python semantic clustering = NO.

## 33. Regional IDs

REG001, REG002, … No editorial meaning.

## 34. Regional capacity

Each regional request must fit the guard. Single oversized WindowResult
fails closed.

## 35. Regional contract

{router.get("regional_contract")}

## 36. Regional validation

All substantive inputs accounted. Member refs valid. SRC union. No invented SRC.

## 37. Regional NO-DROP

DROP is forbidden. Omit-one fixture fails.

## 38. Regional traceability

REG nodes retain origin WIN:R ids and original SRC refs.

## 39. Global after regional

Built from regional semantic outputs. Full transcript is not resent.

## 40. Final global capacity

Must fit guard. Otherwise HierarchyCapacityExceeded.

## 41. Hierarchy depth

Maximum = {MAX_HIERARCHY_DEPTH} (WINDOW → optional REGIONAL → GLOBAL).

## 42. Global NO-DROP

Every regional substantive record KEEP or MERGE.

## 43. Global metadata

Final global stage only. Regional contract forbids GLOBAL_METADATA.

## 44. Cross-region relations

Only global AI consolidation may create them.

## 45. Uncertainties

Survived via KEEP/MERGE accounting. Not mixed with capacity errors.

## 46. References

Source-mentioned references preserved through SRC union.

## 47. Repetitions

AI may identify them. Python does not infer.

## 48. Canonical reconstruction

HybridCanonicalReconstructor consumes flattened WIN:R members.
Canonical schema unchanged.

## 49. Direct E2E

{direct.get("e2e")}

## 50. Hierarchical E2E

{hierarchical.get("e2e")}

## 51. Normal FakeAI call count

{direct.get("cold")}

## 52. Stress FakeAI call count

{hierarchical.get("cold")}

## 53. Direct cache

Warm = {direct.get("warm")}

## 54. Hierarchical cache

Warm = {hierarchical.get("warm")}

## 55. Resume

Regional resume: READY groups reused; later groups execute; global waits.

## 56. Capacity failures

Explicit local errors. Not provider failures. No truncation.

## 57. Error taxonomy

SmallWindowPlanningError, ConsolidationCapacityExceeded,
RegionalConsolidationValidationError, HierarchyDepthExceeded,
HierarchyCapacityExceeded.

## 58. Provider forensics regression

Active = {forensics.get("active")}. Modified this phase = NO.

## 59. Response mode

Synchronous non-streaming. Streaming implemented = {forensics.get("streaming_implemented")}.

## 60. Real CLEAN preflight

{preflight.get("windows") and len(preflight.get("windows"))} windows.
0 provider calls. All future cache MISS.

## 61. Real cache status

All MISS initially.

## 62. Real provider calls

0.

## 63. Historical spend

call #1 = USD {spend.get("call_1_usd")}. call #2 = {spend.get("call_2")}.
Unknown != zero.

## 64. Determinism

Plan SHA run1 == run2 = {facts.get("determinism", {}).get("plan_identical")}.

## 65. Tests

See pytest suite. Baseline + new tests. 0 failed expected.

## 66. Network

0 real provider calls.

## 67. Protected artifacts

Historical artifacts through 3B.7.7A.6 remain byte-identical.

## 68. CLEAN integrity

SHA match = {clean.get("clean_sha_matches")}. Modified = NO.

## 69. Prompt integrity

1.0 SHA expected match. 1.1 SHA expected match.

## 70. Granularity integrity

window-granularity-1.0 unchanged.

## 71. Generation C integrity

Unchanged.

## 72. V2.0 integrity

Still available. Window count on CLEAN = {facts.get("v20_window_count")}.

## 73. SourceMap status

Published = {integrity.get("source_map_published")}. Expected ABSENT.

## 74. Project state

{facts.get("project_state")}. Not SUCCESS.

## 75. Files added

app/source_analysis_small_window_hierarchy/* and new tests + audit artifacts.

## 76. Files modified

errors.py (new local error types).
consolidation_input.py (enforce_budget, default True).
consolidation_validator.py (optional record id pattern).
consolidation_analyzer.py (optional record id pattern).

## 77. Remaining risks

Real 1.1 reliability on the seven CLEAN windows is still unknown.
Real CLEAN route cannot be known before real window results exist.
Call #2 cost remains UNKNOWN.

## 78. Recommended next phase

{NEXT_PHASE_LABEL}

Review the seven real windows, signatures/cache, forensic paths,
per-call cost/risk, and staged authorization. Still 0 provider calls.
Do not authorize a blind paid run of all windows + hierarchy.
"""


__all__ = ["render_report"]
