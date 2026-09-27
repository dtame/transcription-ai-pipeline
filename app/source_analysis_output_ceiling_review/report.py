"""Rapport markdown déterministe 3B.7.7A.10."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_output_ceiling_review.constants import (
    ADAPTIVE_HIERARCHY_STATUS,
    CALL_C_OUTPUT,
    CALL_C_PROVIDER_INPUT,
    NEXT_ACTION,
    NEXT_PHASE_LABEL,
    PRIMARY_ROOT_CAUSE,
    PROPOSED_PROMPT,
    PROPOSED_TRANSPORT,
    REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
    SELECTED_ARCHITECTURE,
    SMALL_PLANNER_STATUS,
)


def _yn(value: Any) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    if value is None:
        return "UNKNOWN"
    return str(value)


def render_report(bundle: Mapping[str, Any]) -> str:
    result = bundle["result"]
    integrity = bundle["integrity"]
    isolation = bundle["isolation"]
    comparison = bundle["comparison"]
    contract = bundle["contract"]
    options = bundle["options"]
    decision = bundle["decision"]
    worst = bundle["worst_case"]
    forensics = bundle["forensics"]
    prefix = forensics["structured_prefix"]
    metrics = prefix["metrics"]
    kinds = metrics["kind_counts"]
    refs = metrics["source_refs"]
    composition = forensics["output_composition"]
    trunc = prefix["truncation"]
    ratios = comparison["input_ratios"]
    gen = contract["generation_c"]
    sortie = isolation["sortie"]
    return f"""# PHASE 3B.7.7A.10 — SMALL WIN001 OUTPUT-CEILING / STRUCTURED-PARSE FAILURE REVIEW

## Result

{result}

REAL PROVIDER CALLS THIS PHASE =
0

NEW WIN001 CALLS =
0

REAL SMALL WIN001 OBSERVED INPUT =
{CALL_C_PROVIDER_INPUT}

REAL SMALL WIN001 OBSERVED OUTPUT =
{CALL_C_OUTPUT} / 32000

FINISH REASON =
max_tokens

STRUCTURED PARSE =
FAIL / unterminated JSON

RAW FORENSICS =
AVAILABLE

COMPLETE RECORDS BEFORE TRUNCATION =
{prefix["complete_record_count"]}

IDEAS BEFORE TRUNCATION =
{kinds.get("IDEA")}

RELATIONS BEFORE TRUNCATION =
{kinds.get("RELATION")}

DISTINCT SRC REFS OBSERVED =
{refs.get("distinct_src_count")}

TRUNCATION LOCATION =
{trunc.get("semantic_location")} / last complete {trunc.get("last_complete_kind")} / incomplete kind visible {trunc.get("incomplete_kind_if_visible")}

TOTAL HARD CEILING =
160

WAS HARD CEILING PROVIDER-ENFORCED =
NO

PRIMARY ROOT CAUSE =
{PRIMARY_ROOT_CAUSE}

SELECTED REDESIGN =
{SELECTED_ARCHITECTURE}

SMALL PLANNER STATUS =
{SMALL_PLANNER_STATUS}

ADAPTIVE HIERARCHY STATUS =
{ADAPTIVE_HIERARCHY_STATUS}

CANONICAL SOURCEMAP =
UNCHANGED

ISOLATION TEST =
FIXED SEMANTICALLY

TESTS =
2459 passed / 0 failed

REAL PROVIDER CALL AUTHORIZED NEXT =
{_yn(REAL_PROVIDER_CALL_AUTHORIZED_NEXT)}

SOURCE MAP =
NOT PUBLISHED

PHASE 3B =
INCOMPLETE

NEXT ACTION =
{NEXT_ACTION}

## 1. Result

{result}. Offline review only. Isolation guard now asserts forensic vs
semantic vs published-canonical artifacts.

## 2. Objective

Explain why a 5447-word / 1195-SRC small WIN001 still reached 32000 output
tokens under window-analysis-1.1, then select an offline redesign.

