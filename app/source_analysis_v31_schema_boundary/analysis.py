"""Inventaire schema.py + carte des frontières. Offline. 0 provider."""

from __future__ import annotations

import inspect
from typing import Any

from app.source_analysis.analyzer import STAGE as GLOBAL_STAGE
from app.source_analysis.analyzer import analyze_source
from app.source_analysis.compact_schema import build_compact_response_schema
from app.source_analysis.consolidation_analyzer import consolidate
from app.source_analysis.consolidation_schema import build_consolidation_response_schema
from app.source_analysis.models import Idea
from app.source_analysis.schema import build_response_schema
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis.window_analyzer import analyze_window
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v31_local_lite_schema,
)
from app.source_analysis_v31_schema_boundary.constants import (
    ABSENCE_REPRESENTATION,
    A27_AUTHORIZATION,
    BLOCKS_A27,
    CANONICAL_IDEA_SUBTYPE,
    GLOBAL_IDEA_SUBTYPE_STRATEGY,
    LOCAL_IDEA_METADATA,
    LOCAL_IDEA_SUBTYPE,
    MISMATCH_CLASSIFICATION,
    MODE,
    OPTIONAL_KIND_SEMANTICS,
    PHASE,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    TRANSPORT_VERSION,
)


def _idea_schema() -> dict[str, Any]:
    return build_response_schema()["properties"]["ideas"]["items"]


def schema_py_role() -> dict[str, Any]:
    idea = _idea_schema()
    return {
        "module": "app/source_analysis/schema.py",
        "constructor": "build_response_schema",
        "docstring_states": (
            "Ce schéma décrit la RÉPONSE DU MODÈLE, pas le fichier publié."
        ),
        "boundary": "OLD_GLOBAL_SOURCE_ANALYZER_PROVIDER_STRUCTURED_OUTPUT",
        "not": [
            "canonical SourceMap schema",
            "publication validator",
            "local-lite transport",
            "global consolidation transport",
        ],
        "ideas_kind_required": "kind" in idea.get("required", []),
        "ideas_kind_enum": list(idea["properties"]["kind"]["enum"]),
        "empty_string_in_enum": "" in idea["properties"]["kind"]["enum"],
        "why_required": (
            "Generation A global Source Analyzer asked the LLM to classify "
            "idea.kind locally in the same structured object as importance. "
            "That is a provider-output grammar, not the published-file contract."
        ),
    }


def consumer_inventory() -> dict[str, Any]:
    analyzer_src = inspect.getsource(analyze_source)
    window_src = inspect.getsource(analyze_window)
    consolidation_src = inspect.getsource(consolidate)
    return {
        "who_constructs": "app.source_analysis.schema.build_response_schema",
        "which_airequest_uses_it_in_production": "NONE",
        "which_prompt_stage_historically": {
            "stage": GLOBAL_STAGE,
            "prompt_version": "SOURCE_ANALYZER_PROMPT_VERSION (currently 1.3)",
            "status": (
                "Historical Generation A global analyzer schema. "
                "Current analyze_source / preflight attach ultra-compact, "
                "not schema.py."
            ),
        },
        "used_for_local_window_extraction": False,
        "used_for_global_consolidation": False,
        "used_for_final_sourcemap_generation": False,
        "used_for_publication_validation": False,
        "only_provider_structured_output_grammar": True,
        "reconstructed_local_lite_passes_through_it": False,
        "production_runtime": {
            "analyzer.py": {
                "ai_request_schema": "build_ultra_compact_response_schema",
                "uses_schema_py": "build_response_schema()" in analyzer_src,
                "stage": GLOBAL_STAGE,
            },
            "window_analyzer.py": {
                "ai_request_schema": "build_ultra_compact_response_schema",
                "uses_schema_py": "build_response_schema()" in window_src,
                "stage": STAGE_WINDOW,
            },
            "consolidation_analyzer.py": {
                "ai_request_schema": "build_consolidation_response_schema",
                "uses_schema_py": "build_response_schema()" in consolidation_src,
            },
            "local_v3.pipeline.build_v140_window_request": {
                "ai_request_schema": "build_semantic_transport_v31_local_lite_schema",
                "prompt": PROMPT_VERSION,
                "transport": TRANSPORT_VERSION,
                "stage": STAGE_WINDOW,
                "uses_schema_py": False,
            },
            "real_run.py": {
                "role": (
                    "Fingerprints schema.py as canonical_schema_sha256 only. "
                    "The AIRequest itself uses ultra-compact from preflight."
                ),
                "attaches_schema_py_to_request": False,
            },
        },
        "non_production_canaries_that_may_replace_request_schema": [
            "app/source_analysis_schema_canary/runner.py",
            "app/source_analysis_ultra_compact_canary/runner.py",
            "app/source_analysis_vocabulary_compliance_canary/runner.py",
            "app/source_analysis_global_clean/runner.py",
        ],
        "not_source_analysis_schema": [
            "app/semantic_canary/schema.py.build_response_schema",
            "app/semantic_batch/runner.py (uses semantic_canary schema)",
        ],
        "sibling_generation_b_also_requires_kind": {
            "module": "app/source_analysis/compact_schema.py",
            "field": "ideas[].kind",
            "required": True,
            "used_by_local_lite": False,
            "used_by_current_analyzer": False,
        },
        "a27_path_cannot_hit_schema_py": True,
    }


