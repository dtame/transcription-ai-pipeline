"""
Configuration générique thinking / effort — indépendante du fournisseur.

Les étapes métier utilisent thinking_mode et effort, jamais un dictionnaire
Anthropic. Les capacités non vérifiées restent fail-closed.

Unknown != 0 : un compteur thinking absent reste None.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from app.file_utils import content_hash

THINKING_MODE_DISABLED = "disabled"
THINKING_MODE_ADAPTIVE = "adaptive"
THINKING_MODE_PROVIDER_DEFAULT = "provider_default"

KNOWN_THINKING_MODES = frozenset(
    {
        THINKING_MODE_DISABLED,
        THINKING_MODE_ADAPTIVE,
        THINKING_MODE_PROVIDER_DEFAULT,
    }
)

EFFORT_LOW = "low"
EFFORT_MEDIUM = "medium"
EFFORT_HIGH = "high"
EFFORT_XHIGH = "xhigh"
EFFORT_MAX = "max"

KNOWN_EFFORTS = frozenset(
    {
        EFFORT_LOW,
        EFFORT_MEDIUM,
        EFFORT_HIGH,
        EFFORT_XHIGH,
        EFFORT_MAX,
    }
)

PHASE_EVAL_EFFORTS = frozenset({EFFORT_LOW, EFFORT_MEDIUM, EFFORT_HIGH})

CONTRACT_THINKING_DISABLED = "THINKING_DISABLED"
CONTRACT_ADAPTIVE_LOW = "ADAPTIVE_LOW"
CONTRACT_ADAPTIVE_MEDIUM = "ADAPTIVE_MEDIUM"
CONTRACT_ADAPTIVE_HIGH = "ADAPTIVE_HIGH"

SONNET5_MODEL = "claude-sonnet-5"
SONNET5_PROVIDER = "anthropic"

_OFFICIAL_SOURCE = (
    "Anthropic official Claude Sonnet 5 documentation — external verification "
    "2026-09-26 (adaptive thinking default, effort control, shared max_tokens, "
    "manual budget_tokens removed, thinking.type=disabled supported)."
)

_OFFICIAL_URLS = (
    "https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking",
    "https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
)


@dataclass(frozen=True)
class ThinkingCapabilities:
    provider: str
    model: str
    known: bool
    adaptive_thinking_supported: bool = False
    thinking_disabled_supported: bool = False
    manual_budget_tokens_supported: bool = False
    effort_supported: bool = False
    effort_values: tuple[str, ...] = ()
    adaptive_thinking_default: bool = False
    default_effort: str | None = None
    max_tokens_shared_output: bool = False
    task_budget_supported: bool = False
    source: str = "unverified"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "known": self.known,
            "adaptive_thinking_supported": self.adaptive_thinking_supported,
            "thinking_disabled_supported": self.thinking_disabled_supported,
            "manual_budget_tokens_supported": self.manual_budget_tokens_supported,
            "effort_supported": self.effort_supported,
            "effort_values": list(self.effort_values),
            "adaptive_thinking_default": self.adaptive_thinking_default,
            "default_effort": self.default_effort,
            "max_tokens_shared_output": self.max_tokens_shared_output,
            "task_budget_supported": self.task_budget_supported,
            "source": self.source,
        }


SONNET5_THINKING_CAPABILITIES = ThinkingCapabilities(
    provider=SONNET5_PROVIDER,
    model=SONNET5_MODEL,
    known=True,
    adaptive_thinking_supported=True,
    thinking_disabled_supported=True,
    manual_budget_tokens_supported=False,
    effort_supported=True,
    effort_values=(
        EFFORT_LOW,
        EFFORT_MEDIUM,
        EFFORT_HIGH,
        EFFORT_XHIGH,
        EFFORT_MAX,
    ),
    adaptive_thinking_default=True,
    default_effort=EFFORT_HIGH,
    max_tokens_shared_output=True,
    task_budget_supported=False,
    source=_OFFICIAL_SOURCE,
)


def resolve_thinking_capabilities(provider: str, model: str) -> ThinkingCapabilities:
    provider = str(provider or "").strip().lower()
    model = str(model or "").strip()
    if provider == SONNET5_PROVIDER and model == SONNET5_MODEL:
        return SONNET5_THINKING_CAPABILITIES
    return ThinkingCapabilities(
        provider=provider,
        model=model,
        known=False,
        source="unverified — do not generalize Sonnet 5 thinking contract",
    )


def normalize_thinking_mode(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return THINKING_MODE_PROVIDER_DEFAULT
    mode = str(value).strip().lower()
    if mode not in KNOWN_THINKING_MODES:
        raise ValueError(
            f"AIRequest.thinking_mode invalide : {value!r}. "
            f"Valeurs : {sorted(KNOWN_THINKING_MODES)}."
        )
    return mode


def normalize_effort(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    effort = str(value).strip().lower()
    if effort not in KNOWN_EFFORTS:
        raise ValueError(
            f"AIRequest.effort invalide : {value!r}. "
            f"Valeurs : {sorted(KNOWN_EFFORTS)}."
        )
    return effort


def validate_request_thinking_fields(
    thinking_mode: str | None,
    effort: str | None,
    thinking_budget_tokens: int | None,
) -> tuple[str, str | None, int | None]:
    mode = normalize_thinking_mode(thinking_mode)
    normalized_effort = normalize_effort(effort)
    budget = thinking_budget_tokens
    if budget is not None:
        budget = int(budget)
        if budget <= 0:
            raise ValueError(
                f"AIRequest.thinking_budget_tokens doit être > 0 : {thinking_budget_tokens}"
            )
    return mode, normalized_effort, budget


def validate_thinking_for_provider(
    provider: str,
    model: str,
    *,
    thinking_mode: str | None,
    effort: str | None,
    thinking_budget_tokens: int | None,
) -> ThinkingCapabilities:
    """
    Rejette localement toute combinaison non vérifiée. Aucun HTTP.
    """
    from app.ai.errors import AIConfigurationError

    caps = resolve_thinking_capabilities(provider, model)
    mode = normalize_thinking_mode(thinking_mode)
    normalized_effort = normalize_effort(effort)

    if thinking_budget_tokens is not None:
        raise AIConfigurationError(
            f"thinking_budget_tokens n'est pas supporté pour {provider}:{model}. "
            "Claude Sonnet 5 a retiré le budget_tokens manuel (HTTP 400). "
            "task_budget n'est pas supporté non plus. Ne pas envoyer ce champ."
        )

    if mode == THINKING_MODE_DISABLED and not caps.thinking_disabled_supported:
        raise AIConfigurationError(
            f"thinking_mode=disabled n'est pas vérifié pour {provider}:{model}."
        )
    if mode == THINKING_MODE_ADAPTIVE and not caps.adaptive_thinking_supported:
        raise AIConfigurationError(
            f"thinking_mode=adaptive n'est pas vérifié pour {provider}:{model}."
        )
    if normalized_effort is not None and not caps.effort_supported:
        raise AIConfigurationError(
            f"effort n'est pas vérifié pour {provider}:{model}."
        )
    if (
        normalized_effort is not None
        and caps.effort_values
        and normalized_effort not in caps.effort_values
    ):
        raise AIConfigurationError(
            f"effort={normalized_effort!r} n'est pas supporté pour {provider}:{model}."
        )
    return caps


def thinking_identity(
    *,
    thinking_mode: str | None,
    effort: str | None,
    thinking_budget_tokens: int | None = None,
) -> dict[str, Any]:
    mode = normalize_thinking_mode(thinking_mode)
    normalized_effort = normalize_effort(effort)
    identity: dict[str, Any] = {
        "thinking_mode": mode,
        "effort": normalized_effort,
    }
    if thinking_budget_tokens is not None:
        identity["thinking_budget_tokens"] = int(thinking_budget_tokens)
    return identity


def thinking_fingerprint(
    thinking_mode: str | None,
    effort: str | None,
    thinking_budget_tokens: int | None = None,
) -> str:
    return content_hash(
        json.dumps(
            thinking_identity(
                thinking_mode=thinking_mode,
                effort=effort,
                thinking_budget_tokens=thinking_budget_tokens,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def is_historical_thinking_default(
    thinking_mode: str | None,
    effort: str | None,
    thinking_budget_tokens: int | None = None,
) -> bool:
    return (
        normalize_thinking_mode(thinking_mode) == THINKING_MODE_PROVIDER_DEFAULT
        and normalize_effort(effort) is None
        and thinking_budget_tokens is None
    )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_thinking_tokens_from_usage(usage: Any) -> int | None:
    """Unknown != 0. Absent → None.

    Preserved sources (first match wins):
    - output_tokens_details.thinking_tokens (Anthropic / historical)
    - usage.thinking_tokens

    Added OpenAI chat.completions sources:
    - completion_tokens_details.reasoning_tokens
    - usage.reasoning_tokens
    """
    if not isinstance(usage, Mapping):
        return None
    details = usage.get("output_tokens_details")
    if isinstance(details, Mapping) and details.get("thinking_tokens") is not None:
        parsed = _optional_int(details.get("thinking_tokens"))
        if parsed is not None:
            return parsed
    if usage.get("thinking_tokens") is not None:
        parsed = _optional_int(usage.get("thinking_tokens"))
        if parsed is not None:
            return parsed
    completion_details = usage.get("completion_tokens_details")
    if (
        isinstance(completion_details, Mapping)
        and completion_details.get("reasoning_tokens") is not None
    ):
        parsed = _optional_int(completion_details.get("reasoning_tokens"))
        if parsed is not None:
            return parsed
    if usage.get("reasoning_tokens") is not None:
        return _optional_int(usage.get("reasoning_tokens"))
    return None


UNKNOWN_TOKEN_COUNT = "UNKNOWN"


def extract_openai_usage_telemetry(usage: Any) -> dict[str, Any]:
    """
    Distinguish input, completion, reasoning, and visible output tokens.

    Absent field = UNKNOWN, never 0. Do not subtract reasoning from
    completion to invent a visible-output count.
    """
    mapping = usage if isinstance(usage, Mapping) else {}
    completion_details = mapping.get("completion_tokens_details")
    if not isinstance(completion_details, Mapping):
        completion_details = {}
    output_details = mapping.get("output_tokens_details")
    if not isinstance(output_details, Mapping):
        output_details = {}

    input_tokens = _optional_int(
        mapping.get("prompt_tokens", mapping.get("input_tokens"))
    )
    completion_tokens = _optional_int(
        mapping.get("completion_tokens", mapping.get("output_tokens"))
    )
    reasoning_tokens = extract_thinking_tokens_from_usage(mapping)
    visible_explicit = _optional_int(
        completion_details.get("text_tokens", completion_details.get("visible_tokens"))
    )

    reasoning_source = "absent"
    if isinstance(output_details, Mapping) and output_details.get("thinking_tokens") is not None:
        reasoning_source = "output_tokens_details.thinking_tokens"
    elif mapping.get("thinking_tokens") is not None:
        reasoning_source = "usage.thinking_tokens"
    elif completion_details.get("reasoning_tokens") is not None:
        reasoning_source = "completion_tokens_details.reasoning_tokens"
    elif mapping.get("reasoning_tokens") is not None:
        reasoning_source = "usage.reasoning_tokens"

    return {
        "input_tokens": input_tokens if input_tokens is not None else UNKNOWN_TOKEN_COUNT,
        "completion_tokens": (
            completion_tokens if completion_tokens is not None else UNKNOWN_TOKEN_COUNT
        ),
        "reasoning_tokens": (
            reasoning_tokens if reasoning_tokens is not None else UNKNOWN_TOKEN_COUNT
        ),
        "visible_output_tokens": (
            visible_explicit if visible_explicit is not None else UNKNOWN_TOKEN_COUNT
        ),
        "unknown_tokens": [
            name
            for name, value in (
                ("input_tokens", input_tokens),
                ("completion_tokens", completion_tokens),
                ("reasoning_tokens", reasoning_tokens),
                ("visible_output_tokens", visible_explicit),
            )
            if value is None
        ],
        "reasoning_source": reasoning_source,
        "completion_tokens_details_present": bool(completion_details),
        "did_not_subtract_reasoning_from_completion": True,
        "did_not_infer_from_max_completion_tokens": True,
        "did_not_infer_cause_from_finish_reason": True,
        "explicit_zero_is_zero": reasoning_tokens == 0,
        "absent_is_unknown": reasoning_tokens is None,
    }


def conceptual_json_budget(*, max_output: int, thinking_disabled: bool) -> dict[str, Any]:
    if thinking_disabled:
        return {
            "thinking_usage_theoretical": 0,
            "thinking_hard_capped": False,
            "thinking_provider_enforced_disabled": True,
            "available_json_budget_conceptual": int(max_output),
            "thinking_token_count_known": False,
            "note": (
                "Official contract: thinking.type=disabled turns thinking off. "
                "Theoretical thinking usage is 0. This is not a schema-enforced "
                "semantic JSON bound."
            ),
        }
    return {
        "thinking_usage_theoretical": None,
        "thinking_hard_capped": False,
        "thinking_provider_enforced_disabled": False,
        "available_json_budget_conceptual": None,
        "thinking_token_count_known": False,
        "note": (
            "Adaptive thinking + effort is model-controlled. "
            "Do not treat effort as an 8000-token thinking cap."
        ),
    }


__all__ = [
    "CONTRACT_ADAPTIVE_HIGH",
    "CONTRACT_ADAPTIVE_LOW",
    "CONTRACT_ADAPTIVE_MEDIUM",
    "CONTRACT_THINKING_DISABLED",
    "EFFORT_HIGH",
    "EFFORT_LOW",
    "EFFORT_MAX",
    "EFFORT_MEDIUM",
    "EFFORT_XHIGH",
    "KNOWN_EFFORTS",
    "KNOWN_THINKING_MODES",
    "PHASE_EVAL_EFFORTS",
    "SONNET5_MODEL",
    "SONNET5_PROVIDER",
    "SONNET5_THINKING_CAPABILITIES",
    "THINKING_MODE_ADAPTIVE",
    "THINKING_MODE_DISABLED",
    "THINKING_MODE_PROVIDER_DEFAULT",
    "ThinkingCapabilities",
    "conceptual_json_budget",
    "UNKNOWN_TOKEN_COUNT",
    "extract_openai_usage_telemetry",
    "extract_thinking_tokens_from_usage",
    "is_historical_thinking_default",
    "normalize_effort",
    "normalize_thinking_mode",
    "resolve_thinking_capabilities",
    "thinking_fingerprint",
    "thinking_identity",
    "validate_request_thinking_fields",
    "validate_thinking_for_provider",
]
