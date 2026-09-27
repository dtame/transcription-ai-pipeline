"""
Politique opérationnelle 3B.5.2 — décision offline, sans réseau.

N'appelle pas engine.generate(). N'ouvre pas requests. N'écrit pas .env.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Mapping

from app.ai.pricing import TOKENS_PER_PRICING_UNIT, build_default_catalog
from app.ai.timeouts import diagnose_stage_timeout, resolve_ai_timeouts
from app.source_analysis_long_run_policy.constants import (
    ATTEMPT_1_READ_TIMEOUT_SECONDS,
    CANDIDATE_READ_TIMEOUTS_SECONDS,
    CANARY_OUTPUT_TOKENS,
    CANARY_WORDS,
    DECISION_ARCHITECTURE_REVIEW,
    DECISION_PRESERVE_TRANSPORT_OFFLINE_DIAGNOSIS,
    DECISION_RETRY_WITH_LONGER_TIMEOUT,
    DECISION_STOP_HUMAN_REVIEW,
    DECISION_STOP_NO_RETRY,
    DEFAULT_CONNECT_SECONDS,
    DEFAULT_READ_SECONDS,
    EDITORIAL_STAGES,
    EXPECTED_INPUT_TOKENS,
    EXPECTED_MAX_OUTPUT_TOKENS,
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    EXPECTED_STAGE,
    EXPECTED_WORDS,
    FAILURE_POST_PROVIDER_LOCAL,
    FAILURE_PROVIDER_ERROR,
    FAILURE_SECOND_TIMEOUT,
    FAILURE_TRUNCATION,
    FALLBACK,
    FIRST_FAILURE_LOWER_BOUND_SECONDS,
    GLOBAL_ATTEMPT_NUMBER,
    ILLUSTRATIVE_OUTPUT_TOKENS,
    LINEAR_CANARY_EXTRAPOLATION_ALLOWED,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    POLICY_CONFIDENCE,
    RETRY,
    SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS,
    SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS,
    SELECTED_POLICY_STATUS,
    SELECTED_READ_DURATION_HUMAN,
    SOURCE_ANALYSIS_CONNECT_ENV,
    SOURCE_ANALYSIS_READ_ENV,
    THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED,
    TIMEOUT_IS_PROVIDER_GUARANTEE,
    TIMEOUT_POLICY_BASIS,
)

_TIMEOUT_CLASSES = frozenset(
    {"AITimeoutError", "TIMEOUT", "timeout", "READ_TIMEOUT", "CONNECT_TIMEOUT"}
)
_PROVIDER_ERROR_CLASSES = frozenset(
    {
        "400",
        "401",
        "403",
        "429",
        "5xx",
        "500",
        "502",
        "503",
        "PROVIDER_ERROR",
        "NETWORK",
        "AIAuthenticationError",
        "AIRateLimitError",
        "AIServerError",
        "AIConnectionError",
        "AIRequestError",
    }
)
_LOCAL_FAILURE_CLASSES = frozenset(
    {
        "LOCAL_FAILURE",
        "POST_PROVIDER_LOCAL_FAILURE",
        "TRANSPORT_PARSE",
        "VOCABULARY",
        "SRC_REFS",
        "LINKS",
        "DECODER",
        "RECONSTRUCTION",
        "NORMALIZER",
        "CANONICAL_VALIDATOR",
        "EDITORIAL_LEAKAGE",
    }
)
_TRUNCATION_CLASSES = frozenset(
    {"TRUNCATION", "max_tokens", "length", "OUTPUT_TRUNCATED"}
)

_CANDIDATE_NOTES = {
    5400: {
        "duration": "90 minutes",
        "advantages": (
            "Exceeds the 3600 s lower bound by 1800 s. Detects a stalled "
            "connection 30 minutes earlier than 7200."
        ),
        "risks": (
            "Only a 50 percent increase over the window that already elapsed "
            "with no body and no first-byte observation. The remaining "
            "generation time is unknown, so a 30-minute increment is a thin "
            "operational margin."
        ),
    },
    7200: {
        "duration": "120 minutes",
        "advantages": (
            "Doubles the previous read window. Materially larger than 3600 "
            "without consuming the maximum candidate. Keeps the second "
            "attempt bounded at two hours."
        ),
        "risks": (
            "If the connection is stalled, failure detection waits one extra "
            "hour versus attempt #1. Upstream limits remain unknown. A "
            "larger window does not guarantee a body."
        ),
    },
    9000: {
        "duration": "150 minutes",
        "advantages": (
            "Provides 150 percent more read time than 3600 if generation is "
            "legitimately very long."
        ),
        "risks": (
            "Adds 30 minutes of stall wait over 7200 without evidence that "
            "7200 is insufficient. Delays the architecture-review gate."
        ),
    },
    10800: {
        "duration": "180 minutes",
        "advantages": (
            "Largest evaluated window. Maximizes the chance that a silent "
            "non-streaming generation finishes inside the local client."
        ),
        "risks": (
            "Triples the previous wait. Consumes the maximum candidate on "
            "the first authorized retry and collapses the no-blind-escalation "
            "rule this policy exists to protect. Longest delay before "
            "declaring a second timeout."
        ),
    },
}

SELECTED_REASONING = (
    "5400 exceeds 3600 but only by 50 percent. Attempt #1 used the entire "
    "3600 s window with no provider body, so remaining generation time is "
    "unknown; a 30-minute increment is too thin as the sole authorized "
    "retry. 9000 and 10800 increase stall cost and 10800 would spend the "
    "maximum candidate immediately, leaving no architectural pause. 7200 "
    "is the only candidate that is both materially larger than 3600 "
    "(exactly 2x) and still bounded. This is an operational engineering "
    "choice, not a measured provider duration."
)


@dataclass(frozen=True)
class LongRunExecutionPolicy:
    """Décision offline du second essai global. Pas une autorisation d'exécution."""

    attempt_number: int
    connect_timeout_seconds: int
    read_timeout_seconds: int
    timeout_policy_basis: str
    timeout_is_provider_guarantee: bool
    max_real_calls: int
    max_attempts: int
    retry: bool
    fallback: None
    third_global_timeout_escalation_allowed: bool
    status: str
    linear_canary_extrapolation_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def selected_policy() -> LongRunExecutionPolicy:
    return LongRunExecutionPolicy(
        attempt_number=GLOBAL_ATTEMPT_NUMBER,
        connect_timeout_seconds=SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS,
        read_timeout_seconds=SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS,
        timeout_policy_basis=TIMEOUT_POLICY_BASIS,
        timeout_is_provider_guarantee=TIMEOUT_IS_PROVIDER_GUARANTEE,
        max_real_calls=MAX_REAL_CALLS,
        max_attempts=MAX_ATTEMPTS,
        retry=RETRY,
        fallback=FALLBACK,
        third_global_timeout_escalation_allowed=(
            THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED
        ),
        status=SELECTED_POLICY_STATUS,
        linear_canary_extrapolation_allowed=LINEAR_CANARY_EXTRAPOLATION_ALLOWED,
    )


