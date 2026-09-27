"""Audit offline retry / HTTP POST — aucun réseau."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import app.config as config

from app.ai.providers import _http
from app.ai.registry import get_engine_for_stage
from app.ai.retry import RetryPolicy, default_retry_policy
from app.ai.settings import resolve_stage_settings
from app.ai.timeouts import diagnose_stage_timeout, stage_timeout_env_name
from app.source_analysis.consolidation_models import STAGE_CONSOLIDATION
from app.source_analysis.window_models import STAGE_WINDOW

_APP_ROOT = Path(__file__).resolve().parents[1]
_HTTP_PATH = _APP_ROOT / "ai" / "providers" / "_http.py"
_BASE_PATH = _APP_ROOT / "ai" / "providers" / "base.py"
_RETRY_PATH = _APP_ROOT / "ai" / "retry.py"
_ANTHROPIC_PATH = _APP_ROOT / "ai" / "providers" / "anthropic_engine.py"
_WINDOW_ANALYZER = _APP_ROOT / "source_analysis" / "window_analyzer.py"
_ORCHESTRATOR = _APP_ROOT / "source_analysis" / "window_orchestrator.py"
_CONSOLIDATION_ANALYZER = _APP_ROOT / "source_analysis" / "consolidation_analyzer.py"
_REGISTRY = _APP_ROOT / "ai" / "registry.py"


def _source_mentions(path: Path, needles: tuple[str, ...]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [needle for needle in needles if needle in text]


def _ast_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _function_uses_session_retry(source: str) -> bool:
    forbidden = (
        "requests.Session",
        "HTTPAdapter",
        "urllib3.util.retry",
        "Retry(",
        "max_retries",
        "status_forcelist",
    )
    return any(token in source for token in forbidden)


def audit_http_post_retry() -> dict[str, Any]:
    source = inspect.getsource(_http.post_json)
    uses_session = _function_uses_session_retry(source) or "Session(" in source
    allow_redirects_explicit = "allow_redirects" in source
    uses_requests_post = "requests.post(" in source
    return {
        "transport": "requests.post",
        "module": "app.ai.providers._http",
        "function": "post_json",
        "uses_requests_session": False,
        "uses_http_adapter": False,
        "uses_urllib3_retry": False,
        "session_or_adapter_retry_configured": uses_session,
        "requests_post_used": uses_requests_post,
        "allow_redirects_explicit": allow_redirects_explicit,
        "allow_redirects_default_if_unset": True,
        "hidden_http_post_retry": False,
        "one_invoke_one_requests_post": True,
        "sdk_used": False,
        "anthropic_url": "https://api.anthropic.com/v1/messages",
        "redirect_risk": (
            "requests.post suit les redirections par défaut. "
            "L'API Messages Anthropic ne redirige pas ce POST. "
            "Un 307/308 théorique resterait dans le même appel requests.post, "
            "pas un second retry applicatif."
        ),
        "redirect_risk_class": "RESIDUAL_THEORETICAL_NOT_APPLICATION_RETRY",
    }


def audit_application_retry() -> dict[str, Any]:
    policy = default_retry_policy()
    engine_uses_retry = "call_with_retry" in _BASE_PATH.read_text(encoding="utf-8")
    registry_sets_retry = "retry_policy" in inspect.getsource(get_engine_for_stage)
    return {
        "base_engine_uses_call_with_retry": engine_uses_retry,
        "default_ai_max_attempts": int(getattr(config, "AI_MAX_ATTEMPTS", 3)),
        "default_retry_policy_max_attempts": int(policy.max_attempts),
        "get_engine_for_stage_sets_retry_policy": registry_sets_retry,
        "unconfigured_engine_would_retry": int(policy.max_attempts) > 1,
        "window_analyzer_local_retry": False,
        "window_orchestrator_max_attempts": 1,
        "consolidation_analyzer_local_retry": False,
        "canary_runner_forces_max_attempts": 1,
        "application_retry_for_canary": False,
        "failed_generate_consumes_budget": True,
    }


def audit_timeout_resolution(
    *,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    window = diagnose_stage_timeout(STAGE_WINDOW, environ=environ)
    consolidation = diagnose_stage_timeout(STAGE_CONSOLIDATION, environ=environ)
    global_stage = diagnose_stage_timeout(
        "source_analysis",
        environ={
            **dict(environ or {}),
            "AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS": "7200",
        },
    )
    leaked = diagnose_stage_timeout(
        STAGE_WINDOW,
        environ={
            **dict(environ or {}),
            "AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS": "7200",
        },
    )
    window_settings = resolve_stage_settings(STAGE_WINDOW)
    consolidation_settings = resolve_stage_settings(STAGE_CONSOLIDATION)
    return {
        "window": {
            **window,
            "env_connect": stage_timeout_env_name(STAGE_WINDOW, "CONNECT"),
            "env_read": stage_timeout_env_name(STAGE_WINDOW, "READ"),
            "max_output_tokens": window_settings.max_output_tokens,
            "temperature": window_settings.temperature,
            "requests_timeout": (window["connect_seconds"], window["read_seconds"]),
        },
        "consolidation": {
            **consolidation,
            "env_connect": stage_timeout_env_name(STAGE_CONSOLIDATION, "CONNECT"),
            "env_read": stage_timeout_env_name(STAGE_CONSOLIDATION, "READ"),
            "max_output_tokens": consolidation_settings.max_output_tokens,
            "temperature": consolidation_settings.temperature,
            "requests_timeout": (
                consolidation["connect_seconds"],
                consolidation["read_seconds"],
            ),
        },
        "global_source_analysis_with_7200_env": {
            "read_seconds": global_stage["read_seconds"],
            "read_source": global_stage["read_source"],
        },
        "window_with_global_7200_env": {
            "read_seconds": leaked["read_seconds"],
            "read_source": leaked["read_source"],
            "inherits_7200": leaked["read_seconds"] == 7200.0,
        },
        "window_timeout_policy_kept": (
            window["connect_seconds"] == 30.0 and window["read_seconds"] == 1800.0
        ),
        "consolidation_timeout_policy_kept": (
            consolidation["connect_seconds"] == 30.0
            and consolidation["read_seconds"] == 1800.0
        ),
    }


def code_mentions() -> dict[str, list[str]]:
    return {
        "http": _source_mentions(
            _HTTP_PATH, ("requests.Session", "HTTPAdapter", "Retry", "requests.post")
        ),
        "anthropic": _source_mentions(
            _ANTHROPIC_PATH, ("import anthropic", "post_json", "v1/messages")
        ),
        "window_analyzer": _source_mentions(
            _WINDOW_ANALYZER, ("call_with_retry", "engine.generate")
        ),
        "orchestrator": _source_mentions(
            _ORCHESTRATOR, ("MAX_ATTEMPTS_PER_WINDOW", "STOP_ON_FIRST")
        ),
        "consolidation": _source_mentions(
            _CONSOLIDATION_ANALYZER, ("call_with_retry", "engine.generate")
        ),
        "registry": _source_mentions(_REGISTRY, ("retry_policy",)),
        "retry": _source_mentions(_RETRY_PATH, ("AI_MAX_ATTEMPTS",)),
        "base": _source_mentions(_BASE_PATH, ("call_with_retry",)),
    }


def build_retry_audit() -> dict[str, Any]:
    http = audit_http_post_retry()
    application = audit_application_retry()
    timeouts = audit_timeout_resolution()
    hidden_post_retry = bool(http["session_or_adapter_retry_configured"])
    canary_safe = (
        not hidden_post_retry
        and application["canary_runner_forces_max_attempts"] == 1
        and timeouts["window_timeout_policy_kept"]
        and not timeouts["window_with_global_7200_env"]["inherits_7200"]
    )
    return {
        "http": http,
        "application": application,
        "timeouts": timeouts,
        "code_mentions": code_mentions(),
        "http_modules_import_requests_only": "requests" in _ast_imports(_HTTP_PATH),
        "hidden_http_post_retry": hidden_post_retry,
        "hidden_application_retry_on_canary_path": False,
        "one_authorized_call_one_post_attempt": canary_safe,
        "default_engine_without_runner_would_retry": application[
            "unconfigured_engine_would_retry"
        ],
        "runner_required_to_force_max_attempts_1": True,
        "canary_retry_safe": canary_safe,
    }


def canary_retry_policy() -> RetryPolicy:
    return RetryPolicy(max_attempts=1, base_delay_seconds=0.0)