## 3. Real-call freeze

REAL PROVIDER CALLS THIS PHASE = 0.
NEW WIN001 CALLS = 0.
No retry, no streaming, no planner activation.

## 4. 3B.7.7A.9 evidence

FAIL CONTROLLED. One authorized small WIN001 call. engine.generate = 1.
Anthropic POST = 1. HTTP 200. AIResponse CREATED. Structured parse FAIL
(unterminated JSON). Cost USD 0.421206. Finish reason max_tokens proven.

## 5. Three-call comparison

CALL A large/1.0 local {comparison["calls"][0]["local_estimate"]} /
provider {comparison["calls"][0]["provider_input"]} / output 32000 /
finish {comparison["calls"][0]["finish_reason"]} / cost {comparison["calls"][0]["cost_usd"]}.
CALL B large/1.1 local {comparison["calls"][1]["local_estimate"]} /
provider UNKNOWN / AIResponseError / body lost / cost UNKNOWN.
CALL C small/1.1 local {comparison["calls"][2]["local_estimate"]} /
provider {comparison["calls"][2]["provider_input"]} / output 32000 /
finish max_tokens / cost {comparison["calls"][2]["cost_usd"]} /
thinking_tokens {comparison["calls"][2]["thinking_tokens"]}.
Missing values were not invented.

## 6. Input-token ratios

CALL A = {ratios["call_a"]}. CALL C = {ratios["call_c"]}.
Difference A−C = {ratios["difference_a_minus_c"]}
({ratios["difference_percent_of_a"]}% of A).
Not a universal conversion factor.

## 7. Output-ceiling evidence

CALL A and CALL C both spent 32000 output tokens. Small input was about
half the local size and still consumed the full ceiling.

## 8. Forensic availability

Provider envelope and structured raw text are present under the small
signature. Historical large signatures were not overwritten.
HTTP raw sha unchanged = {_yn(integrity["forensic_bytes_preserved"]["http_raw_unchanged"])}.
Structured raw sha unchanged = {_yn(integrity["forensic_bytes_preserved"]["structured_raw_unchanged"])}.

## 9. Raw response structure

HTTP bytes = {forensics["http_envelope"]["raw_bytes"]}.
Structured text = {prefix["raw_chars"]} chars / {prefix["raw_bytes"]} bytes.
Root keys complete = {prefix["root_keys_complete"]}.
Records array reached = {_yn(prefix["records_array_reached"])}.
Records array closed = {_yn(prefix["records_array_closed"])}.
JSON remains invalid. Not treated as transport.

## 10. Truncation point

Unterminated string at column {trunc.get("unterminated_string_at_col")}.
Last complete kind = {trunc.get("last_complete_kind")}.
Incomplete kind visible = {trunc.get("incomplete_kind_if_visible")}.
Scan stopped at char {trunc.get("scan_stopped_at_char")}.

## 11. Complete records

{prefix["complete_record_count"]} complete + {prefix["incomplete_record_count"]} incomplete.
Hard ceiling 160 was not exceeded. Truncation occurred before 160.

## 12. Record kinds

{kinds}

## 13. Ideas

IDEA complete = {kinds.get("IDEA")}. Soft 40 / hard 64.
Compliance = {prefix["prompt_compliance"]["idea_soft"]} / {prefix["prompt_compliance"]["idea_hard"]}.

## 14. Relations

RELATION complete = {kinds.get("RELATION")}. Hard 36.
Compliance = {prefix["prompt_compliance"]["relation_hard"]}.
Serialized values were short (mean {metrics["value_chars_by_kind"]["RELATION"]["mean"]} chars).
Not a quadratic explosion in this prefix.

## 15. Other kinds

TOPIC {kinds.get("TOPIC")}; EXAMPLE {kinds.get("EXAMPLE")};
REFERENCE {kinds.get("REFERENCE")}; UNCERTAINTY {kinds.get("UNCERTAINTY")};
REPETITION 0 complete (incomplete tail visible);
VOICE / INTENT_KIND / AUDIENCE_KIND = 0.

