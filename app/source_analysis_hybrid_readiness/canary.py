"""
Runner canary WIN001 — fail-safe.

Défaut : dry-run. Aucun engine.generate.
Exécution réelle : --execute-real + fenêtre explicite + allow_real_provider.
Ne consolide pas. Ne publie pas. Ne marque pas SUCCESS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.base import BaseAIEngine
from app.ai.settings import resolve_stage_settings
from app.ai.timeouts import diagnose_stage_timeout
from app.source_analysis.errors import WindowOrchestrationError
from app.source_analysis.hybrid_service import run_hybrid_source_analysis
from app.source_analysis.window_analyzer import build_window_ai_request
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_cache import inspect_window_cache
from app.source_analysis.window_fixtures import window_plan_from_inputs
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_orchestrator import orchestrate_windows
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    resolve_window_prompt_version,
    window_prompt_sha256,
)
from app.source_analysis.window_writer import (
    metadata_path,
    read_json_artifact,
    result_path,
    transport_path,
    windows_root,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
    AUTHORIZATION_SCOPE_REMAINING_WINDOWS,
    AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    AUTHORIZATION_SCOPE_WIN001_ONLY,
    AUTO_CONSOLIDATION,
    AUTO_CONTINUE,
    AUTO_FALLBACK,
    AUTO_PUBLICATION,
    AUTO_RETRY,
    CANARY_WINDOW_ID,
    MAX_ATTEMPTS,
    MAX_NEW_CALLS_REMAINING,
    MAX_NEW_CALLS_WIN001,
    SMALL_V21_EXECUTION_CONTRACT_NAME,
    TARGET_MODEL,
    TARGET_PROVIDER,
)
from app.source_analysis_hybrid_readiness.retry_audit import canary_retry_policy

CANDIDATE_PLANNER_VERSION = "window-planner-v2.1-small"

ALLOWED_SCOPES = frozenset(
    {
        AUTHORIZATION_SCOPE_WIN001_ONLY,
        AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
        AUTHORIZATION_SCOPE_REMAINING_WINDOWS,
        AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    }
)
WIN001_SCOPES = frozenset(
    {
        AUTHORIZATION_SCOPE_WIN001_ONLY,
        AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
        AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    }
)
REAL_EXECUTABLE_SCOPES = frozenset(
    {
        AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
        AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    }
)


class CanaryAuthorizationError(ValueError):
    """Échec d'autorisation avant tout appel provider."""


@dataclass
class CanaryRunResult:
    mode: str
    project_name: str
    window_id: str | None
    authorization_scope: str
    accepted: bool = False
    error: str | None = None
    engine_generate_attempted: bool = False
    provider_calls: int = 0
    consolidation_called: bool = False
    source_map_published: bool = False
    source_analysis_success: bool = False
    continued_to_next_window: bool = False
    dry_run: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "project_name": self.project_name,
            "window_id": self.window_id,
            "authorization_scope": self.authorization_scope,
            "accepted": self.accepted,
            "error": self.error,
            "engine_generate_attempted": self.engine_generate_attempted,
            "provider_calls": self.provider_calls,
            "consolidation_called": self.consolidation_called,
            "source_map_published": self.source_map_published,
            "source_analysis_success": self.source_analysis_success,
            "continued_to_next_window": self.continued_to_next_window,
            "dry_run": self.dry_run,
            "execution": self.execution,
        }


