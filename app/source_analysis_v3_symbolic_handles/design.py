"""Audit de design — représentation choisie et alternatives rejetées."""

from __future__ import annotations

from typing import Any

from app.source_analysis_local_v3.constants import (
    FORWARD_REFERENCES,
    GAP_FREE_NUMBERING,
    GLOBAL_NUMERIC_LINK_INDEXES,
    HANDLE_INDEX_BASE,
    HANDLE_LINK_IDEA_KINDS,
    HANDLE_LINK_TOPIC_KINDS,
    HANDLE_OWNER_KINDS,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SEMANTIC_TRANSPORT_VERSION_V3,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
)
from app.source_analysis_local_v3.links import link_contract


def build_design_audit() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
        "handle_index_base": HANDLE_INDEX_BASE,
        "global_numeric_link_indexes": GLOBAL_NUMERIC_LINK_INDEXES,
        "forward_references": FORWARD_REFERENCES,
        "gap_free_numbering": GAP_FREE_NUMBERING,
        "owner_kinds": list(HANDLE_OWNER_KINDS),
        "link_t_kinds": list(HANDLE_LINK_TOPIC_KINDS),
        "link_i_kinds": list(HANDLE_LINK_IDEA_KINDS),
        "wire_representation": {
            "selected": "A_explicit_owner_h_plus_string_l",
            "record_shape": {"k": "str", "v": "str", "s": ["SRC"], "h": "T1|I1|", "l": ["Tn|In"], "m": ["meta"]},
            "h": "explicit owner handle; empty string for non-owners",
            "l": "string-handle array; never integers",
            "not_selected": {
                "B_reuse_existing_field": (
                    "Rejected: v/s/k already have coherent meanings. "
                    "Reusing them would hide ownership."
                ),
                "C_replace_l_with_new_t": (
                    "Rejected: renaming l to t adds churn without a new concept. "
                    "Keeping l as the link field preserves decoder familiarity."
                ),
                "D_handles_in_m": (
                    "Rejected: m must retain kind-specific metadata "
                    "(summary / kind / importance). Putting handles in m "
                    "would be a schema-avoidance hack."
                ),
                "I37_alias": (
                    "Rejected: prefixing a global index as I37 keeps the "
                    "hidden global-index problem."
                ),
            },
            "why_not_m": (
                "Ownership is a new semantic concept in the wire contract. "
                "It is represented explicitly by h."
            ),
        },
        "python_role": {
            "may": [
                "validate symbolic references",
                "resolve handles deterministically",
                "map local handles to transport/canonical structures",
                "assign canonical IDs",
            ],
            "may_not": [
                "decide semantic relationships",
                "invent missing links",
                "choose a better idea target",
                "merge ideas semantically",
                "guess nearest IDEA",
                "repair typos",
                "convert T3 to I3",
            ],
        },
        "llm_role": [
            "identify semantic entities",
            "classify semantic entities",
            "decide semantic relationships",
            "assign local T/I labels",
        ],
        "link_contract": link_contract(),
        "historical_freeze": [
            "semantic-transport-v1",
            "semantic-transport-v2",
            "window-analysis-1.0",
            "window-analysis-1.1",
            "window-analysis-1.2",
            "window-analysis-1.2.1",
        ],
        "a15_not_repaired": True,
        "canonical_sourcemap_unchanged": True,
    }


__all__ = ["build_design_audit"]
