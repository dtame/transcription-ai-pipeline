"""Politique d'acceptation sémantique locale. Offline. Pas de seuil SRC brut."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v3_a25_forensics.constants import MODE, PHASE, SCHEMA_VERSION


def build_acceptance_policy(
    *,
    semantic: Mapping[str, Any],
    coverage: Mapping[str, Any],
    delta: Mapping[str, Any],
) -> dict[str, Any]:
    dimensions = {
        "no_material_unsupported_content": {
            "rule": "0 UNSUPPORTED records that invent or contradict CLEAN.",
            "a24": semantic.get("unsupported_content") == 0,
            "automated": True,
        },
        "no_material_distortion": {
            "rule": (
                "No record that attributes to the speaker a claim CLEAN does "
                "not support in substance. Paraphrase allowed."
            ),
            "automated": False,
            "reviewer": "human/offline forensic",
        },
        "major_substantive_ideas_sufficiently_represented": {
            "rule": (
                "Each major teaching of the window is represented, partial, or "
                "recoverable as a merged/compressed neighbor. Identical wording "
                "and identical record counts are not required."
            ),
            "automated": False,
            "needle_outline_is_diagnostic_only": True,
        },
        "no_beginning_middle_end_abandonment": {
            "rule": (
                "At least one substantive record is grounded in the first, "
                "middle, and last positional SRC bands. Not a coverage %."
            ),
            "a24": (
                f"{coverage.get('beginning')}/{coverage.get('middle')}/"
                f"{coverage.get('end')}"
            ),
            "automated": True,
        },
        "relations_sufficiently_grounded": {
            "rule": (
                "RELATION types ∈ vocabulary; targets are distinct IDEAs; "
                "no self-link. Semantic tightness is graded offline; loose "
                "thematic adjacency is allowed."
            ),
            "automated_structural": True,
            "automated_semantic": False,
        },
        "examples_source_grounded": {
            "rule": "EXAMPLE.s[] owned + text supported by cited CLEAN.",
            "automated_src": True,
            "automated_semantic": False,
        },
        "traceability_intact": {
            "rule": "Strict SRC tokens; symbolic handles; no numeric link indexes.",
            "automated": True,
        },
    }
    material_omission = {
        "definition": (
            "A material local omission is a distinct major teaching the speaker "
            "developed in this window that is neither represented as an IDEA/"
            "TOPIC nor recoverable from neighboring records as a merged or "
            "compressed restatement, such that a later reader of the local "
            "extraction would miss that teaching. Supporting illustrations, "
            "phrasing variants, and needle-only misses are not material."
        ),
        "not_material": [
            "lower IDEA/RELATION counts versus a prior stochastic run",
            "raw SRC coverage percentage",
            "absence of a specific diagnostic needle",
            "IDEA subtype mislabel when content is present",
        ],
        "audit_method": (
            "Use the diagnostic outline as a checklist, then confirm each "
            "'missing' row by reading IDEA/TOPIC/EXAMPLE text — not needles "
            "alone. Classify MINOR / MODERATE / MATERIAL."
        ),
        "a24_reported_missing_materiality": delta.get("major_idea_delta", {})
        .get("missing_idea_automated", {})
        .get("materiality"),
    }
    automated = [
        "unsupported content count",
        "beginning/middle/end band presence",
        "SRC lexical validity and ownership",
        "handle registry / resolution",
        "metadata vocabulary / cardinality",
        "RELATION structural shape",
        "capacity signal / finish reason / output ceiling",
    ]
    human = [
        "major-idea representation and materiality",
        "distortion versus CLEAN",
        "relation semantic tightness",
        "IDEA/EXAMPLE separation quality",
        "whether a needle miss is a true omission",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "policy_id": "LOCAL_EXTRACTION_SEMANTIC_ACCEPTANCE_V1",
        "status": "DEFINED",
        "stochastic_identity_not_required": True,
        "raw_src_coverage_threshold": None,
        "minimum_record_counts": None,
        "do_not_use_raw_coverage_threshold": True,
        "do_not_require_record_count": True,
        "dimensions": dimensions,
        "material_omission": material_omission,
        "future_automated_gate": {
            "deterministic_now": automated,
            "require_human_or_offline_review": human,
        },
        "acceptance_for_remaining_windows": (
            "A local window may be semantically acceptable for extraction "
            "when transport is valid AND the dimensions above pass, even if "
            "record counts differ from WIN001/WIN004 priors."
        ),
        "a24_application_note": (
            "A.24 fails the transport-validity gate. Independently of "
            "metadata, it would pass this semantic policy: 0 unsupported, "
            "B/M/E intact, Fall present despite needle miss, fingerprint "
            "partial is not material abandonment."
        ),
    }


__all__ = ["build_acceptance_policy"]