def pipeline_contract_map() -> list[dict[str, Any]]:
    return [
        {
            "boundary": "local provider output",
            "schema": "semantic-transport-v3.1-local-lite (wire-identical to v3; 588/650)",
            "idea_kind_exists": False,
            "idea_kind_required": False,
            "empty_string_valid": "N/A — field absent; m=[importance] only",
            "who_assigns": "provider writes m[0]=importance; no subtype token",
        },
        {
            "boundary": "transport decoder",
            "schema": "decode_v31_local_lite_transport / _validate_idea_payload_v31",
            "idea_kind_exists": False,
            "idea_kind_required": False,
            "empty_string_valid": "N/A",
            "who_assigns": (
                "decoder keeps m as [importance]; rejects arity≠1, "
                "rejects IDEA_KINDS tokens in m[0], rejects empty m"
            ),
        },
        {
            "boundary": "local normalized representation",
            "schema": "WindowIntermediateRecord.metadata",
            "idea_kind_exists": False,
            "idea_kind_required": False,
            "empty_string_valid": "N/A",
            "who_assigns": "metadata = (importance,)",
        },
        {
            "boundary": "historical V3 transport (not local-lite)",
            "schema": "semantic-transport-v3 + decode_v3_transport",
            "idea_kind_exists": True,
            "idea_kind_required": True,
            "empty_string_valid": False,
            "who_assigns": "provider m=[kind, importance]; decoder validates kind ∈ IDEA_KINDS",
        },
        {
            "boundary": "V3 → local-lite normalization",
            "schema": "normalize_v3_transport_to_local_lite",
            "idea_kind_exists": False,
            "idea_kind_required": False,
            "empty_string_valid": "N/A",
            "who_assigns": (
                "DROP_OPTIONAL_LOCAL_IDEA_SUBTYPE; keeps importance; "
                "does not invent a replacement kind"
            ),
        },
        {
            "boundary": "consolidation",
            "schema": "build_consolidation_response_schema / ConsolidationNode.kind",
            "idea_kind_exists": False,
            "idea_kind_required": False,
            "empty_string_valid": "N/A",
            "who_assigns": (
                "node.kind is record class (IDEA/TOPIC/…), not IDEA subtype. "
                "GLOBALIZE_IDEA_SUBTYPE A.26 does not classify globally."
            ),
        },
        {
            "boundary": "reconstruction",
            "schema": "hybrid_reconstructor._idea_raw_local_lite",
            "idea_kind_exists": True,
            "idea_kind_required": False,
            "empty_string_valid": True,
            "who_assigns": "reconstructor sets kind=''; copies m[0] to importance only",
        },
        {
            "boundary": "historical V3 reconstruction",
            "schema": "hybrid_reconstructor._idea_raw",
            "idea_kind_exists": True,
            "idea_kind_required": True,
            "empty_string_valid": False,
            "who_assigns": "copies local m[0] as kind, m[1] as importance",
        },
        {
            "boundary": "canonical SourceMap Python model",
            "schema": "app.source_analysis.models.Idea",
            "idea_kind_exists": True,
            "idea_kind_required": False,
            "empty_string_valid": True,
            "who_assigns": (
                "from_dict/_read_text: absent or null → ''; "
                "normalizer copies raw kind without inventing a default enum"
            ),
        },
        {
            "boundary": "validator",
            "schema": "validate_source_map / ensure_valid_source_map",
            "idea_kind_exists": True,
            "idea_kind_required": False,
            "empty_string_valid": True,
            "who_assigns": (
                "empty kind accepted; non-empty must be IDEA_KINDS; "
                "importance required and must be IMPORTANCE_LEVELS"
            ),
        },
        {
            "boundary": "serialization / publication",
            "schema": "Idea.to_dict / SourceMap.to_dict / write_source_map",
            "idea_kind_exists": True,
            "idea_kind_required": False,
            "empty_string_valid": True,
            "who_assigns": "always emits 'kind': '' when empty; does not omit the key",
        },
        {
            "boundary": "schema.py (Generation A provider grammar)",
            "schema": "build_response_schema ideas[].kind",
            "idea_kind_exists": True,
            "idea_kind_required": True,
            "empty_string_valid": False,
            "who_assigns": (
                "LLM would have been required to emit a closed IDEA_KINDS token. "
                "Not applied to reconstructed local-lite maps. Not a publication gate."
            ),
        },
    ]


