"""Contrat officiel Claude Sonnet 5 — faits externes vérifiés. 0 fetch."""

from __future__ import annotations

from typing import Any

from app.ai.thinking import (
    KNOWN_EFFORTS,
    SONNET5_THINKING_CAPABILITIES,
)
from app.source_analysis_thinking_contract.constants import (
    MODE,
    MODEL,
    OFFICIAL_SOURCE_NOTES,
    OFFICIAL_SOURCE_URLS,
    OFFICIAL_VERIFICATION_DATE,
    PHASE,
    PROVIDER,
    SCHEMA_VERSION,
)


def official_sonnet5_contract() -> dict[str, Any]:
    caps = SONNET5_THINKING_CAPABILITIES
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "model": MODEL,
        "provider": PROVIDER,
        "adaptive_default": True,
        "default_effort": "high",
        "thinking_disabled_supported": True,
        "manual_budget_tokens_supported": False,
        "manual_budget_tokens_http_status_if_sent": 400,
        "effort_supported": True,
        "effort_values": list(KNOWN_EFFORTS),
        "phase_evaluated_effort_values": ["low", "medium", "high"],
        "max_tokens_shared_output": True,
        "task_budget_supported": False,
        "omitting_thinking_field_enables_adaptive": True,
        "omitting_effort_uses_default_high": True,
        "effort_is_deterministic_thinking_cap": False,
        "thinking_type_enabled_budget_tokens_supported": False,
        "capabilities": caps.to_dict(),
        "source_references": list(OFFICIAL_SOURCE_URLS),
        "source_notes": OFFICIAL_SOURCE_NOTES,
        "verification_date": OFFICIAL_VERIFICATION_DATE,
        "verification_method": "external_official_documentation_facts",
        "live_documentation_fetch_this_phase": False,
    }


__all__ = ["official_sonnet5_contract"]
