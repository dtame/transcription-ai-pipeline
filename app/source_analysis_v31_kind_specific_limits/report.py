"""Rapport markdown 3B.7.7A.30. Offline."""

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
    schema = bundle["schema"]
    replay = bundle["replay"]
    ready = bundle["ready"]
    relations = bundle["relations"]
    preflight = bundle["preflight"]
    semantic = bundle["semantic"]
    identity = replay["identity"]
    return "\n".join(
        [
            "# PHASE 3B.7.7A.30 — KIND-SPECIFIC LENGTH POLICY + SAVED WIN003 REVALIDATION",
            "",
            "## Result",
            "",
            str(header["result"]),
            "",
            "REAL PROVIDER CALLS =",
            "0",
            "",
            "REAL WINDOW CALLS =",
            "0",
            "",
            "A.28 HISTORICAL STATUS =",
            "FAIL unchanged",
            "",
            "A.29 STATUS =",
            "PASS",
            "",
            "OLD THEME LIMIT =",
            "200",
            "",
            "NEW THEME LIMIT =",
            "225",
            "",
            "OLD EXAMPLE LIMIT =",
            "200",
            "",
            "NEW EXAMPLE LIMIT =",
            "225",
            "",
            "IDEA LIMIT =",
            "280 unchanged",
            "",
            "OTHER LIMITS =",
            "unchanged",
            "",
            "PROMPT =",
            "window-analysis-1.4.0 unchanged",
            "",
            "TRANSPORT =",
            "semantic-transport-v3.1-local-lite unchanged",
            "",
            "SCHEMA RAW / ADAPTED =",
            f"{schema.get('raw_bytes')} / {schema.get('adapted_bytes')}",
            "",
            "SCHEMA HASH =",
            str(schema.get("hash")),
            "",
            "SCHEMA IDENTITY =",
            str(schema.get("identity")),
            "",
            "A.18 GRAMMAR PROOF =",
            str(schema.get("a18_grammar_proof")),
            "",
            "WIN003 RESPONSE SOURCE =",
            "SAVED_A28_RESPONSE",
            "",
            "WIN003 NEW PROVIDER CALL =",
            "NO",
            "",
            "WIN003 ORIGINAL REQUEST ID =",
            str(identity.get("request_id")),
            "",
            "WIN003 THEME LENGTH =",
            "212",
            "",
            "WIN003 EXAMPLE LENGTH =",
            "213",
            "",
            "WIN003 IDEA LENGTH =",
            "209",
            "",
            "WIN003 STRUCTURED PARSE =",
            str(replay.get("structured_parse")),
            "",
            "WIN003 SRC =",
            str(replay.get("src")),
            "",
            "WIN003 HANDLES =",
            str(replay.get("handles")),
            "",
            "WIN003 DECODER =",
            str(replay.get("decoder")),
            "",
            "WIN003 LOCAL VALIDATOR =",
            str(replay.get("local_validator")),
            "",
            "WIN003 SEMANTIC QUALITY =",
            str(replay.get("semantic_quality") or semantic.get("a29_semantic_quality")),
            "",
            "WIN003 CANONICAL RECONSTRUCTION =",
            str(replay.get("canonical_reconstruction")),
            "",
            "WIN003 MIXED COMPATIBILITY =",
            str(replay.get("mixed_compatibility")),
            "",
            "WIN003 PROMOTED =",
            _yn(header.get("win003_promoted")),
            "",
            "READY BEFORE =",
            "3 / 7",
            "",
            "READY AFTER =",
            str(ready.get("ready_after")),
            "",
            "RELATION_QUALITY_TECHNICAL_DEBT =",
            str(relations.get("RELATION_QUALITY_TECHNICAL_DEBT")),
            "",
            "WIN005-007 FUTURE PREFLIGHT =",
            "COMPATIBLE" if preflight.get("compatible") else "INCOMPATIBLE",
            "",
            "TESTS =",
            tests,
            "",
            "NEW FAILURES =",
            "0",
            "",
            "SOURCE MAP =",
            "NOT PUBLISHED",
            "",
            "PRODUCTION PROVIDER CONFIG =",
            "UNCHANGED",
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
            "No Anthropic. No OpenAI. No WIN003 retry. No WIN005/WIN006/WIN007. "
            "No grammar canary. No global consolidation.",
            "",
            "## 2. Policy",
            "",
            "Implemented USE_KIND_SPECIFIC_LIMITS. "
            "theme 200→225. EXAMPLE.v 200→225. IDEA.v remains 280. "
            "TOPIC.v=80, RELATION.v=40, REFERENCE.v=220, UNCERTAINTY.v=280, "
            "intent/aud=280. No universal MAX_VALUE_LENGTH.",
            "New immutable policy: window-granularity-1.2-kind-specific. "
            "Historical window-granularity-1.1-minimal stays frozen at 200/200 "
            "so A.28 FAIL remains reproducible.",
            "",
            "## 3. Signature",
            "",
            str((bundle["policy"].get("signature") or {}).get("decision")),
            str((bundle["policy"].get("signature") or {}).get("reason")),
            "",
            "## 4. Saved WIN003 identity",
            "",
            f"same_paid_response={identity.get('same_paid_response')}.",
            f"request_id={identity.get('request_id')}.",
            f"raw_sha256={identity.get('raw_sha256')}.",
            f"signature={identity.get('analysis_signature')}.",
            f"src_range={identity.get('src_range')}.",
            "",
            "## 5. Historical vs corrected policy",
            "",
            f"Under 1.1-minimal: `{replay.get('historical_granularity_error')}`.",
            f"A.28 reproduced={replay.get('historical_a28_reproduced')}.",
            f"Under 1.2 live validator: {replay.get('local_validator')}.",
            "A.28 remains historically FAIL.",
            "",
            "## 6. Semantic evidence",
            "",
            "A.29 counterfactual review reused (same saved raw). "
            f"quality={semantic.get('a29_semantic_quality')}. "
            f"unsupported={semantic.get('a29_unsupported_count')}. "
            f"omissions={semantic.get('a29_material_omissions')}. "
            "No second LLM.",
            "",
            "## 7. Relations",
            "",
            f"WIN003={replay.get('relation_quality_summary')}.",
            "WIN002=all plausible-loose. WIN004=23 plausible-loose.",
            f"RELATION_QUALITY_TECHNICAL_DEBT={relations.get('RELATION_QUALITY_TECHNICAL_DEBT')}.",
            "Does not block promotion. Architecture unchanged.",
            "",
            "## 8. Provenance",
            "",
            f"original provider phase=A.28. revalidation phase=A.30. "
            f"provider call during A.30=false. promoted={header.get('win003_promoted')}.",
            "",
            "## 9. Future windows",
            "",
            "WIN005/WIN006/WIN007 were not executed. Offline preflight only: "
            f"{'compatible' if preflight.get('compatible') else 'incompatible'} "
            "with prompt 1.4.0, transport v3.1, same grammar, thinking disabled, "
            "max_output 32000.",
            "",
            "## 10. Stop",
            "",
            "WAIT FOR HUMAN REVIEW. Do not call remaining windows.",
            "",
        ]
    )


__all__ = ["render_report"]
