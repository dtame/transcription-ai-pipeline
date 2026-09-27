"""
Correspondance exacte avec la politique 3B.5.2.

Compare la configuration pré-appel à
`audit/source_analysis_second_global_attempt_policy.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_global_clean.constants import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
)
from app.source_analysis_global_clean_attempt2.constants import (
    ATTEMPT_NUMBER,
    EXPECTED_CONNECT_TIMEOUT_SECONDS,
    EXPECTED_READ_TIMEOUT_SECONDS,
    POLICY_ARTIFACT_NAME,
)
from app.source_analysis_global_clean_attempt2.errors import PolicyArtifactMismatch
from app.source_analysis_long_run_policy.constants import (
    THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED,
)
from app.source_analysis_long_run_policy.policy import selected_policy


def policy_artifact_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / POLICY_ARTIFACT_NAME


def load_policy_artifact(
    project_name: str, *, sortie_dir: Path | None = None
) -> dict[str, Any]:
    path = policy_artifact_path(project_name, sortie_dir=sortie_dir)
    if not path.is_file():
        raise PolicyArtifactMismatch(
            f"Politique 3B.5.2 absente : {path}. STOP PRE_CALL."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PolicyArtifactMismatch("Politique 3B.5.2 illisible.")
    return payload


def expected_selected_policy() -> dict[str, Any]:
    policy = selected_policy()
    return {
        "attempt_number": policy.attempt_number,
        "connect_timeout_seconds": policy.connect_timeout_seconds,
        "read_timeout_seconds": policy.read_timeout_seconds,
        "max_real_calls": policy.max_real_calls,
        "max_attempts": policy.max_attempts,
        "retry": policy.retry,
        "fallback": policy.fallback,
        "third_global_timeout_escalation_allowed": (
            policy.third_global_timeout_escalation_allowed
        ),
    }


def effective_policy_view(
    *,
    connect_seconds: float,
    read_seconds: float,
    max_real_calls: int,
    max_attempts: int,
    retry: bool,
    fallback: Any,
    attempt_number: int,
    third_escalation: bool,
) -> dict[str, Any]:
    return {
        "attempt_number": attempt_number,
        "connect_timeout_seconds": int(connect_seconds)
        if connect_seconds == int(connect_seconds)
        else connect_seconds,
        "read_timeout_seconds": int(read_seconds)
        if read_seconds == int(read_seconds)
        else read_seconds,
        "max_real_calls": max_real_calls,
        "max_attempts": max_attempts,
        "retry": retry,
        "fallback": fallback,
        "third_global_timeout_escalation_allowed": third_escalation,
    }


def match_attempt2_policy(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    effective: Mapping[str, Any],
    require_file: bool = True,
) -> dict[str, Any]:
    """
    Exige une correspondance exacte avec selected_policy de 3B.5.2.

    `require_file=False` (tests isolés) compare à selected_policy() en mémoire.
    """
    expected = expected_selected_policy()
    source = "in_memory_selected_policy"
    artifact: dict[str, Any] | None = None
    if require_file:
        artifact = load_policy_artifact(project_name, sortie_dir=sortie_dir)
        selected = dict(artifact.get("selected_policy") or {})
        file_expected = {
            "attempt_number": selected.get("attempt_number"),
            "connect_timeout_seconds": selected.get("connect_timeout_seconds"),
            "read_timeout_seconds": selected.get("read_timeout_seconds"),
            "max_real_calls": selected.get("max_real_calls"),
            "max_attempts": selected.get("max_attempts"),
            "retry": selected.get("retry"),
            "fallback": selected.get("fallback"),
            "third_global_timeout_escalation_allowed": selected.get(
                "third_global_timeout_escalation_allowed"
            ),
        }
        if file_expected != expected:
            raise PolicyArtifactMismatch(
                "Le fichier politique 3B.5.2 ne correspond pas à selected_policy()."
            )
        expected = file_expected
        source = "policy_artifact"
    actual = {
        "attempt_number": effective.get("attempt_number"),
        "connect_timeout_seconds": effective.get("connect_timeout_seconds"),
        "read_timeout_seconds": effective.get("read_timeout_seconds"),
        "max_real_calls": effective.get("max_real_calls"),
        "max_attempts": effective.get("max_attempts"),
        "retry": effective.get("retry"),
        "fallback": effective.get("fallback"),
        "third_global_timeout_escalation_allowed": effective.get(
            "third_global_timeout_escalation_allowed"
        ),
    }
    if actual != expected:
        raise PolicyArtifactMismatch(
            f"Configuration pré-appel ≠ politique 3B.5.2 ({source}) : "
            f"effectif={actual} attendu={expected}."
        )
    if actual["attempt_number"] != ATTEMPT_NUMBER:
        raise PolicyArtifactMismatch("attempt_number ≠ 2.")
    if actual["connect_timeout_seconds"] != int(EXPECTED_CONNECT_TIMEOUT_SECONDS):
        raise PolicyArtifactMismatch("connect_timeout_seconds ≠ 30.")
    if actual["read_timeout_seconds"] != int(EXPECTED_READ_TIMEOUT_SECONDS):
        raise PolicyArtifactMismatch("read_timeout_seconds ≠ 7200.")
    if actual["max_real_calls"] != MAX_REAL_CALLS:
        raise PolicyArtifactMismatch("max_real_calls ≠ 1.")
    if actual["max_attempts"] != MAX_ATTEMPTS:
        raise PolicyArtifactMismatch("max_attempts ≠ 1.")
    if actual["retry"] is not False:
        raise PolicyArtifactMismatch("retry doit être false.")
    if actual["fallback"] is not None:
        raise PolicyArtifactMismatch("fallback doit être none.")
    if actual["third_global_timeout_escalation_allowed"] is not False:
        raise PolicyArtifactMismatch("third_global_timeout_escalation_allowed doit être false.")
    if THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED is not False:
        raise PolicyArtifactMismatch("Constante d'escalade #3 ≠ false.")
    return {
        "status": "PASS",
        "source": source,
        "provider": EXPECTED_PROVIDER,
        "model": EXPECTED_MODEL,
        "matched": dict(actual),
    }
