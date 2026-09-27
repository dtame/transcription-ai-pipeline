"""Rapport 3B.7.7A.26.1."""

from __future__ import annotations

from typing import Any, Mapping


def render_report(
    *,
    header: Mapping[str, Any],
    boundary: Mapping[str, Any],
    roundtrip: Mapping[str, Any],
    mixed: Mapping[str, Any],
    a27: Mapping[str, Any],
    isolation: Mapping[str, Any],
    tests: str,
) -> str:
    role = boundary.get("schema_py_role") or {}
    consumers = boundary.get("consumers") or {}
    classification = boundary.get("classification") or {}
    globalize = boundary.get("globalize") or {}
    semantics = boundary.get("optional_kind_semantics") or {}
    downstream = boundary.get("downstream") or {}
    publication = roundtrip.get("publication_gates") or {}
    contamination = roundtrip.get("importance_never_becomes_kind") or {}
    lines = [
        "# PHASE 3B.7.7A.26.1 — LOCAL-LITE CANONICAL SCHEMA BOUNDARY",
        "",
        "## Result",
        "",
        str(header.get("result")),
        "",
        f"REAL PROVIDER CALLS = {header.get('real_provider_calls')}",
        "",
        f"REAL WINDOW CALLS = {header.get('real_window_calls')}",
        "",
        f"A.26 STATUS = {header.get('a26_status')}",
        "",
        f"schema.py ROLE = {header.get('schema_py_role')}",
        "",
        f"schema.py USED BY LOCAL-LITE = {header.get('schema_py_used_by_local_lite')}",
        "",
        f"schema.py USED BY GLOBAL CONSOLIDATION = {header.get('schema_py_used_by_global_consolidation')}",
        "",
        f"schema.py USED BY PUBLICATION = {header.get('schema_py_used_by_publication')}",
        "",
        f"CANONICAL kind OPTIONAL = {header.get('canonical_kind_optional')}",
        "",
        f"EMPTY kind VALID = {header.get('empty_kind_valid')}",
        "",
        f"EMPTY kind SERIALIZATION = {header.get('empty_kind_serialization')}",
        "",
        f"IMPORTANCE→KIND CONTAMINATION = {header.get('importance_to_kind_contamination')}",
        "",
        f"LOCAL-LITE ROUNDTRIP = {header.get('local_lite_roundtrip')}",
        "",
        f"MIXED V3/V3.1 = {header.get('mixed_v3_v31')}",
        "",
        f"MISMATCH CLASSIFICATION = {header.get('mismatch_classification')}",
        "",
        f"BLOCKS A.27 = {header.get('blocks_a27')}",
        "",
        f"PRODUCTION CHANGED = {header.get('production_changed')}",
        "",
        f"SOURCE MAP = {header.get('source_map')}",
        "",
        f"REAL WINDOWS READY = {header.get('real_windows_ready')}",
        "",
        f"PHASE 3B = {header.get('phase_3b')}",
        "",
        f"TESTS = {header.get('tests')}",
        "",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Historical status",
        "",
        f"A.19 = {header.get('a19')}",
        f"A.21 = {header.get('a21')}",
        f"A.22 = {header.get('a22')}",
        f"A.23 = {header.get('a23')}",
        f"A.24 = {header.get('a24')}",
        f"A.25 = {header.get('a25')}",
        f"A.26 = {header.get('a26')} unchanged",
        "",
        "## schema.py",
        "",
        f"Constructor = {role.get('constructor')}.",
        f"Boundary = {role.get('boundary')}.",
        f"Docstring = {role.get('docstring_states')}",
        f"ideas[].kind required = {role.get('ideas_kind_required')}.",
        f"empty string in enum = {role.get('empty_string_in_enum')}.",
        f"Why required = {role.get('why_required')}",
        "",
        "## Answers",
        "",
        f"Who constructs = {consumers.get('who_constructs')}.",
        f"Which AIRequest uses it in production = {consumers.get('which_airequest_uses_it_in_production')}.",
        f"Historical prompt/stage = {consumers.get('which_prompt_stage_historically')}.",
        f"Local window extraction = {consumers.get('used_for_local_window_extraction')}.",
        f"Global consolidation = {consumers.get('used_for_global_consolidation')}.",
        f"Final SourceMap generation = {consumers.get('used_for_final_sourcemap_generation')}.",
        f"Publication validation = {consumers.get('used_for_publication_validation')}.",
        f"Only provider structured-output grammar = {consumers.get('only_provider_structured_output_grammar')}.",
        f"Reconstructed local-lite passes through it = {consumers.get('reconstructed_local_lite_passes_through_it')}.",
        "",
        "## GLOBALIZE_IDEA_SUBTYPE",
        "",
        f"Architecture = {globalize.get('selected_architecture')}.",
        f"A.26 strategy = {globalize.get('a26_implementation')}.",
        f"Actual = {globalize.get('actual')}",
        f"Not implemented = {globalize.get('not_implemented')}.",
        "",
        "## Optional kind semantics",
        "",
        f"Current contract = {semantics.get('current_contract')}.",
        f"Decision = {semantics.get('decision')}",
        f"Compatibility if schema.py reused as publication schema = "
        f"{(semantics.get('compatibility') or {}).get('if_future_publication_schema_reuses_schema_py')}",
        "",
        "## Downstream",
        "",
        f"Editorial Planner = {(downstream.get('editorial_planner') or {}).get('evidence')}",
        f"Book Generator = {(downstream.get('book_generator') or {}).get('evidence')}",
        f"Book Validator = {(downstream.get('book_validator') or {}).get('evidence')}",
        "",
        "## Publication",
        "",
        (
            f"kind='' passes implemented gates = "
            f"{publication.get('would_pass_every_implemented_publication_gate')}. "
            f"Failing boundary = {publication.get('failing_boundary')}. "
            f"Published = {publication.get('source_map_published')}."
        ),
        "",
        "## Roundtrip",
        "",
        (
            f"Result = {roundtrip.get('result')}. "
            f"All kinds empty = {roundtrip.get('all_kinds_empty')}. "
            f"Serialized as empty string = {roundtrip.get('serialized_kind_empty_string')}. "
            f"schema.py rejects empty kind = "
            f"{(roundtrip.get('schema_py_rejects_empty_kind') or {}).get('empty_kind_rejected_by_schema_py')}."
        ),
        "",
        "## Mixed V3 / V3.1",
        "",
        (
            f"Result = {mixed.get('result')}. "
            f"Common path = {mixed.get('common_path')}. "
            f"Old V3 rejected under local-lite decoder = "
            f"{mixed.get('old_v3_rejected_under_local_lite_decoder')}."
        ),
        "",
        "## Critical contamination",
        "",
        (
            f"importance=central became kind=central = "
            f"{contamination.get('contamination')}. "
            f"Local-lite reconstructor kind = "
            f"{(contamination.get('local_lite_reconstructor') or {}).get('kind')}."
        ),
        "",
        "## A.27 path",
        "",
        (
            f"Authorization = {header.get('a27_authorization')}. "
            f"Hits schema.py = {a27.get('a27_hits_schema_py')}. "
            f"Prompt = {a27.get('prompt_version')}. "
            f"Transport = {a27.get('transport_version')}."
        ),
        "",
        "## Classification",
        "",
        f"{classification.get('mismatch_classification')}: {classification.get('why')}",
        "",
        "## Isolation",
        "",
        (
            f"Provider calls = {isolation.get('real_provider_calls')}. "
            f"Window calls = {isolation.get('real_window_calls')}. "
            f"schema.py untouched = {isolation.get('schema_py_untouched')}. "
            f"Historical hashes intact = {isolation.get('historical_hashes_intact')}."
        ),
        "",
        f"Tests = {tests}.",
        "",
        "WAIT FOR HUMAN REVIEW. Do not execute A.27. Do not call Anthropic.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
