"""
Injection process-scoped et vérification des timeouts de l'essai #2.

N'écrit pas le .env réel. Ne rallonge pas le connect. Interdit l'escalade #3.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.timeouts import (
    diagnose_stage_timeout,
    resolve_ai_timeouts,
)
from app.source_analysis_global_clean.constants import EXPECTED_MODEL, STAGE
from app.source_analysis_global_clean_attempt2.constants import (
    EXPECTED_CONNECT_TIMEOUT_SECONDS,
    EXPECTED_READ_TIMEOUT_SECONDS,
    EXPECTED_REQUESTS_TIMEOUT,
    EXPECTED_TIMEOUT_SOURCE,
    FORBIDDEN_THIRD_TIMEOUTS,
    SOURCE_ANALYSIS_CONNECT_ENV,
    SOURCE_ANALYSIS_READ_ENV,
)
from app.source_analysis_global_clean_attempt2.errors import TimeoutPolicyMismatch
from app.source_analysis_long_run_policy.constants import (
    EDITORIAL_STAGES,
    THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED,
)
from app.source_analysis_long_run_policy.policy import (
    DEFAULT_CONNECT_SECONDS,
    DEFAULT_READ_SECONDS,
    other_stages_isolated,
    proposed_environ,
)


def inject_attempt2_timeout_env(
    *,
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Injecte les deux variables d'étape dans l'environnement du processus.

    `environ is None` → os.environ (process-scoped). Aucun fichier .env.
    """
    values = proposed_environ()
    target = os.environ if environ is None else environ
    target[SOURCE_ANALYSIS_CONNECT_ENV] = values[SOURCE_ANALYSIS_CONNECT_ENV]
    target[SOURCE_ANALYSIS_READ_ENV] = values[SOURCE_ANALYSIS_READ_ENV]
    return {
        SOURCE_ANALYSIS_CONNECT_ENV: target[SOURCE_ANALYSIS_CONNECT_ENV],
        SOURCE_ANALYSIS_READ_ENV: target[SOURCE_ANALYSIS_READ_ENV],
        "injection": "process_scoped_os_environ",
        "real_dotenv_modified": False,
    }


def resolve_attempt2_timeouts(
    *,
    environ: Mapping[str, str] | None = None,
    request: AIRequest | None = None,
    engine: AnthropicEngine | None = None,
) -> dict[str, Any]:
    """Résout connect/read indépendamment, sans réseau."""
    env = os.environ if environ is None else environ
    resolved = resolve_ai_timeouts(stage=STAGE, environ=env)
    if engine is not None and request is not None:
        via_engine = engine.resolve_timeouts(request)
        resolved = via_engine
    connect, read = resolved.as_requests_timeout()
    return {
        "connect_seconds": resolved.connect_seconds,
        "connect_source": resolved.connect_source,
        "read_seconds": resolved.read_seconds,
        "read_source": resolved.read_source,
        "requests_timeout": [connect, read],
        "requests_timeout_shape": "tuple",
        "scalar_timeout_used": False,
        "total_wall_clock_timeout": False,
    }


def assert_attempt2_timeouts(resolved: Mapping[str, Any]) -> None:
    connect = float(resolved["connect_seconds"])
    read = float(resolved["read_seconds"])
    if (connect, read) != EXPECTED_REQUESTS_TIMEOUT:
        raise TimeoutPolicyMismatch(
            f"Timeouts effectifs ({connect}, {read}) ≠ "
            f"{EXPECTED_REQUESTS_TIMEOUT}. STOP PRE_CALL."
        )
    if resolved.get("connect_source") != EXPECTED_TIMEOUT_SOURCE:
        raise TimeoutPolicyMismatch(
            f"Source connect={resolved.get('connect_source')!r}, "
            f"attendu {EXPECTED_TIMEOUT_SOURCE}."
        )
    if resolved.get("read_source") != EXPECTED_TIMEOUT_SOURCE:
        raise TimeoutPolicyMismatch(
            f"Source read={resolved.get('read_source')!r}, "
            f"attendu {EXPECTED_TIMEOUT_SOURCE}."
        )
    tuple_value = resolved.get("requests_timeout")
    if list(tuple_value or []) != [
        EXPECTED_CONNECT_TIMEOUT_SECONDS,
        EXPECTED_READ_TIMEOUT_SECONDS,
    ]:
        raise TimeoutPolicyMismatch(
            f"requests timeout {tuple_value!r} n'est pas le tuple (30, 7200)."
        )
    if resolved.get("requests_timeout_shape") != "tuple":
        raise TimeoutPolicyMismatch("requests doit recevoir un tuple, pas un scalaire.")
    if resolved.get("scalar_timeout_used") is True:
        raise TimeoutPolicyMismatch("timeout=7200 scalaire interdit (allongerait connect).")


def diagnose_other_stages(
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    env = os.environ if environ is None else environ
    blocks: dict[str, dict[str, Any]] = {}
    for stage in EDITORIAL_STAGES:
        block = diagnose_stage_timeout(stage, environ=env)
        blocks[stage] = {
            "stage": block["stage"],
            "connect_seconds": block["connect_seconds"],
            "connect_source": block["connect_source"],
            "read_seconds": block["read_seconds"],
            "read_source": block["read_source"],
        }
    return blocks


def assert_other_stages_isolated(blocks: Mapping[str, Mapping[str, Any]]) -> bool:
    isolated = other_stages_isolated(blocks)
    if not isolated:
        raise TimeoutPolicyMismatch(
            "La configuration essai #2 a fuité vers editorial_planning / "
            "book_generation / book_validation."
        )
    for stage in EDITORIAL_STAGES:
        if stage == STAGE:
            continue
        block = blocks[stage]
        if block["connect_seconds"] != DEFAULT_CONNECT_SECONDS:
            raise TimeoutPolicyMismatch(f"{stage} connect modifié.")
        if block["read_seconds"] != DEFAULT_READ_SECONDS:
            raise TimeoutPolicyMismatch(f"{stage} read modifié.")
    return True


def third_timeout_escalation_prohibited() -> bool:
    if THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED:
        raise TimeoutPolicyMismatch("L'escalade de timeout #3 est interdite.")
    return True


def refuse_third_timeout_value(seconds: float) -> None:
    if seconds in FORBIDDEN_THIRD_TIMEOUTS or seconds > EXPECTED_READ_TIMEOUT_SECONDS:
        raise TimeoutPolicyMismatch(
            f"Timeout {seconds} interdit : THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED=false."
        )