def proposed_environ() -> dict[str, str]:
    return {
        SOURCE_ANALYSIS_CONNECT_ENV: str(
            SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS
        ),
        SOURCE_ANALYSIS_READ_ENV: str(SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS),
    }


def evaluate_candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seconds in CANDIDATE_READ_TIMEOUTS_SECONDS:
        notes = _CANDIDATE_NOTES[seconds]
        selected = seconds == SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS
        rows.append(
            {
                "candidate": seconds,
                "duration": notes["duration"],
                "exceeds_first_failure_lower_bound": (
                    seconds > FIRST_FAILURE_LOWER_BOUND_SECONDS
                ),
                "advantages": notes["advantages"],
                "risks": notes["risks"],
                "selected": selected,
            }
        )
    return rows


def justify_selected_timeout() -> dict[str, Any]:
    if SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS <= FIRST_FAILURE_LOWER_BOUND_SECONDS:
        raise RuntimeError(
            "La politique 3B.5.2 refuse un read timeout <= 3600 pour un retry identique."
        )
    if SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS not in CANDIDATE_READ_TIMEOUTS_SECONDS:
        raise RuntimeError("Le timeout sélectionné n'est pas dans le jeu de candidats.")
    if LINEAR_CANARY_EXTRAPOLATION_ALLOWED:
        raise RuntimeError("L'extrapolation linéaire du canary est interdite.")
    return {
        "value": SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS,
        "duration": SELECTED_READ_DURATION_HUMAN,
        "reasoning": SELECTED_REASONING,
        "confidence": POLICY_CONFIDENCE,
        "scientifically_proven": False,
        "provider_guarantee": False,
        "operational_engineering_policy": True,
        "linear_canary_extrapolation_used": False,
        "first_failure_lower_bound_seconds": FIRST_FAILURE_LOWER_BOUND_SECONDS,
    }