def validate_canary_authorization(
    *,
    window_id: str | None,
    authorization_scope: str,
    execute_real: bool,
    dry_run: bool,
    max_new_calls: int | None,
) -> None:
    if not window_id or not str(window_id).strip():
        raise CanaryAuthorizationError(
            "sélection de fenêtre obligatoire : l'absence ne signifie jamais "
            "toutes les fenêtres."
        )
    scope = str(authorization_scope or "").strip()
    if scope not in ALLOWED_SCOPES:
        raise CanaryAuthorizationError(f"authorization_scope inconnu : {scope!r}.")
    if execute_real and dry_run:
        raise CanaryAuthorizationError("--dry-run et --execute-real sont exclusifs.")
    if scope in WIN001_SCOPES:
        if window_id != CANARY_WINDOW_ID:
            raise CanaryAuthorizationError(
                f"{scope} n'autorise que {CANARY_WINDOW_ID}, reçu {window_id}."
            )
        if max_new_calls is not None and int(max_new_calls) != MAX_NEW_CALLS_WIN001:
            raise CanaryAuthorizationError(
                f"{scope} exige max_new_calls={MAX_NEW_CALLS_WIN001}."
            )
    if scope == AUTHORIZATION_SCOPE_REMAINING_WINDOWS:
        if window_id == CANARY_WINDOW_ID:
            raise CanaryAuthorizationError(
                "REMAINING_WINDOWS n'inclut pas WIN001."
            )
        if window_id not in {"WIN002", "WIN003"}:
            raise CanaryAuthorizationError(
                f"REMAINING_WINDOWS n'autorise que WIN002/WIN003, reçu {window_id}."
            )


def resolve_canary_planner_version(
    authorization_scope: str,
    planner_version: str | None = None,
) -> str:
    """
    SMALL_V21_WIN001_ONLY → window-planner-v2.1-small (jamais v2.0).
    Autres scopes → window-planner-v2.0. Un planner explicite incorrect échoue.
    """
    scope = str(authorization_scope or "").strip()
    if scope == AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY:
        chosen = str(planner_version or CANDIDATE_PLANNER_VERSION).strip()
        if chosen != CANDIDATE_PLANNER_VERSION:
            raise CanaryAuthorizationError(
                f"{AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY} exige "
                f"{CANDIDATE_PLANNER_VERSION}, reçu {chosen!r}."
            )
        return chosen
    chosen = str(planner_version or PLANNER_VERSION).strip()
    if chosen != PLANNER_VERSION:
        raise CanaryAuthorizationError(
            f"{scope or 'scope historique'} exige {PLANNER_VERSION}, "
            f"reçu {chosen!r}."
        )
    return chosen


def resolve_canary_plan(
    transcript,
    authorization_scope: str,
    *,
    planner_version: str | None = None,
    plan=None,
):
    required = resolve_canary_planner_version(authorization_scope, planner_version)
    if plan is not None:
        if getattr(plan, "planner_version", None) != required:
            raise CanaryAuthorizationError(
                f"plan.planner_version={getattr(plan, 'planner_version', None)!r} "
                f"≠ planner exigé {required}."
            )
        return plan
    if required == CANDIDATE_PLANNER_VERSION:
        from app.source_analysis_small_window_hierarchy.planner import (
            plan_windows_v21_small,
        )

        return plan_windows_v21_small(transcript)
    return plan_windows_v2(transcript)


def load_small_v21_execution_contract(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any] | None:
    from app.language_cleanup.transcript_source import audit_dir

    path = audit_dir(project_name, sortie_dir=sortie_dir) / SMALL_V21_EXECUTION_CONTRACT_NAME
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def validate_small_v21_fail_closed(
    *,
    authorization_scope: str,
    planner_version: str,
    window,
    prompt_version: str,
    window_input_hash: str,
    analysis_signature: str,
    expected: Mapping[str, Any] | None,
) -> None:
    if authorization_scope != AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY:
        raise CanaryAuthorizationError(
            f"scope {authorization_scope!r} n'est pas "
            f"{AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY}."
        )
    if planner_version != CANDIDATE_PLANNER_VERSION:
        raise CanaryAuthorizationError(
            f"planner {planner_version!r} ≠ {CANDIDATE_PLANNER_VERSION}."
        )
    if getattr(window, "planner_version", None) != CANDIDATE_PLANNER_VERSION:
        raise CanaryAuthorizationError(
            "fenêtre hors planner window-planner-v2.1-small."
        )
    if getattr(window, "window_id", None) != CANARY_WINDOW_ID:
        raise CanaryAuthorizationError(
            f"{AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY} n'autorise que "
            f"{CANARY_WINDOW_ID}."
        )
    if prompt_version != WINDOW_ANALYSIS_PROMPT_VERSION:
        raise CanaryAuthorizationError(
            f"{AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY} exige "
            f"{WINDOW_ANALYSIS_PROMPT_VERSION}."
        )
    if expected is None:
        raise CanaryAuthorizationError(
            "contrat d'exécution SMALL_V21 absent : POST provider refusé."
        )
    if str(expected.get("window_input_hash") or "") != window_input_hash:
        raise CanaryAuthorizationError(
            "window_input_hash ≠ identité SMALL_V21 figée du contrat."
        )
    if str(expected.get("analysis_signature") or "") != analysis_signature:
        raise CanaryAuthorizationError(
            "analysis_signature ≠ identité SMALL_V21 figée du contrat."
        )