## 16. Record verbosity

Mean serialized record = {metrics["serialized_size_bytes"]["mean"]} bytes
(median {metrics["serialized_size_bytes"]["median"]}, max {metrics["serialized_size_bytes"]["max"]}).
IDEA.v mean {metrics["value_chars_by_kind"]["IDEA"]["mean"]} chars / max {metrics["value_chars_by_kind"]["IDEA"]["max"]}
(limit 280). EXAMPLE.v max {metrics["value_chars_by_kind"]["EXAMPLE"]["max"]}
exceeds 200 by 1 character — compactness NONCOMPLIANT, not an explosion.

## 17. Source-ref serialization

Mean refs/record {refs["per_record"]["mean"]}; median {refs["per_record"]["median"]};
max {refs["per_record"]["max"]}; total entries {refs["total_serialized_entries"]}.
Hard max 48 never exceeded. Not a source-ref explosion.

## 18. Multi-SRC grouping

{refs["multi_src_record_count"]} of {prefix["complete_record_count"]} complete
records cite multiple SRCs. Grouping occurred. One-record-per-SRC = NO
({prefix["complete_record_count"]} records vs {refs["distinct_src_count"]} distinct SRCs vs 1195 owned).

## 19. Distinct SRC coverage

Forensic only, not semantic coverage: {refs["distinct_src_count"]} distinct
owned-looking refs, earliest {refs["earliest_src"]}, latest {refs["latest_src"]}.

## 20. Record ordering

Kind-major order: TOPIC → IDEA → RELATION → EXAMPLE → REFERENCE →
UNCERTAINTY → REPETITION (incomplete). Concept/kind order, not SRC order.

## 21. Missing categories

Not yet emitted when ceiling hit: {prefix["missing_categories_before_truncation"]}.
REPETITION was started but incomplete.

## 22. Prompt compliance

{prefix["prompt_compliance"]}
Invalid prefix cannot receive an overall semantic quality score.

## 23. Granularity contract

window-granularity-1.0 remains prompt instruction + local post-validation.
CALL C never reached post-validation because JSON parse failed first.

## 24. Prompt-only bounds

Soft/hard ceilings, text limits, source-ref max, grouping, overflow token:
all prompt-only at generation time.

## 25. Provider-enforced bounds

Generation C enforces none of: records length, value length, source-ref
count, record kind enum, thinking budget. maxItems is locally classified
unsupported for Anthropic Structured Outputs.

## 26. Post-generation bounds

validate_window_transport_granularity / validate_window_result_granularity
run after a successful parse.

## 27. Why post-validation was insufficient

A post-generation hard limit can reject excessive output. It cannot
prevent spending 32000 tokens first. CALL C never arrived there.

## 28. Generation C

Unchanged. Raw unchanged = {_yn(integrity["generation_c_raw_unchanged"])}.
Anthropic copy unchanged = {_yn(integrity["generation_c_anthropic_unchanged"])}.
Does not structurally bound records or value length.

## 29. Historical grammar constraint

3B.4 / 3B.4.1 compiled-grammar-too-large after richer compact schemas.
Generation C removed constraints to gain grammar compatibility.
Cardinality became provider-unbounded.

## 30. maxItems feasibility

Investigated offline only. Local adapter lists maxItems as unsupported.
No grammar canary this phase. Not reintroduced.

## 31. max_output analysis

Raising max_output is not adopted: it may enlarge thinking and cost.
Lowering it alone would truncate earlier unless the generation contract
and thinking budget change.

## 32. Input-size analysis

Shrinking ~50k to ~23.6k local tokens did not prevent 32k output.
That does not prove smaller windows are useless. It shows input-size
reduction alone is insufficient.

## 33. Candidate A

Single-pass all dimensions: already observed; insufficient alone.

## 34. Candidate B

Multi-pass by dimension: better kind coverage, but each pass can re-spend
~20k thinking tokens. Deferred.

## 35. Candidate C

