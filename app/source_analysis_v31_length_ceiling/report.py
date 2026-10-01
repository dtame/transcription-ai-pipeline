"""Rapport markdown 3B.7.7A.29. Offline."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: bool | None) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "UNKNOWN"


def render_report(bundle: Mapping[str, Any], *, tests: str) -> str:
    header = bundle["header"]
    offenders = bundle["replay"]["offenders"]
    decision = bundle["decision"]
    counter = bundle["counterfactual"]
    classification = bundle["classification"]
    semantic = counter.get("semantic_review") or {}
    relations = semantic.get("relation_quality_summary") or {}
    ready = bundle["distribution"].get("ready_only") or {}
    lines = [
        "# PHASE 3B.7.7A.29 — WIN003 VALUE-LENGTH CEILING FORENSICS",
        "",
        "## Result",
        "",
        str(header["result"]),
        "",
        "REAL PROVIDER CALLS =",
        str(header["real_provider_calls"]),
        "",
        "REAL WINDOW CALLS =",
        str(header["real_window_calls"]),
        "",
        "A.28 STATUS =",
        "FAIL unchanged",
        "",
        "READY WINDOWS =",
        "3 / 7",
        "",
        "OFFENDING VALUES =",
        (
            f"theme {offenders['theme']['chars']} chars ; "
            f"IDEA {offenders['idea']['chars']} chars ; "
            f"EXAMPLE {offenders['example']['chars']} chars"
        ),
        "",
        "200 LIMIT ORIGIN =",
        str(bundle["boundary"]["200_limit_origin"]),
        "",
        "200 LIMIT ENFORCED BY =",
        str(bundle["boundary"]["200_enforced_by"]),
        "",
        "PROVIDER SCHEMA ENFORCES 200 =",
        _yn(bundle["boundary"]["provider_schema_enforces_200"]),
        "",
        "CANONICAL MODEL REQUIRES 200 =",
        _yn(bundle["boundary"]["canonical_model_requires_200"]),
        "",
        "WIN003 FAILURE CLASS =",
        str(decision["failure_class"]),
        "",
        "OFFENDING VALUES SEMANTIC QUALITY =",
        (
            f"theme {classification['theme']['grounding']} / "
            f"IDEA {classification['idea']['grounding']} / "
            f"EXAMPLE {classification['example']['grounding']}"
        ),
        "",
        "REAL LENGTH DISTRIBUTION =",
        (
            "READY maxima theme="
            f"{(ready.get('theme') or {}).get('maximum')} "
            f"IDEA.v={(ready.get('IDEA.v') or {}).get('maximum')} "
            f"EXAMPLE.v={(ready.get('EXAMPLE.v') or {}).get('maximum')}; "
            "only A.28 WIN003 exceeds 200 on theme/EXAMPLE"
        ),
        "",
        "COUNTERFACTUAL 225 =",
        str(counter["counterfactual_225"]),
        "",
        "COUNTERFACTUAL 250 =",
        str(counter["counterfactual_250"]),
        "",
        "COUNTERFACTUAL 300 =",
        str(counter["counterfactual_300"]),
        "",
        "COUNTERFACTUAL WIN003 SEMANTIC QUALITY =",
        str(semantic.get("semantic_quality") or "NOT_PERFORMED"),
        "",
        "SELECTED POLICY =",
        str(decision["selected_policy"]),
        "",
        "PROPOSED LIMITS =",
        (
            f"theme={decision['proposed_limits']['theme']}; "
            f"EXAMPLE.v={decision['proposed_limits']['EXAMPLE.v']}; "
            f"IDEA.v={decision['proposed_limits']['IDEA.v']} unchanged"
        ),
        "",
        "PROMPT CHANGE REQUIRED =",
        _yn(decision["prompt_change_required"]),
        "",
        "TRANSPORT VERSION CHANGE REQUIRED =",
        _yn(decision["transport_version_change_required"]),
        "",
        "SCHEMA IDENTITY CHANGES =",
        _yn(decision["schema_identity_changes"]),
        "",
        "A.18 GRAMMAR PROOF STILL APPLIES =",
        _yn(decision["a18_grammar_proof_still_applies"]),
        "",
        "WIN003 FUTURE ACTION =",
        str(decision["win003_future_action"]),
        "",
        "WIN005-007 SAFE TO RESUME AFTER FIX =",
        _yn(decision["win005_007_safe_to_resume_after_fix"]),
        "",
        "TESTS =",
        tests,
        "",
        "SOURCE MAP =",
        "NOT PUBLISHED",
        "",
        "PHASE 3B =",
        "INCOMPLETE",
        "",
        "NEXT ACTION =",
        "HUMAN REVIEW",
        "",
        "## 1. Mode",
        "",
        "OFFLINE ONLY. Real provider calls = 0. Real window calls = 0. "
        "No WIN003 retry. No WIN005/WIN006/WIN007. No consolidation. "
        "Production TEXT_HARD_LIMITS unchanged.",
        "",
        "## 2. Exact failure reproduction",
        "",
        f"Reproduced={bundle['replay']['reproduced']}.",
        f"A.28 validator error reproduced: `{bundle['replay']['granularity_error']}`.",
        "Production validator failed theme and EXAMPLE only. "
        "IDEA 209 was listed in the A.28 exhaustive inventory against an "
        "assumed 200 ceiling; production IDEA.v is 280, so IDEA 209 is legal.",
        "",
        f"theme ({offenders['theme']['chars']}): {offenders['theme']['value']}",
        "",
        f"IDEA[{offenders['idea']['index']}] ({offenders['idea']['chars']}): "
        f"{offenders['idea']['value']}",
        "",
        f"EXAMPLE[{offenders['example']['index']}] ({offenders['example']['chars']}): "
        f"{offenders['example']['value']}",
        "",
        "## 3. Character definition",
        "",
        "200 characters means Python `len(str)` = Unicode code points. "
        "Not bytes, not tokens, not trimmed, not normalized. "
        "No local truncation.",
        "",
        "## 4. Boundary map",
        "",
        "Provider schema / transport schema / decoder / canonical model / "
        "publication: no 200 maxLength. Local validator is the only hard gate.",
        "",
        "## 5. Prompt contract (window-analysis-1.4.0)",
        "",
        bundle["boundary"]["prompt"]["verbatim_contract_line"],
        "",
        "theme, EXAMPLE.v, RELATION.v, REFERENCE.v, UNCERTAINTY.v are not "
        "instructed to stay within 200 characters.",
        "",
        "## 6. Offending-value classification",
        "",
        f"theme: {classification['theme']['classification']} / "
        f"{classification['theme']['grounding']}. "
        f"{classification['theme']['reason']}",
        "",
        f"IDEA: {classification['idea']['classification']} / "
        f"{classification['idea']['grounding']}. "
        f"{classification['idea']['reason']}",
        "",
        f"EXAMPLE: {classification['example']['classification']} / "
        f"{classification['example']['grounding']}. "
        f"{classification['example']['reason']}",
        "",
        "## 7. Counterfactual semantic review",
        "",
        "Performed only because 225/250/300 are technically clean. "
        "Does not mark WIN003 READY. A.28 remains FAIL.",
        "",
        f"semantic_quality = {semantic.get('semantic_quality')}",
        f"unsupported = {semantic.get('unsupported_count')}",
        f"material_omissions = {semantic.get('material_omissions')}",
        (
            "relations diagnostic (WIN003 only, not added to READY total): "
            f"well-supported {relations.get('well-supported', 0)} / "
            f"plausible-loose {relations.get('plausible-loose', 0)} / "
            f"incorrect {relations.get('incorrect', 0)} / "
            f"unverifiable {relations.get('unverifiable', 0)}"
        ),
        "",
        "Current successful READY relation total remains "
        "36 plausible-loose / 0 well-supported (A.27 WIN004 + A.28 WIN002).",
        "",
        "## 8. Token-budget and grammar impact",
        "",
        "Raising only theme and EXAMPLE.v from 200 to 225 adds at most "
        f"{(counter.get('token_budget') or {}).get('proposed_only_theme_and_example_225', {}).get('extra_chars')} "
        "worst-case characters / "
        f"{(counter.get('token_budget') or {}).get('proposed_only_theme_and_example_225', {}).get('extra_local_tokens')} "
        "local tokens versus a 200 baseline at established EXAMPLE cardinality. "
        "max_output stays 32000. JSON schema bytes, adapted schema bytes, and "
        "schema hash do not change. A.18 grammar proof still applies.",
        "",
        "## 9. Downstream",
        "",
        "Editorial Planner / Book Generator / Book Validator have no Phase 4 "
        "consumer of local-lite value strings. Canonical SourceMap has no "
        "independent 200-character cap. 209–213 character local values create "
        "no current downstream problem.",
        "",
        "## 10. Decision",
        "",
        f"SELECTED POLICY = {decision['selected_policy']}",
        f"PROPOSED LIMITS = theme {decision['proposed_limits']['theme']}, "
        f"EXAMPLE.v {decision['proposed_limits']['EXAMPLE.v']}, "
        f"IDEA.v {decision['proposed_limits']['IDEA.v']}.",
        "READY WIN001 already sits at theme=200 exactly and has IDEA.v=218>200, "
        "so a universal 200 was never the production contract.",
        "Do not implement in this phase. Wait for human review.",
        "",
        "## 11. Stop",
        "",
        "STOP. Do not modify production length policy. Do not retry WIN003. "
        "Do not call WIN005/WIN006/WIN007. Do not run grammar canary. "
        "Do not run consolidation. Do not publish source_map. "
        "Do not activate local-lite globally. Do not start Phase 4.",
        "",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["render_report"]
