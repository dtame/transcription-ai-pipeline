"""Rapport markdown déterministe 3B.7.7A.16."""

from __future__ import annotations

from typing import Any, Mapping


def _dash(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value)


def render_report(bundle: Mapping[str, Any]) -> str:
    h = bundle.get("header") or {}
    replay = bundle.get("replay") or {}
    forensics = bundle.get("forensics") or {}
    prompt = bundle.get("prompt") or {}
    semantic = bundle.get("semantic") or {}
    coverage = bundle.get("coverage") or {}
    options = bundle.get("options") or {}
    decision = bundle.get("decision") or {}
    invalid = forensics.get("invalid_table") or []
    compliance = forensics.get("per_kind_compliance") or {}
    counts = semantic.get("grounding_counts") or {}
    lines = [
        "# PHASE 3B.7.7A.16 — A.15 INVALID-LINK FORENSICS & OFFLINE SEMANTIC REVIEW",
        "",
        "## Result",
        "",
        str(h.get("result") or "UNKNOWN"),
        "",
        f"REAL PROVIDER CALLS = {h.get('real_provider_calls')}",
        "",
        f"REAL WINDOW CALLS = {h.get('real_window_calls')}",
        "",
        f"A.15 HTTP = {h.get('a15_http')}",
        "",
        f"A.15 THINKING TOKENS = {h.get('a15_thinking_tokens')}",
        "",
        f"A.15 OUTPUT = {h.get('a15_output')}",
        "",
        f"A.15 FINISH = {h.get('a15_finish')}",
        "",
        f"A.15 STRUCTURED PARSE = {h.get('a15_structured_parse')}",
        "",
        f"A.15 RECORDS = {h.get('a15_records')}",
        "",
        f"INVALID RECORDS = {h.get('invalid_records')}",
        "",
        f"INVALID LINKS = {h.get('invalid_links')}",
        "",
        f"LINK FAILURE PATTERN = {h.get('link_failure_pattern')}",
        "",
        f"PER-KIND LINK COMPLIANCE = {h.get('per_kind_link_compliance')}",
        "",
        f"GLOBAL INDEX HYPOTHESIS = {h.get('global_index_hypothesis')}",
        "",
        f"PER-KIND ORDINAL HYPOTHESIS = {h.get('per_kind_ordinal_hypothesis')}",
        "",
        f"PROMPT AMBIGUITY REMAINING = {h.get('prompt_ambiguity_remaining')}",
        "",
        f"SEMANTIC RECORD GROUNDING = {h.get('semantic_record_grounding')}",
        "",
        f"MAJOR IDEA COVERAGE = {h.get('major_idea_coverage')}",
        "",
        f"SEMANTIC SRC COVERAGE = {h.get('semantic_src_coverage')}",
        "",
        f"COVERAGE DISTRIBUTION = {h.get('coverage_distribution')}",
        "",
        f"LARGEST SUBSTANTIVE GAP = {h.get('largest_substantive_gap')}",
        "",
        f"UNSUPPORTED CONTENT = {h.get('unsupported_content')}",
        "",
        f"SEMANTIC CONTENT CLASSIFICATION = {h.get('semantic_content_classification')}",
        "",
        f"THINKING_DISABLED QUALITY = {h.get('thinking_disabled_quality')}",
        "",
        f"SELECTED LINK ARCHITECTURE = {h.get('selected_link_architecture')}",
        "",
        f"NEW PROMPT = {h.get('new_prompt')}",
        "",
        f"NEW TRANSPORT = {h.get('new_transport')}",
        "",
        f"SCHEMA CHANGED = {h.get('schema_changed')}",
        "",
        f"SERVER GRAMMAR STATUS = {h.get('server_grammar_status')}",
        "",
        f"SYNTHETIC MAX OUTPUT = {h.get('synthetic_max_output')}",
        "",
        f"FUTURE WIN001 INPUT ESTIMATE = {h.get('future_win001_input_estimate')}",
        "",
        f"FUTURE REAL CALL AUTHORIZED = {h.get('future_real_call_authorized')}",
        "",
        f"PRODUCTION DEFAULT = {h.get('production_default')}",
        "",
        f"SOURCE MAP = {h.get('source_map')}",
        "",
        f"PHASE 3B = {h.get('phase_3b')}",
        "",
        f"TESTS = {h.get('tests')}",
        "",
        f"NEXT ACTION = {h.get('next_action')}",
        "",
        "## 1. Mode",
        "",
        "OFFLINE_A15_INVALID_LINK_FORENSICS_AND_SEMANTIC_REVIEW. "
        "0 provider calls. 0 window calls. No WIN001 retry. No WIN002–WIN007. "
        "No consolidation. No response repair. No cache salvage.",
        "",
        "## 2. A.15 replay",
        "",
        f"structured_parse = {replay.get('structured_parse')}. "
        f"decoder = {replay.get('v2_decoder')}. "
        f"validator = {replay.get('v2_validator')}. "
        f"reproduced = {replay.get('reproduced')}. "
        f"records = {replay.get('record_count')}. "
        f"invalid_targets = {(replay.get('link_metrics') or {}).get('invalid_targets')}.",
        "",
        "The A.15 response remains an invalid transport. It was inspected, not promoted.",
        "",
        "## 3. Invalid records versus invalid links",
        "",
        f"Invalid records = {forensics.get('invalid_record_count')} "
        f"{forensics.get('invalid_record_indexes')}.",
        "",
        f"Invalid individual links = {forensics.get('invalid_link_count')}.",
        "",
        "Do not conflate them. Records 57 and 58 each contribute two invalid "
        "RELATION→TOPIC links. Records 75–77 each contribute one EXAMPLE→TOPIC link.",
        "",
        "## 4. Exact invalid-link table",
        "",
    ]
    for row in invalid:
        lines.append(
            f"- records[{row.get('record_index')}] {row.get('kind')} v={row.get('v')!r} "
            f"s={row.get('s')} l={row.get('l')} target={row.get('target_index')} "
            f"{row.get('target_kind')} {row.get('target_value')!r} "
            f"nearest_prec_IDEA={row.get('nearest_preceding_idea_index')} "
            f"nearest_foll_IDEA={row.get('nearest_following_idea_index')} "
            f"nearest_TOPIC={row.get('nearest_topic')} "
            f"src_overlap={row.get('source_overlap_with_candidate_target')} "
            f"reason={row.get('reason_invalid')}"
        )
    idea = compliance.get("IDEA") or {}
    rel = compliance.get("RELATION") or {}
    ex = compliance.get("EXAMPLE") or {}
    lines.extend(
        [
            "",
            "## 5. Per-kind link compliance",
            "",
            f"IDEA→TOPIC = {idea.get('valid_links')}/{idea.get('total_links')} ({idea.get('pct')}%).",
            "",
            f"RELATION→IDEA = {rel.get('valid_links')}/{rel.get('total_links')} ({rel.get('pct')}%).",
            "",
            f"EXAMPLE→IDEA = {ex.get('valid_links')}/{ex.get('total_links')} ({ex.get('pct')}%).",
            "",
            "IDEA→TOPIC is fully valid. The failure is specific to later kinds, "
            "and even there most RELATION links are valid.",
            "",
            "## 6. Index hypotheses",
            "",
            f"Global index: {h.get('global_index_hypothesis')}",
            "",
            f"Per-kind ordinal: {h.get('per_kind_ordinal_hypothesis')}",
            "",
            "Valid RELATION l values are global IDEA indexes (13–54), not IDEA "
            "ordinals (0–43). Invalid l values are also global indexes — of TOPIC "
            "records. Reading them as IDEA ordinals does not recover the emitted targets.",
            "",
            "## 7. Prompt 1.2.1 audit",
            "",
            f"0-based TARGET explicit = {(prompt.get('compliance') or {}).get('zero_based_target_explicit')}.",
            "",
            f"Per-kind rules explicit = {(prompt.get('compliance') or {}).get('per_kind_target_rules_explicit')}.",
            "",
            f"Self-link forbidden = {(prompt.get('compliance') or {}).get('self_link_prohibition_explicit')}.",
            "",
            f"RELATION rule correct = {(prompt.get('compliance') or {}).get('relation_rule_correct')}.",
            "",
            f"RELATION JSON example = {(prompt.get('compliance') or {}).get('relation_json_example_present')}.",
            "",
            f"EXAMPLE JSON example = {(prompt.get('compliance') or {}).get('example_json_example_present')}.",
            "",
            f"Old phrase 'index locaux de CE transport' in 1.2.1 = "
            f"{(prompt.get('conflicts') or {}).get('old_v1_phrase_present')}.",
            "",
            "LINK RULES sit late in the short system prompt and early in the user "
            "prompt, then are diluted by the owned-source dump. Remaining ambiguity: "
            "no RELATION worked example; mini-example l=[1] is an IDEA only in a "
            "3-record world; never-TOPIC-even-if-thematic is unstated.",
            "",
            "## 8. Schema",
            "",
            "Schema still only guarantees l is an integer array. It cannot enforce "
            "RELATION→IDEA or EXAMPLE→IDEA. Schema was not enlarged.",
            "",
            "## 9. Forensic semantic review",
            "",
            "Status = FORENSIC_SEMANTIC_REVIEW_OF_INVALID_TRANSPORT. Not a validated result.",
            "",
            f"Grounding counts = {counts}.",
            "",
            "Topics are useful and distinct. Ideas are compact paraphrases covering "
            "the sermon’s movement. Some RELATION indexes are valid but semantically "
            "loose (59, 61). Examples 75–77 are genuine anecdotes wrongly aimed at "
            "TOPICs. References and uncertainties are present in cited SRC. "
            "Legitimate French remains. Interpreter translations were not reconstructed.",
            "",
            "## 10. Coverage",
            "",
            f"238/1195 = {coverage.get('semantic_src_coverage_pct')}%. Not automatically bad.",
            "",
            _dash(coverage.get("coverage_distribution")),
            "",
            f"Largest substantive gap = {_dash((coverage.get('largest_substantive_gap') or {}).get('start_src'))}"
            f" → {_dash((coverage.get('largest_substantive_gap') or {}).get('end_src'))}"
            f" ({_dash((coverage.get('largest_substantive_gap') or {}).get('classification'))}).",
            "",
            "19.92% is mostly compression, multi-SRC grouping, and low-information "
            "stretches (cake, amen, scripture reread), with thinner later application.",
            "",
            "## 11. Thinking-disabled",
            "",
            "On this window: thinking=0, output completed, JSON parsed, shared-budget "
            "truncation did not recur. That does not prove thinking-disabled is "
            "globally suitable. Apart from link encoding, semantic content is "
            "acceptable local extraction. Adaptive-low is not justified.",
            "",
            "## 12. Architecture",
            "",
            f"Selected = {options.get('selected')} ({decision.get('status')}).",
            "",
            "Per-kind ordinals are contraindicated (silent remap of TOPIC numbers). "
            "Prompt-only is insufficient alone after A.14. Inline nesting and "
            "two-pass are not justified. Local symbolic handles move arithmetic "
            "to Python and keep kind visible. Not implemented in A.16.",
            "",
            "## 13. Isolation",
            "",
            "A.15 raw/structured/forensics/execution/report unchanged. A.13 and "
            "CALL C unchanged. CLEAN unchanged. No candidate cache. No source_map. "
            "Production planner remains window-planner-v2.0. Phase 3B INCOMPLETE.",
            "",
            "## 14. Required questions",
            "",
            "Were any provider calls made? NO.",
            "",
            "Was WIN001 retried? NO.",
            "",
            "What exactly are the 7 invalid links? RELATION 57→TOPIC 1,2; "
            "RELATION 58→TOPIC 10,11; EXAMPLE 75→TOPIC 3; EXAMPLE 76→TOPIC 4; "
            "EXAMPLE 77→TOPIC 5.",
            "",
            f"How many records are actually invalid? {forensics.get('invalid_record_count')}.",
            "",
            f"What percentage of RELATION links are valid? {rel.get('pct')}%.",
            "",
            f"What percentage of EXAMPLE links are valid? {ex.get('pct')}%.",
            "",
            "Are IDEA→TOPIC links valid? YES, 100%.",
            "",
            "Did Claude use global indexes correctly elsewhere? YES.",
            "",
            "Did it mix global indexes with per-kind ordinals? NO for the invalid set.",
            "",
            "Are invalid links arithmetic or semantic? Kind-selection / conceptual "
            "TOPIC targeting, using correct global numbers.",
            "",
            "Does prompt 1.2.1 remain ambiguous anywhere? YES.",
            "",
            "Does record ordering contribute? It makes TOPIC indexes salient; it is "
            "not the sole cause.",
            "",
            "Is semantic content itself well grounded? Yes as forensic paraphrase review.",
            "",
            f"How many records are unsupported? {counts.get('UNSUPPORTED', 0)}.",
            "",
            "Are major ideas represented? YES, with listed diagnostic omissions.",
            "",
            "Are there substantive unreferenced regions? Some later application is thinner.",
            "",
            "Does 19.92% indicate compression or omission? Primarily compression.",
            "",
            "Did extraction cover beginning/middle/end? YES.",
            "",
            "Are topics useful? YES.",
            "",
            "Are ideas grouped sensibly? YES, with mild death/immortality restatement.",
            "",
            "Are relations semantically plausible apart from indexes? Most yes; 59 and 61 weak.",
            "",
            "Are examples genuine? YES.",
            "",
            "Are references genuine? YES.",
            "",
            "Are uncertainties genuine? YES.",
            "",
            "Is thinking-disabled semantic content acceptable apart from link encoding? YES.",
            "",
            "Is adaptive-low justified by evidence? NO.",
            "",
            "Should the LLM continue calculating global numeric indexes? Prefer not.",
            "",
            "What alternative transport is simplest? LOCAL_SYMBOLIC_HANDLES.",
            "",
            "Would schema structure change? Not in A.16. A.17 must choose encoding.",
            "",
            "Would another grammar canary become necessary? Only if schema structure changes.",
            "",
            "Can A.13 grammar proof still be reused? YES while schema is unchanged.",
            "",
            "Is another real WIN001 call justified eventually? Not from this phase.",
            "",
            "What exact issue should that future call test? The new handle contract.",
            "",
            "Is production unchanged? YES.",
            "",
            "Is source_map absent? YES.",
            "",
            f"Does full suite pass? {h.get('tests')}.",
            "",
            "## 15. Next phase",
            "",
            "Recommend A.17 — offline transport/prompt redesign implementation "
            "(LOCAL_SYMBOLIC_HANDLES). Do not execute a real WIN001 retry or "
            "adaptive-low canary from this report.",
            "",
            "NEXT ACTION = HUMAN REVIEW",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