Inventory then detail: useful later; thinking must be capped first.

## 36. Candidate D

SRC-batch extraction: grouping already works; call explosion risk. Deferred.

## 37. Candidate E

Paginated extraction with model cursor: rejected. Cursor must not be
model-invented.

## 38. Candidate F

Deterministic SRC subrange + quota: kept as overflow path, not the
primary pass. Another input halving is not assumed to fix output.

## 39. Output-oriented decomposition

The selected direction bounds OUTPUT work (fewer local kinds + reserved
JSON budget) rather than only shrinking input.

## 40. Minimal local contract

Local kinds: {worst["local_kinds"]}.
Deferred: {worst["deferred_kinds"]}.
Enough source-grounded units for later AI consolidation.

## 41. Relations responsibility

Prefix relations were cheap and already emitted. Keep optional-local with
a modest cap; global relation graphs stay with consolidation.

## 42. Repetition responsibility

Local repetition was the truncation tail. Defer to consolidation /
later pass. Global repetition is not a local-window duty.

## 43. Metadata responsibility

VOICE / INTENT_KIND / AUDIENCE_KIND had not been emitted. Local windows
should keep only short theme/intent/audience candidates already in the
header; full voice/intent/audience kinds deferred.

## 44. Topics

12 TOPIC records, grouped, useful for consolidation. Keep locally.

## 45. Traceability

Every candidate preserves original SRC refs. No numeric range compression
that would hide sparse IDs.

## 46. NO-DROP

Capacity/overflow signal remains. Deterministic subdivision if a faithful
analysis exceeds the local quota. No silent omission.

## 47. Capacity signaling

analysis_capacity_exceeded stays the explicit overflow token. Python
does not invent missing semantics.

## 48. Transport versioning

Proposed {PROPOSED_TRANSPORT}. semantic-transport-v1 is not mutated.

## 49. Prompt versioning

Proposed {PROPOSED_PROMPT}. window-analysis-1.1 is not modified.

## 50. Schema size

Generic records[] schema complexity vs Generation C = {worst["schema"]["generic_records"]["grammar_vs_generation_c"]}.
Fixed-slot option = {worst["schema"]["fixed_slots"]["grammar_vs_generation_c"]}.
Generation C raw bytes = {gen["raw_bytes"]}; adapted = {gen["adapted_bytes"]}.

## 51. Grammar-risk assessment

Generic records[]: SIMILAR to Generation C.
Fixed slots: HIGHER. No provider grammar canary this phase.

## 52. Structural worst case

Proposed maximal-policy synthetic local tokens = {worst["local_tokens"]}.
Record count = {worst["record_count"]}.
Target JSON local tokens = {worst["target_json_local_tokens"]}.
Within target = {_yn(worst["within_json_target"])}.

## 53. Output headroom

65% of 32000 is not reused as the JSON target. CALL C spent 21911
thinking tokens, leaving ~10089 for text. New target: JSON structural
worst-case ≤ 12000 local tokens AND an explicit thinking reserve
({worst["reserved_thinking_tokens"]}) so JSON is not competing for the
entire 32000.

## 54. Provider enforcement gap

Worst-case generation is still not technically enforced. This remains a
blocker for claiming true output boundedness until thinking is
request-capped and/or a future grammar canary proves cardinality.

## 55. Fixed-slot option

Clearer per-kind arrays, more schema properties, HIGHER local grammar
complexity. Not selected.

## 56. Generic-record option

Minimizes grammar size; encourages heterogeneous unbounded output unless
the prompt/kind set is reduced. Selected for the provider schema shape,
with a smaller local kind set.

## 57. Cost/call-count implications

More passes repeat input and can repeat thinking. Reliability outranks
minimizing calls, but multiplying 21911 thinking tokens is not acceptable
as the first move. Selected design stays 1 call/window unless overflow.

## 58. Small planner status

{SMALL_PLANNER_STATUS}. Input sizing remains useful. It is not activated
globally. Output architecture is the primary issue.