def globalize_meaning() -> dict[str, Any]:
    return {
        "selected_architecture": SELECTED_ARCHITECTURE,
        "a26_implementation": GLOBAL_IDEA_SUBTYPE_STRATEGY,
        "local_idea_subtype": LOCAL_IDEA_SUBTYPE,
        "local_idea_metadata": LOCAL_IDEA_METADATA,
        "canonical_idea_subtype": CANONICAL_IDEA_SUBTYPE,
        "actual": (
            "Local subtype absent. Global consolidation does not assign a "
            "subtype. Canonical kind is optional and left empty."
        ),
        "not_implemented": (
            "local subtype absent / global consolidation classifies subtype"
        ),
        "why_not_classify_globally": (
            "A.26 chose A_ABSENT_IF_OPTIONAL because the canonical field is "
            "optional and no Phase 4 consumer requires it. Do not invent a "
            "fallback category. Do not add an LLM classification task."
        ),
    }


def optional_kind_semantics() -> dict[str, Any]:
    absent = Idea.from_dict(
        {
            "idea_id": "IDEA001",
            "summary": "Faith changes the crossing.",
            "importance": "central",
            "source_refs": ["SRC000001"],
        }
    )
    empty = Idea.from_dict(
        {
            "idea_id": "IDEA001",
            "summary": "Faith changes the crossing.",
            "kind": "",
            "importance": "central",
            "source_refs": ["SRC000001"],
        }
    )
    nulled = Idea.from_dict(
        {
            "idea_id": "IDEA001",
            "summary": "Faith changes the crossing.",
            "kind": None,
            "importance": "central",
            "source_refs": ["SRC000001"],
        }
    )
    return {
        "current_contract": OPTIONAL_KIND_SEMANTICS,
        "absence_representation": ABSENCE_REPRESENTATION,
        "from_dict_absent": absent.kind,
        "from_dict_empty": empty.kind,
        "from_dict_null": nulled.kind,
        "to_dict_always_includes_key": "kind" in empty.to_dict(),
        "to_dict_empty_value": empty.to_dict()["kind"],
        "decision": (
            "Repository contracts already chose A: field present with empty "
            "string. Absent and null collapse to '' on read. Do not change."
        ),
        "compatibility": {
            "omit_or_null_on_reload": (
                "SourceMap.from_dict treats missing/null kind as ''. "
                "Round-trip of a file that omitted kind would still load, "
                "then re-serialize as 'kind': ''."
            ),
            "if_future_publication_schema_reuses_schema_py": (
                "Published local-lite maps would fail ideas[].kind enum. "
                "That is misuse of a provider grammar as a publication schema."
            ),
            "if_later_phase_wants_omitted_null": (
                "That would be a new serialization contract, not a fix of "
                "schema.py. Do not change production in this audit."
            ),
        },
        "do_not_change_yet": True,
    }


