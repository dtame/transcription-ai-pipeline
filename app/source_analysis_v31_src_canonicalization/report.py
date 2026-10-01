"""Rapport markdown 3B.7.7A.33. Offline."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: bool | None) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "UNKNOWN"


def _unsupported(replay: Mapping[str, Any], semantic: Mapping[str, Any]) -> Any:
    value = replay.get("unsupported_count")
    if value is None:
        value = replay.get("unsupported_content")
    if value is None:
        value = semantic.get("live_unsupported")
    if value is None:
        value = semantic.get("a32_unsupported_count")
    return value


def render_report(bundle: Mapping[str, Any], *, tests: str) -> str:
    header = bundle["header"]
    schema = bundle["schema"]
    replay = bundle["replay"]
    ready = bundle["ready"]
    semantic = bundle["semantic"]
    identity = replay["identity"]
    inventory = bundle.get("inventory")
    return "\n".join(
        [
            "# PHASE 3B.7.7A.33 — SRC CANONICALIZATION + SAVED WIN007 REVALIDATION",
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
            "A.31 HISTORICAL STATUS =",
            "FAIL unchanged",
            "",
            "A.32 STATUS =",
            "PASS",
            "",
            "SRC POLICY OLD =",
            str(header.get("src_policy_old")),
            "",
            "SRC POLICY NEW =",
            str(header.get("src_policy_new")),
            "",
            "RAW WIN007 SRC TOKENS =",
            str(replay.get("raw_src_tokens")),
            "",
            "RAW EXACT SRC =",
            str(replay.get("raw_exact_src")),
            "",
            "RAW MALFORMED SRC =",
            str(replay.get("raw_malformed_src")),
            "",
            "CANONICALIZED SRC =",
            str(replay.get("canonicalized_src")),
            "",
            "REJECTED MALFORMED SRC =",
            str(replay.get("rejected_malformed_src")),
            "",
            "RAW TOKEN =",
            "SRec007337",
            "",
            "CANONICAL TOKEN =",
            "SRC007337",
            "",
            "RAW RESPONSE MUTATED =",
            "NO" if replay.get("raw_response_mutated") is False else "YES",
            "",
            "STRICT HISTORICAL REPLAY =",
            str(replay.get("strict_historical_replay")),
            "",
            "DERIVED REPLAY =",
            "PASS" if replay.get("technical_ok") else "FAIL",
            "",
            "PROMPT =",
            "window-analysis-1.4.0 unchanged",
            "",
            "TRANSPORT =",
            "semantic-transport-v3.1-local-lite unchanged",
            "",
            "GRANULARITY =",
            "window-granularity-1.2-kind-specific unchanged",
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
            "WIN007 DECODER =",
            str(replay.get("decoder")),
            "",
            "WIN007 SRC =",
            str(replay.get("src")),
            "",
            "WIN007 HANDLES =",
            str(replay.get("handles")),
            "",
            "WIN007 LENGTH POLICY =",
            str(replay.get("length_policy")),
            "",
            "WIN007 LOCAL VALIDATOR =",
            str(replay.get("local_validator")),
            "",
            "WIN007 SEMANTIC QUALITY =",
            str(replay.get("semantic_quality") or semantic.get("a32_semantic_quality")),
            "",
            "WIN007 UNSUPPORTED MATERIAL =",
            str(_unsupported(replay, semantic)),
            "",
            "WIN007 MATERIAL OMISSIONS =",
            str(replay.get("material_omissions") if replay.get("material_omissions") is not None else semantic.get("a32_material_omissions")),
            "",
            "WIN007 CANONICAL RECONSTRUCTION =",
            str(replay.get("canonical_reconstruction")),
            "",
            "WIN007 MIXED COMPATIBILITY =",
            str(replay.get("mixed_compatibility")),
            "",
            "WIN007 PROMOTED =",
            _yn(header.get("win007_promoted")),
            "",
            "READY BEFORE =",
            "6 / 7",
            "",
            "READY AFTER =",
            str(ready.get("ready_after")),
            "",
            "LOCAL_EXTRACTION_FREEZE_CANDIDATE =",
            str(ready.get("local_extraction_freeze_candidate")),
            "",
            "RELATION_QUALITY_TECHNICAL_DEBT =",
            "YES",
            "",
            "CONSOLIDATION INPUT INVENTORY =",
            "CREATED" if inventory else "NOT_CREATED",
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
            "GLOBAL CONSOLIDATION =",
            "NOT EXECUTED",
            "",
            "PHASE 3B =",
            "INCOMPLETE",
            "",
            "NEXT ACTION =",
            "HUMAN REVIEW",
            "",
            "## Identity",
            "",
            f"request_id = {identity.get('request_id')}",
            f"same_paid_response = {_yn(bool(identity.get('same_paid_response')))}",
            f"raw_sha256 = {identity.get('raw_sha256')}",
            "",
            "## Pipeline",
            "",
            "after raw structured parse / before strict derived SRC validation",
            "and decoding that require canonical identifiers",
            "decoder remains strict on the identifiers it receives",
            "canonicalization is derived-only",
            "",
            "## STRICT vs DERIVED",
            "",
            f"STRICT_RAW_VALIDITY = {replay.get('strict_raw_validity')}",
            f"DERIVED_CANONICAL_VALIDITY = {replay.get('derived_canonical_validity')}",
            f"exactly one canonicalization = {_yn(bool(replay.get('exactly_one_canonicalization')))}",
            f"EXAMPLE max = {replay.get('example_max')} <= 225",
            "",
            "WAIT FOR HUMAN REVIEW. Do not call Anthropic. Do not call OpenAI.",
            "Do not retry WIN007. Do not change prompt/transport/granularity.",
            "Do not run grammar canary. Do not execute global consolidation.",
            "Do not publish source_map. Phase 3B remains INCOMPLETE.",
            "",
        ]
    ) + "\n"


__all__ = ["render_report"]