## 59. Adaptive hierarchy status

{ADAPTIVE_HIERARCHY_STATUS}. Downstream consolidation still needs it.

## 60. Root cause

Primary: {PRIMARY_ROOT_CAUSE}.
Provider usage.output_tokens_details.thinking_tokens = {composition.get("provider_thinking_tokens")}
of {composition.get("provider_output_tokens")} output tokens
(share {composition.get("thinking_share_of_output_tokens")}).
JSON text was only {prefix["raw_chars"]} chars (~{prefix["local_token_estimate"]} local tokens)
and still truncated.

## 61. Contributing factors

Primary: thinking tokens share max_tokens and were uncapped.
Secondary: single-pass kind-order left REPETITION/VOICE/INTENT/AUDIENCE
for the tail; prompt/schema do not enforce ceilings; post-validation
never ran.
Unknown: CALL A thinking split; controllability of thinking budget.

## 62. Selected redesign

{SELECTED_ARCHITECTURE}.
See decision JSON. Python does not infer semantic equivalence. AI merges.

## 63. Why alternatives deferred

A observed-failed; B/C/D multiply thinking or calls; E cursor-unsafe;
F retained only as overflow.

## 64. Implementation prerequisites

{decision["implementation_prerequisites"]}

## 65. Isolation-test failure

Failed assertion was
TestRealProjectsUntouched.test_aucun_repertoire_analysis_dans_le_sortie_reel:
`assert list(sortie.glob("*/analysis")) == []`.
The authorized small-WIN001 forensics created analysis/.

## 66. Original isolation intent

Prevent accidental Source Analyzer publication on real projects.
analysis/ was a proxy because the intended published file was
source_map.json.

## 67. Forensic vs semantic artifact

FORENSIC_ARTIFACT = provider_forensics / structured_output_forensics.
SEMANTIC_ANALYSIS_ARTIFACT = windows transport/result, consolidation.
PUBLISHED_CANONICAL_ARTIFACT = source_map.json.
Raw forensic response ≠ validated transport.

## 68. Isolation-test correction

The guard now forbids unauthorized semantic/canonical artifacts and
allows classified forensic directories. analysis/ existence alone is
not publication.

## 69. Isolation regression tests

Forensics allowed: PASS.
source_map.json unauthorized: FAIL.
windows/result.json or transport.json unauthorized: FAIL.

## 70. Full test suite

2459 passed, 0 failed, 2 pre-existing warnings. 0 provider calls.

## 71. Network

0.

## 72. Protected artifacts

Historical A4/A5/A7/A8/A9 reports and execution JSON preserved.
Small forensic raw hashes match 3B.7.7A.9.

## 73. CLEAN

Clean transcript unchanged = {_yn(integrity["clean_unchanged"])}.

## 74. Prompt 1.1

Unchanged = {_yn(integrity["prompt_1_1_unchanged"])}.

## 75. Granularity 1.0

Unchanged = {_yn(integrity["granularity_unchanged"])}.

## 76. Generation C

Not mutated.

## 77. SourceMap

Absent = {_yn(not integrity["source_map_present"])}. Canonical contract unchanged.

## 78. Project state

status={integrity["project_state"].get("status")} not SUCCESS =
{_yn(integrity["project_state"]["not_success"])}.

## 79. Files added

app/source_analysis/publication_isolation.py
app/source_analysis_output_ceiling_review/*
audit artefacts listed in writer
updated isolation tests

## 80. Files modified

app/tests/test_source_analysis_isolation.py
No forensic raw files rewritten.

## 81. Remaining unknowns

CALL A/B thinking split. Whether this model accepts an explicit thinking
budget. Whether the JSON would have closed if thinking were capped.
Provider maxItems accept/reject without a future canary.

## 82. Recommended next phase

{NEXT_PHASE_LABEL}

REAL PROVIDER CALL AUTHORIZED NEXT =
{_yn(REAL_PROVIDER_CALL_AUTHORIZED_NEXT)}
"""
