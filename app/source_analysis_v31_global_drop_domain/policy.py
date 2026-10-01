"""Politique des kinds locaux sous transport 2.0 / prochain contrat. 0 provider."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_global_drop_domain.constants import (
    DROP_DOMAIN,
    DROP_REASONS_V20,
    GLOBAL_HANDLE_PREFIX_BY_KIND,
    LOCAL_HANDLE_KIND_LETTER,
)


OBJECT_KIND_POLICY: dict[str, dict[str, str]] = {
    "IDEA": {
        "treatment": "PROVIDER_REFERENCED",
        "accountability": "L_IDEA = M ∪ D; M ∩ D = ∅",
        "drop": "ONLY_KIND_ALLOWED_IN_DROP",
        "membership": "i[].m",
        "notes": "Every local IDEA id appears exactly once in membership or drop[].",
    },
    "TOPIC": {
        "treatment": "PROVIDER_REFERENCED",
        "accountability": "OPTIONAL_MEMBERSHIP_VIA_t[].m",
        "drop": "FORBIDDEN",
        "membership": "t[].m local TOPIC ids only",
        "notes": "Not part of L_IDEA. Absence from t[] is not a silent IDEA drop.",
    },
    "RELATION": {
        "treatment": "DEFERRED",
        "accountability": "IGNORED_BY_THIS_STAGE",
        "drop": "FORBIDDEN",
        "membership": "none",
        "notes": (
            "Local RELATION records are non-authoritative hints. "
            "They need no membership, no disposition, no DROP. "
            "Absence is not silent omission."
        ),
    },
    "EXAMPLE": {
        "treatment": "PROVIDER_REFERENCED",
        "accountability": "OPTIONAL_VIA_x[].l",
        "drop": "FORBIDDEN",
        "membership": "x[].l local EXAMPLE ids",
        "notes": "Provider may omit an example; that is not IDEA DROP.",
    },
    "REFERENCE": {
        "treatment": "PROVIDER_REFERENCED",
        "accountability": "OPTIONAL_VIA_f[].l",
        "drop": "FORBIDDEN",
        "membership": "f[].l local REFERENCE ids",
        "notes": "Provider may omit a reference; that is not IDEA DROP.",
    },
    "UNCERTAINTY": {
        "treatment": "PROVIDER_REFERENCED",
        "accountability": "OPTIONAL_VIA_u[].l",
        "drop": "FORBIDDEN",
        "membership": "u[].l local UNCERTAINTY ids",
        "notes": "Provider may omit an uncertainty; that is not IDEA DROP.",
    },
    "REPETITION": {
        "treatment": "IGNORED_BY_THIS_STAGE",
        "accountability": "LATER_OPTIONAL_ENRICHMENT",
        "drop": "FORBIDDEN",
        "membership": "none",
        "notes": "Do not emit REPETITION nodes in transport 2.0.",
    },
    "metadata": {
        "treatment": "PROVIDER_SYNTHESIZED",
        "accountability": "gm required",
        "drop": "FORBIDDEN",
        "membership": "none",
        "notes": "Global theme/intent/audience/voice only.",
    },
}


def local_object_kind_policy() -> dict[str, Any]:
    return {
        "drop_domain": DROP_DOMAIN,
        "drop_means": (
            "local IDEA inputs intentionally excluded from global IDEA membership "
            "for one of the narrowly allowed reasons"
        ),
        "drop_does_not_mean": "all local semantic records not represented globally",
        "allowed_drop_kinds": ["IDEA"],
        "forbidden_drop_kinds": [
            "TOPIC",
            "RELATION",
            "EXAMPLE",
            "REFERENCE",
            "UNCERTAINTY",
            "REPETITION",
            "metadata",
        ],
        "allowed_drop_reasons": list(DROP_REASONS_V20),
        "idea_accountability": {
            "L_IDEA": "all local IDEA IDs",
            "M": "union of all global IDEA member IDs",
            "D": "explicit IDEA drop IDs",
            "require": ["L_IDEA = M ∪ D", "M ∩ D = ∅"],
            "exclude_from_L_IDEA": [
                "TOPIC",
                "RELATION",
                "EXAMPLE",
                "REFERENCE",
                "UNCERTAINTY",
            ],
        },
        "no_universal_drop_ledger": True,
        "kinds": dict(OBJECT_KIND_POLICY),
        "handle_encoding": {
            "local_convention": "{namespace}:{kind_letter}{index}",
            "local_examples": {
                "IDEA": "SYN:I001 or SYN001:I12",
                "TOPIC": "SYN:T001",
                "EXAMPLE": "SYN:E001",
                "REFERENCE": "SYN:F001",
                "RELATION": "SYN:L001",
                "UNCERTAINTY": "SYN:U001",
            },
            "local_kind_letter": dict(LOCAL_HANDLE_KIND_LETTER),
            "global_handle_prefix": dict(GLOBAL_HANDLE_PREFIX_BY_KIND),
            "global_examples": "T1, I1, E1, F1, U1 — no R/L global handle; r[] retired",
            "relation_not_in_global_prefix_table": "RELATION uses local L; no global r[]",
            "kind_encoding_sufficient_for_human": True,
            "kind_encoding_not_a_schema_enum": True,
            "authoritative_kind_source": "local input k / kind_by_input, not ID spelling alone",
        },
        "exact_duplicate": "membership/merge, not DROP",
        "other": "RETIRED",
        "link_related": "RETIRED",
        "relations": "DEFERRED",
        "repetition": "later optional enrichment",
        "provider_disposition_ledger": False,
        "inverse_idea_membership": True,
        "derived_src_union": True,
    }


__all__ = ["OBJECT_KIND_POLICY", "local_object_kind_policy"]