def decide_after_attempt_2(result_class: str) -> str:
    """
    Décision déterministe après l'essai #2.

    Un second timeout n'autorise JAMAIS RETRY_WITH_LONGER_TIMEOUT.
    """
    token = str(result_class or "").strip()
    if token in _TIMEOUT_CLASSES:
        return DECISION_ARCHITECTURE_REVIEW
    if token in _PROVIDER_ERROR_CLASSES:
        return DECISION_STOP_HUMAN_REVIEW
    if token in _LOCAL_FAILURE_CLASSES:
        return DECISION_PRESERVE_TRANSPORT_OFFLINE_DIAGNOSIS
    if token in _TRUNCATION_CLASSES:
        return DECISION_STOP_NO_RETRY
    raise ValueError(f"Classe de résultat d'essai #2 inconnue : {result_class!r}.")


def local_failure_requirements() -> dict[str, Any]:
    return {
        "preserve_transport": True,
        "offline_diagnosis_first": True,
        "provider_retry_allowed": False,
        "decision": FAILURE_POST_PROVIDER_LOCAL,
    }


def simulate_stage_timeouts(
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    env = dict(environ) if environ is not None else proposed_environ()
    resolved: dict[str, dict[str, Any]] = {}
    for stage in EDITORIAL_STAGES:
        block = diagnose_stage_timeout(stage, environ=env)
        resolved[stage] = {
            "stage": block["stage"],
            "provider": block["provider"],
            "model": block["model"],
            "connect_seconds": block["connect_seconds"],
            "connect_source": block["connect_source"],
            "read_seconds": block["read_seconds"],
            "read_source": block["read_source"],
        }
    return resolved


def simulate_source_analysis_timeouts(
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = dict(environ) if environ is not None else proposed_environ()
    timeouts = resolve_ai_timeouts(stage=EXPECTED_STAGE, environ=env)
    connect, read = timeouts.as_requests_timeout()
    return {
        "connect_seconds": timeouts.connect_seconds,
        "connect_source": timeouts.connect_source,
        "read_seconds": timeouts.read_seconds,
        "read_source": timeouts.read_source,
        "requests_timeout": [connect, read],
        "requests_timeout_shape": "tuple",
        "total_wall_clock_timeout": False,
    }


def current_default_stage_timeouts() -> dict[str, dict[str, Any]]:
    return simulate_stage_timeouts(environ={})


def other_stages_isolated(simulated: Mapping[str, Mapping[str, Any]]) -> bool:
    for stage in EDITORIAL_STAGES:
        if stage == EXPECTED_STAGE:
            continue
        block = simulated[stage]
        if block["connect_seconds"] != DEFAULT_CONNECT_SECONDS:
            return False
        if block["read_seconds"] != DEFAULT_READ_SECONDS:
            return False
        if block["read_source"] != "default":
            return False
        if block["connect_source"] != "default":
            return False
    source = simulated[EXPECTED_STAGE]
    return (
        source["connect_seconds"] == float(SELECTED_OPERATIONAL_CONNECT_TIMEOUT_SECONDS)
        and source["read_seconds"] == float(SELECTED_OPERATIONAL_READ_TIMEOUT_SECONDS)
        and source["read_source"] == "stage_env"
        and source["connect_source"] == "stage_env"
    )


def canary_linear_output_forbidden() -> dict[str, Any]:
    invalid = (CANARY_OUTPUT_TOKENS / CANARY_WORDS) * EXPECTED_WORDS
    return {
        "allowed": LINEAR_CANARY_EXTRAPOLATION_ALLOWED,
        "forbidden_formula": (
            f"{CANARY_OUTPUT_TOKENS} output / {CANARY_WORDS} words "
            f"× {EXPECTED_WORDS} words"
        ),
        "invalid_result_if_applied": invalid,
        "reason": (
            "The 10-SRC / 100-word canary is not linearly predictive of the "
            "global request. 3B.5 already recorded "
            "CANARY_SCALING_IS_NOT_LINEARLY_PREDICTIVE = true."
        ),
    }


def _money(value: Decimal) -> str:
    return format(value, "f")


def input_side_cost_estimate() -> dict[str, Any]:
    catalog = build_default_catalog()
    pricing = catalog.get(EXPECTED_PROVIDER, EXPECTED_MODEL)
    if pricing is None:
        return {
            "status": "unknown",
            "estimated_input_tokens": EXPECTED_INPUT_TOKENS,
            "input_cost": None,
            "output_cost": None,
            "total_cost": None,
            "note": "Aucun tarif local pour le modèle. unknown n'est pas zéro.",
        }
    input_cost = (
        Decimal(EXPECTED_INPUT_TOKENS) / TOKENS_PER_PRICING_UNIT
    ) * pricing.input_cost_per_1m_tokens
    return {
        "status": "input_side_local_estimate_output_unknown",
        "catalog_line_status": pricing.cost_status,
        "provider": EXPECTED_PROVIDER,
        "model": EXPECTED_MODEL,
        "currency": pricing.currency,
        "estimated_input_tokens": EXPECTED_INPUT_TOKENS,
        "input_is_preflight_estimate_not_provider_usage": True,
        "input_cost_per_1m_tokens": _money(pricing.input_cost_per_1m_tokens),
        "output_cost_per_1m_tokens": _money(pricing.output_cost_per_1m_tokens),
        "input_cost": _money(input_cost),
        "output_tokens": None,
        "output_cost": None,
        "total_cost": None,
        "unknown_must_not_become_zero": True,
        "long_context_regime_declared_on_catalog_line": bool(
            pricing.unmodeled_regimes
        ),
        "unmodeled_regimes": pricing.unmodeled_regimes or "",
        "pricing_source": pricing.source,
        "effective_date": pricing.effective_date,
        "verified": pricing.verified,
        "note": (
            "Input cost uses the local preflight token estimate and the "
            "configured base rate. Output length is unknown until the run. "
            "Unknown output is not converted to zero, so no complete total "
            "is claimed. If an upstream long-context regime applies, it is "
            "not modeled here and the figure is not an invoice."
        ),
    }


def illustrative_output_scenarios() -> list[dict[str, Any]]:
    catalog = build_default_catalog()
    rows: list[dict[str, Any]] = []
    for output_tokens in ILLUSTRATIVE_OUTPUT_TOKENS:
        breakdown = catalog.estimate_cost(
            EXPECTED_PROVIDER,
            EXPECTED_MODEL,
            EXPECTED_INPUT_TOKENS,
            output_tokens,
        )
        rows.append(
            {
                "label": "ILLUSTRATIVE ONLY",
                "output_tokens": output_tokens,
                "input_tokens_preflight_estimate": EXPECTED_INPUT_TOKENS,
                "input_cost": (
                    None if breakdown.input_cost is None else _money(breakdown.input_cost)
                ),
                "output_cost": (
                    None
                    if breakdown.output_cost is None
                    else _money(breakdown.output_cost)
                ),
                "total_cost": (
                    None if breakdown.total_cost is None else _money(breakdown.total_cost)
                ),
                "currency": breakdown.currency,
                "catalog_status": breakdown.status,
                "prediction": False,
            }
        )
    return rows


def global_versus_multi_window() -> dict[str, Any]:
    return {
        "abandon_global_now": False,
        "plan_windows_exists": True,
        "multi_window_consolidation_implemented": False,
        "evidence_strong_enough_to_abandon_global": False,
        "reason": (
            "The first global failure has a concrete local read-timeout "
            "explanation. The global semantic pipeline already passed the "
            "real canary. The corpus still fits the configured context "
            "budget without truncation. Moving to multi-window would itself "
            "require cross-window topic consolidation, idea deduplication, "
            "relationship reconciliation, global ordering, voice-profile "
            "consolidation, coverage reconciliation, and additional "
            "provider calls. Multi-window is therefore not automatically "
            "safer or simpler, and is not implemented now."
        ),
        "multi_window_would_introduce": [
            "cross-window topic consolidation",
            "idea deduplication",
            "relationship reconciliation",
            "global ordering",
            "voice-profile consolidation",
            "coverage reconciliation",
            "additional provider calls / cost",
        ],
    }


def supporting_factors() -> list[dict[str, str]]:
    return [
        {
            "id": "A",
            "factor": "Corpus fits configured context budget.",
            "evidence": (
                f"estimated_input_tokens={EXPECTED_INPUT_TOKENS}, "
                f"usable_input_budget=572000, remaining_margin=429047."
            ),
        },
        {
            "id": "B",
            "factor": "Global strategy selected without truncation.",
            "evidence": "preflight.strategy=global on the clean DERIVED corpus.",
        },
        {
            "id": "C",
            "factor": "Generation C server grammar already accepted.",
            "evidence": "3B.4.3 Generation C server grammar acceptance = VERIFIED.",
        },
        {
            "id": "D",
            "factor": "Prompt 1.3 vocabulary compliance passed a real canary.",
            "evidence": "3B.4.4 offline PASS; 3B.4.5 SRC003799–SRC003808 PASS.",
        },
        {
            "id": "E",
            "factor": "Full canary pipeline passed.",
            "evidence": (
                "SERVER GRAMMAR ACCEPTED, VOCABULARY COMPLIANCE VERIFIED, "
                "PIPELINE PASS, canonical validator PASS."
            ),
        },
        {
            "id": "F",
            "factor": "First global failure occurred before any provider body.",
            "evidence": (
                "AITimeoutError after 3600 s. No provider body, transport, "
                "usage, or source_map."
            ),
        },
        {
            "id": "G",
            "factor": "3B.5 identified a local read timeout as the immediate failure.",
            "evidence": "ROOT CAUSE CLASSIFICATION = HTTP_READ_TIMEOUT_TOO_SHORT.",
        },
        {
            "id": "H",
            "factor": "No lower local timeout existed on the failed path.",
            "evidence": "lowest_active_timeout_seconds = 3600. 3B.5 lower_timeout_elsewhere = NO.",
        },
        {
            "id": "I",
            "factor": "3B.5.1 corrected connect/read architecture.",
            "evidence": (
                "requests.post now receives timeout=(connect, read). Stage "
                "and env overrides are supported without Python changes."
            ),
        },
        {
            "id": "J",
            "factor": "Global analysis preserves whole-source semantic context.",
            "evidence": (
                "A single coherent analysis avoids unimplemented "
                "cross-window consolidation."
            ),
        },
    ]


def risk_factors() -> list[dict[str, str]]:
    return [
        {
            "id": "A",
            "factor": "Attempt #1 waited 3600 s without a usable response.",
            "evidence": "AITimeoutError. No body. Remaining work unknown.",
        },
        {
            "id": "B",
            "factor": "Actual required provider generation time is unknown.",
            "evidence": "NO_EVIDENCE_BASED_EXACT_TIMEOUT. No linear canary forecast.",
        },
        {
            "id": "C",
            "factor": "Upstream Anthropic/proxy limits remain unknown.",
            "evidence": "provider_upstream layer was NOT_DOCUMENTED_LOCALLY.",
        },
        {
            "id": "D",
            "factor": "Output could be large.",
            "evidence": (
                f"max_output_tokens={EXPECTED_MAX_OUTPUT_TOKENS}. "
                "Structured Generation C over 8298 segments."
            ),
        },
        {
            "id": "E",
            "factor": "Max output is 128000.",
            "evidence": "EXPECTED_MODEL_MAX_OUTPUT = 128000.",
        },
        {
            "id": "F",
            "factor": "Non-streaming execution provides limited mid-call observability.",
            "evidence": "ANTHROPIC_RESPONSE_MODE = NON_STREAMING. No percent progress.",
        },
        {
            "id": "G",
            "factor": "A connection failure late in generation can lose the response.",
            "evidence": "No partial-body preservation on the current path.",
        },
        {
            "id": "H",
            "factor": "Provider-side progress cannot be measured.",
            "evidence": "heartbeat_local=false, streaming=false.",
        },
        {
            "id": "I",
            "factor": "A second attempt may incur cost even if no body is received.",
            "evidence": (
                "Attempt #1 cost status = unavailable. unknown must not "
                "become zero."
            ),
        },
        {
            "id": "J",
            "factor": "Global run remains a single-shot operation.",
            "evidence": "max_real_calls=1, max_attempts=1, retry=false, fallback=none.",
        },
    ]


def read_timeout_semantics() -> dict[str, Any]:
    return {
        "controls": (
            "requests/urllib3 read timeout: maximum time waiting for the "
            "next bytes after the TCP/TLS connection is established, on a "
            "non-streaming requests.post. If the server stays silent until "
            "the full generation is ready, the entire generation wait must "
            "fit inside this window."
        ),
        "is_provider_computation_deadline": False,
        "is_total_wall_clock_timeout": False,
        "clock_starts_at": "requests.post() inside app.ai.providers._http.post_json",
        "resets_on_incoming_bytes": True,
        "application_total_timeout_on_this_path": False,
    }
