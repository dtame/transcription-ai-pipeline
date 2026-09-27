"""
Contrôle thinking / effort Anthropic — application locale fail-closed.

Ne vit pas dans build_payload() pour ne pas muter l'audit A.11
(clés littérales historiques). Aucun HTTP ici.
"""

from __future__ import annotations

from typing import Any

from app.ai.contracts import AIRequest
from app.ai.thinking import (
    SONNET5_MODEL,
    THINKING_MODE_ADAPTIVE,
    THINKING_MODE_DISABLED,
    THINKING_MODE_PROVIDER_DEFAULT,
    normalize_effort,
    normalize_thinking_mode,
    validate_thinking_for_provider,
)


def attach_request_output_controls(
    payload: dict[str, Any],
    request: AIRequest,
    model: str,
) -> dict[str, Any]:
    """
    Enrichit le payload Messages selon AIRequest.

    provider_default : n'ajoute aucun champ thinking/effort (historique).
    Sonnet 5 : n'envoie pas temperature (sampling non-défaut rejeté).
    effort fusionne avec output_config.format s'il existe déjà.
    """
    validate_thinking_for_provider(
        "anthropic",
        model,
        thinking_mode=request.thinking_mode,
        effort=request.effort,
        thinking_budget_tokens=request.thinking_budget_tokens,
    )

    if str(model).strip() == SONNET5_MODEL:
        payload.pop("temperature", None)

    mode = normalize_thinking_mode(request.thinking_mode)
    if mode == THINKING_MODE_DISABLED:
        payload["thinking"] = {"type": "disabled"}
    elif mode == THINKING_MODE_ADAPTIVE:
        payload["thinking"] = {"type": "adaptive"}
    elif mode == THINKING_MODE_PROVIDER_DEFAULT:
        payload.pop("thinking", None)

    effort = normalize_effort(request.effort)
    if effort is not None:
        output_config = payload.get("output_config")
        if not isinstance(output_config, dict):
            output_config = {}
            payload["output_config"] = output_config
        output_config["effort"] = effort

    return payload


__all__ = ["attach_request_output_controls"]