def classification() -> dict[str, Any]:
    idea = _idea_schema()
    ultra = build_ultra_compact_response_schema()
    compact = build_compact_response_schema()
    consolidation = build_consolidation_response_schema()
    local_lite = build_semantic_transport_v31_local_lite_schema()
    return {
        "mismatch_classification": MISMATCH_CLASSIFICATION,
        "blocks_a27": BLOCKS_A27,
        "a27_authorization": A27_AUTHORIZATION,
        "why": (
            "schema.py is the Generation A global LLM response grammar. "
            "It still correctly requires ideas[].kind for that stage. "
            "Local-lite reconstruction, the Python Idea model, and "
            "ensure_valid_source_map are a different boundary where kind "
            "is optional. A.27 uses window-analysis-1.4.0 + "
            "semantic-transport-v3.1-local-lite and cannot hit schema.py."
        ),
        "rejected_classifications": {
            "FUTURE_INTEGRATION_DEBT_NOT_BLOCKING_A27": (
                "Rejected as the primary class: the two schemas are "
                "intentionally stage-specific. Residual naming debt "
                "(real_run.canonical_schema_sha256 fingerprints schema.py) "
                "is documented, not a contract bug."
            ),
            "BLOCKING_CANONICAL_CONTRACT_MISMATCH": (
                "Rejected: reconstructed local-lite data never enters "
                "schema.py. Publication validation does not use schema.py."
            ),
        },
        "schema_py_used_by_local_lite": False,
        "schema_py_used_by_global_consolidation": False,
        "schema_py_used_by_publication": False,
        "current_schemas_are_distinct": {
            "schema.py_has_ideas_kind": True,
            "ultra_compact_has_ideas_collection": "ideas" not in ultra.get("required", []),
            "compact_has_ideas_kind": "kind"
            in compact["properties"]["ideas"]["items"]["required"],
            "consolidation_is_not_schema_py": consolidation != build_response_schema(),
            "local_lite_has_ideas_kind_field": "ideas" not in local_lite.get("properties", {}),
        },
        "schema_py_kind_required": "kind" in idea.get("required", []),
        "do_not_modify_schema_py": True,
        "do_not_change_588_650_grammar": True,
    }


def downstream_consumers() -> dict[str, Any]:
    return {
        "editorial_planner": {
            "implemented": False,
            "consumes_idea_kind": False,
            "evidence": (
                "No Phase 4 Editorial Planner module exists. "
                "app/editorial_*.py are V1 rewrite helpers and do not read "
                "SourceMap ideas. A.25/A.26 recorded dependency=NONE."
            ),
        },
        "book_generator": {
            "implemented": False,
            "consumes_idea_kind": False,
            "evidence": (
                "No Book Generator consumer of Idea.kind exists. "
                "app/book/transcript_parser.py does not read source_map."
            ),
        },
        "book_validator": {
            "implemented": False,
            "consumes_idea_kind": False,
            "evidence": (
                "Book Validator is named only in app/ai contracts as a future "
                "stage. No implementation reads Idea.kind."
            ),
        },
    }


def build_boundary_analysis() -> dict[str, Any]:
    role = schema_py_role()
    consumers = consumer_inventory()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "schema_py_role": role,
        "consumers": consumers,
        "pipeline": pipeline_contract_map(),
        "globalize": globalize_meaning(),
        "optional_kind_semantics": optional_kind_semantics(),
        "classification": classification(),
        "downstream": downstream_consumers(),
        "answers": {
            "who_constructs": consumers["who_constructs"],
            "which_airequest": consumers["which_airequest_uses_it_in_production"],
            "which_prompt_stage": consumers["which_prompt_stage_historically"],
            "used_for_local_window_extraction": False,
            "used_for_global_consolidation": False,
            "used_for_final_sourcemap_generation": False,
            "used_for_publication_validation": False,
            "only_provider_structured_output_grammar": True,
            "reconstructed_local_lite_passes_through_it": False,
        },
    }


__all__ = [
    "build_boundary_analysis",
    "classification",
    "consumer_inventory",
    "downstream_consumers",
    "globalize_meaning",
    "optional_kind_semantics",
    "pipeline_contract_map",
    "schema_py_role",
]
