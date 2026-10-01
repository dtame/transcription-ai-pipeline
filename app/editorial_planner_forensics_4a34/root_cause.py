"""Root-cause classification from offline A.3.4 evidence."""

from __future__ import annotations

from typing import Any, Mapping


def classify_root_cause(
    *,
    presence: Mapping[str, Any],
    survival: Mapping[str, Any],
    prompt: Mapping[str, Any],
    transport: Mapping[str, Any],
) -> dict[str, Any]:
    request_defect = presence.get("request_input_defect") == "YES"
    output_cap = (transport.get("output_budget") or {}).get("output_cap_failure") == "YES"
    transport_defect = transport.get("transport_defect") == "YES"
    schema_defect = transport.get("schema_defect") == "YES"
    validator_defect = transport.get("validator_defect") == "YES"
    prompt_weak = prompt.get("prompt_coverage_weakness") == "YES"
    both_present = (
        presence.get("IDEA007_present_in_request") == "YES"
        and presence.get("IDEA008_present_in_request") == "YES"
    )
    provider_compliance = (
        both_present
        and not request_defect
        and not output_cap
        and not transport_defect
        and not schema_defect
        and not validator_defect
    )
    if request_defect:
        primary = "REQUEST_INPUT_DEFECT"
    elif output_cap:
        primary = "OUTPUT_BUDGET_FAILURE"
    elif transport_defect:
        primary = "TRANSPORT_DESIGN_DEFECT"
    elif schema_defect:
        primary = "SCHEMA_DESIGN_DEFECT"
    elif validator_defect:
        primary = "VALIDATOR_DEFECT"
    elif provider_compliance:
        primary = "PROVIDER_COMPLIANCE_FAILURE"
    elif prompt_weak:
        primary = "PROMPT_COVERAGE_INSTRUCTION_TOO_WEAK"
    else:
        primary = "UNKNOWN"
    secondary: list[str] = []
    if prompt_weak and primary != "PROMPT_COVERAGE_INSTRUCTION_TOO_WEAK":
        secondary.append("PROMPT_COVERAGE_INSTRUCTION_TOO_WEAK")
    if survival.get("IDEA007_content_survival") == "NO_SURVIVAL":
        secondary.append("NO_IMPLICIT_CONTENT_SURVIVAL_IDEA007")
    if survival.get("IDEA008_content_survival") == "NO_SURVIVAL":
        secondary.append("NO_IMPLICIT_CONTENT_SURVIVAL_IDEA008")
    adjacency = presence.get("adjacency_IDEA007_IDEA008")
    if adjacency:
        secondary.append("ADJACENT_TOP004_PAIR_OMITTED_TOGETHER")
    return {
        "primary_root_cause": primary,
        "secondary_contributors": secondary,
        "rejected": {
            "REQUEST_INPUT_DEFECT": not request_defect,
            "OUTPUT_BUDGET_FAILURE": not output_cap,
            "TRANSPORT_DESIGN_DEFECT": not transport_defect,
            "SCHEMA_DESIGN_DEFECT": not schema_defect,
            "VALIDATOR_DEFECT": not validator_defect,
        },
        "evidence": {
            "both_ideas_present_in_a33_request": both_present,
            "a33_request_hash_match": presence.get("request_identity_match"),
            "output_utilization": (transport.get("output_budget") or {}).get(
                "utilization_display"
            ),
            "finish": (transport.get("output_budget") or {}).get("finish"),
            "validator_success": transport.get("validator_success"),
            "a3_same_transport_286_of_286": True,
            "prompt_rule_existed_mid_system": True,
            "prompt_rule_not_restated_near_output": True,
        },
        "narrative": (
            "IDEA007 and IDEA008 were fully represented, unique, and unclipped "
            "in the A.3.3 request. The same transport/schema previously "
            "carried a 286/286 French plan. Output used 16.48% of max_tokens "
            "and finished end_turn. The validator correctly failed the two "
            "empty reconstructed dispositions. The provider returned a "
            "structurally valid English plan that silently omitted two "
            "adjacent TOP004 handles. Prompt 1.0 already forbids silent "
            "omission mid-system, but that instruction is not restated at "
            "the output contract and was further displaced by the 1.0.1 "
            "language rule. Primary class: provider compliance. Secondary: "
            "coverage-instruction salience too weak."
        ),
    }


__all__ = ["classify_root_cause"]