def inspect_output_ceiling(
    project_name: str,
    window_id: str,
    *,
    windows_root_path: Path,
) -> dict[str, Any]:
    path = metadata_path(project_name, window_id, root=windows_root_path)
    tokens = None
    if path.is_file():
        status, meta = read_json_artifact(path)
        if status == "ok" and isinstance(meta, dict):
            obs = meta.get("observability") or {}
            tokens = obs.get("output_tokens")
            if tokens is None:
                tokens = (meta.get("provider") or {}).get("output_tokens")
    reached = isinstance(tokens, int) and int(tokens) >= int(WINDOW_MAX_OUTPUT_TOKENS)
    return {
        "output_tokens": tokens,
        "output_ceiling_reached": reached,
        "flag": "OUTPUT_CEILING_REACHED" if reached else None,
        "max_output": WINDOW_MAX_OUTPUT_TOKENS,
    }


def resolve_canary_prompt_version(
    authorization_scope: str,
    prompt_version: str | None = None,
    *,
    allow_real_provider: bool = False,
    execute_real: bool = False,
) -> str:
    """
    Sélection explicite. Historique WIN001_ONLY = 1.0.
    BOUNDED_WIN001_ONLY / SMALL_V21_WIN001_ONLY = window-analysis-1.1.
    Un appel provider réel refuse 1.0 : l'autorisation historique est consommée.
    """
    scope = str(authorization_scope or "").strip()
    if scope in {
        AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY,
        AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY,
    }:
        chosen = resolve_window_prompt_version(
            prompt_version or WINDOW_ANALYSIS_PROMPT_VERSION
        )
        if chosen != WINDOW_ANALYSIS_PROMPT_VERSION:
            raise CanaryAuthorizationError(
                f"{scope} exige {WINDOW_ANALYSIS_PROMPT_VERSION}, reçu {chosen}."
            )
        return chosen
    chosen = resolve_window_prompt_version(
        prompt_version or WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    if execute_real and allow_real_provider:
        if chosen != WINDOW_ANALYSIS_PROMPT_VERSION:
            raise CanaryAuthorizationError(
                "appel provider réel refusé : window-analysis-1.1 obligatoire "
                f"(reçu {chosen}). L'autorisation 1.0 est consommée."
            )
        if scope not in REAL_EXECUTABLE_SCOPES:
            raise CanaryAuthorizationError(
                "appel provider réel refusé : authorization_scope="
                f"{AUTHORIZATION_SCOPE_BOUNDED_WIN001_ONLY} ou "
                f"{AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY} obligatoire."
            )
    return chosen


def select_window_or_fail(plan, window_id: str):
    matches = [window for window in plan.windows if window.window_id == window_id]
    if len(matches) != 1:
        raise CanaryAuthorizationError(
            f"fenêtre {window_id} introuvable ou ambiguë dans le plan."
        )
    return matches[0]


def restrict_plan_to_window(transcript, plan, window_id: str):
    window = select_window_or_fail(plan, window_id)
    return window_plan_from_inputs(transcript, (window,))


def build_canary_anthropic_engine() -> AnthropicEngine:
    """
    Moteur Anthropic canary : max_attempts=1, modèle/stage verrouillés.

    N'appelle pas generate. get_engine_for_stage n'est PAS utilisé :
    il hériterait de AI_MAX_ATTEMPTS=3.
    """
    settings = resolve_stage_settings(STAGE_WINDOW)
    return AnthropicEngine(
        model=settings.model or TARGET_MODEL,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        retry_policy=canary_retry_policy(),
    )


def describe_canary_engine(engine: BaseAIEngine | None) -> dict[str, Any]:
    if engine is None:
        return {
            "instantiated": False,
            "provider": TARGET_PROVIDER,
            "model": TARGET_MODEL,
            "retry_max_attempts": MAX_ATTEMPTS,
        }
    policy = getattr(engine, "retry_policy", None) or getattr(
        engine, "_retry_policy", None
    )
    max_attempts = int(getattr(policy, "max_attempts", 0) or 0) if policy else 0
    model = None
    resolver = getattr(engine, "resolve_model", None)
    if callable(resolver):
        try:
            model = resolver()
        except Exception:
            model = getattr(engine, "_model", None)
    return {
        "instantiated": True,
        "class_name": type(engine).__name__,
        "provider": getattr(engine, "provider_name", None),
        "model": model,
        "retry_max_attempts": max_attempts,
        "is_anthropic": isinstance(engine, AnthropicEngine),
        "is_fake": type(engine).__name__ in {"FakeAIEngine", "WindowMappedFakeAI"},
    }


def dry_run_win001(
    project_name: str,
    *,
    window_id: str = CANARY_WINDOW_ID,
    authorization_scope: str = AUTHORIZATION_SCOPE_WIN001_ONLY,
    prompt_version: str | None = None,
    planner_version: str | None = None,
    sortie_dir: Path | None = None,
    windows_root_override: Path | None = None,
    transcript=None,
    plan=None,
) -> dict[str, Any]:
    validate_canary_authorization(
        window_id=window_id,
        authorization_scope=authorization_scope,
        execute_real=False,
        dry_run=True,
        max_new_calls=MAX_NEW_CALLS_WIN001,
    )
    chosen_prompt = resolve_canary_prompt_version(
        authorization_scope, prompt_version
    )
    chosen_planner = resolve_canary_planner_version(
        authorization_scope, planner_version
    )
    if transcript is None:
        transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    full_plan = resolve_canary_plan(
        transcript,
        authorization_scope,
        planner_version=chosen_planner,
        plan=plan,
    )
    window = select_window_or_fail(full_plan, window_id)
    bundle = build_window_ai_request(
        window, transcript, prompt_version=chosen_prompt
    )
    timeout = diagnose_stage_timeout(STAGE_WINDOW)
    root = windows_root_override or windows_root(project_name, sortie_dir=sortie_dir)
    inspection = inspect_window_cache(
        window,
        transcript,
        windows_root=root,
        project_name=project_name,
        expected_signature=bundle.signature,
    )
    system = bundle.system_prompt or ""
    user = bundle.request.prompt or ""
    from app.source_analysis_window_output_bounding.preflight import _payload_bytes

    return {
        "mode": "DRY_RUN",
        "authorization_scope": authorization_scope,
        "planner_version": chosen_planner,
        "window_id": window_id,
        "selected_windows": [window_id],
        "plan_window_count": full_plan.window_count,
        "owned_src_count": window.owned_src_count,
        "first_src": window.first_owned_src_ref,
        "last_src": window.last_owned_src_ref,
        "word_count": window.word_count,
        "window_input_hash": window.input_hash,
        "provider": TARGET_PROVIDER,
        "model": TARGET_MODEL,
        "stage": bundle.request.stage,
        "prompt_version": bundle.signature_inputs.prompt_version,
        "prompt_sha256": window_prompt_sha256(bundle.system_prompt),
        "granularity_policy_version": (
            POLICY_VERSION
            if chosen_prompt == WINDOW_ANALYSIS_PROMPT_VERSION
            else None
        ),
        "response_schema": "semantic-transport-v1",
        "response_schema_sha256": bundle.response_schema_sha256,
        "temperature": bundle.request.temperature,
        "output_language": transcript.primary_language,
        "max_output_tokens": bundle.request.max_output_tokens,
        "system_chars": len(system),
        "user_chars": len(user),
        "combined_chars": len(system) + len(user),
        "payload_bytes": _payload_bytes(bundle.request),
        "system_prompt_tokens": bundle.token_estimate["system_tokens"],
        "user_prompt_tokens": bundle.token_estimate["user_tokens"],
        "estimated_input_tokens": bundle.token_estimate["total_tokens"],
        "connect_timeout_seconds": timeout["connect_seconds"],
        "read_timeout_seconds": timeout["read_seconds"],
        "timeout_connect_source": timeout["connect_source"],
        "timeout_read_source": timeout["read_source"],
        "analysis_signature": bundle.signature,
        "cache_state": inspection.cache_state,
        "transport_exists": inspection.transport_present,
        "result_exists": inspection.result_present,
        "max_new_calls": MAX_NEW_CALLS_WIN001,
        "max_attempts": MAX_ATTEMPTS,
        "auto_retry": AUTO_RETRY,
        "auto_continue": AUTO_CONTINUE,
        "auto_fallback": AUTO_FALLBACK,
        "auto_consolidation": AUTO_CONSOLIDATION,
        "auto_publication": AUTO_PUBLICATION,
        "auto_reconstruction": False,
        "engine_generate": False,
        "would_call_ai": True,
        "execution": False,
        "actual_real_provider_calls": 0,
        "artifact_paths": {
            "transport": str(transport_path(project_name, window_id, root=root)),
            "result": str(result_path(project_name, window_id, root=root)),
            "metadata": str(metadata_path(project_name, window_id, root=root)),
        },
        "transcript_text_included": False,
        "secrets_included": False,
    }


def run_win001_canary(
    project_name: str,
    *,
    window_id: str | None,
    dry_run: bool = True,
    execute_real: bool = False,
    authorization_scope: str = AUTHORIZATION_SCOPE_WIN001_ONLY,
    max_new_calls: int | None = None,
    engine=None,
    allow_real_provider: bool = False,
    allow_consolidation: bool = False,
    allow_publication: bool = False,
    prompt_version: str | None = None,
    planner_version: str | None = None,
    sortie_dir: Path | None = None,
    windows_root_override: Path | None = None,
    transcript=None,
    plan=None,
) -> CanaryRunResult:
    """
    Point d'entrée unique. Fail-safe par défaut.

    allow_real_provider=False même si execute_real : le CLI seul le lève.
    """
    budget = (
        MAX_NEW_CALLS_WIN001
        if authorization_scope in WIN001_SCOPES
        else (max_new_calls if max_new_calls is not None else MAX_NEW_CALLS_REMAINING)
    )
    if authorization_scope in WIN001_SCOPES:
        budget = MAX_NEW_CALLS_WIN001
    result = CanaryRunResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        project_name=project_name,
        window_id=window_id,
        authorization_scope=authorization_scope,
    )
    try:
        validate_canary_authorization(
            window_id=window_id,
            authorization_scope=authorization_scope,
            execute_real=execute_real and not dry_run,
            dry_run=dry_run or not execute_real,
            max_new_calls=budget,
        )
    except CanaryAuthorizationError as exc:
        result.accepted = False
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    try:
        chosen_prompt = resolve_canary_prompt_version(
            authorization_scope,
            prompt_version,
            allow_real_provider=allow_real_provider,
            execute_real=execute_real and not dry_run,
        )
        chosen_planner = resolve_canary_planner_version(
            authorization_scope, planner_version
        )
    except CanaryAuthorizationError as exc:
        result.accepted = False
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if allow_consolidation or allow_publication:
        result.accepted = False
        result.error = "consolidation et publication interdites en canary."
        result.mode = "REJECTED"
        return result

    if execute_real and engine is None and not allow_real_provider:
        result.accepted = False
        result.error = (
            "exécution réelle refusée : allow_real_provider=false "
            "(défaut fail-safe)."
        )
        result.mode = "REJECTED"
        return result

    if dry_run or not execute_real:
        result.accepted = True
        result.dry_run = dry_run_win001(
            project_name,
            window_id=str(window_id),
            authorization_scope=authorization_scope,
            prompt_version=chosen_prompt,
            planner_version=chosen_planner,
            sortie_dir=sortie_dir,
            windows_root_override=windows_root_override,
            transcript=transcript,
            plan=plan,
        )
        return result

    injected = transcript is not None or plan is not None
    if transcript is None:
        transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    try:
        full_plan = resolve_canary_plan(
            transcript,
            authorization_scope,
            planner_version=chosen_planner,
            plan=plan,
        )
    except CanaryAuthorizationError as exc:
        result.accepted = False
        result.error = str(exc)
        result.mode = "REJECTED"
        return result
    window = select_window_or_fail(full_plan, str(window_id))
    bundle = build_window_ai_request(
        window, transcript, prompt_version=chosen_prompt
    )
    if authorization_scope == AUTHORIZATION_SCOPE_SMALL_V21_WIN001_ONLY:
        try:
            expected = None
            if not injected:
                expected = load_small_v21_execution_contract(
                    project_name, sortie_dir=sortie_dir
                )
                validate_small_v21_fail_closed(
                    authorization_scope=authorization_scope,
                    planner_version=chosen_planner,
                    window=window,
                    prompt_version=chosen_prompt,
                    window_input_hash=window.input_hash,
                    analysis_signature=bundle.signature,
                    expected=expected,
                )
            elif (
                window.planner_version != CANDIDATE_PLANNER_VERSION
                or chosen_prompt != WINDOW_ANALYSIS_PROMPT_VERSION
                or str(window_id) != CANARY_WINDOW_ID
            ):
                raise CanaryAuthorizationError(
                    "SMALL_V21_WIN001_ONLY refuse planner/prompt/fenêtre hors contrat."
                )
        except CanaryAuthorizationError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            return result
    scoped = restrict_plan_to_window(transcript, full_plan, str(window_id))
    root = windows_root_override or windows_root(project_name, sortie_dir=sortie_dir)

    if engine is None:
        engine = build_canary_anthropic_engine()

    before = int(getattr(engine, "call_count", 0) or 0)
    result.accepted = True
    try:
        orchestration = orchestrate_windows(
            scoped,
            transcript,
            windows_root=root,
            engine=engine,
            project_name=project_name,
            max_new_calls=budget,
            prompt_version=chosen_prompt,
        )
    except KeyboardInterrupt:
        result.error = "KeyboardInterrupt"
        result.engine_generate_attempted = True
        result.provider_calls = int(getattr(engine, "call_count", 0) or 0) - before
        return result
    except WindowOrchestrationError as exc:
        result.error = str(exc)
        result.engine_generate_attempted = True
        result.provider_calls = int(getattr(engine, "call_count", 0) or 0) - before
        return result

    after = int(getattr(engine, "call_count", 0) or 0)
    result.provider_calls = max(after - before, orchestration.new_calls_consumed)
    result.engine_generate_attempted = orchestration.new_calls_consumed > 0
    result.continued_to_next_window = orchestration.generated_windows > 1
    result.execution = {
        "window_id": window_id,
        "total_windows_in_scope": orchestration.total_windows,
        "ready_windows": orchestration.ready_windows,
        "generated_windows": orchestration.generated_windows,
        "failed_windows": orchestration.failed_windows,
        "pending_windows": orchestration.pending_windows,
        "new_calls_consumed": orchestration.new_calls_consumed,
        "max_new_calls": orchestration.max_new_calls,
        "all_windows_ready": orchestration.all_windows_ready,
        "statuses": [status.to_dict() for status in orchestration.statuses],
        "engine": describe_canary_engine(engine),
        "source_map_path_exists": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
        "planner_version": chosen_planner,
        "window_input_hash": window.input_hash,
        "analysis_signature": bundle.signature,
        "output_ceiling": inspect_output_ceiling(
            project_name, str(window_id), windows_root_path=root
        ),
    }
    if result.execution["output_ceiling"]["output_ceiling_reached"]:
        result.execution["canary_success"] = False
        result.execution["stop_reason"] = "OUTPUT_CEILING_REACHED"
    # Garde-fou : le canary n'appelle jamais le service hybride complet.
    result.consolidation_called = False
    result.source_map_published = False
    result.source_analysis_success = False
    return result


def canary_cannot_consolidate() -> bool:
    return run_hybrid_source_analysis is not None and AUTO_CONSOLIDATION is False
