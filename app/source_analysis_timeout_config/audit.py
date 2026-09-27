"""
Préflight offline des timeouts connect/read — Phase 3B.5.1.

Aucun engine.generate(), aucun requests.post(), aucun appel réseau.
Diagnostic déterministe : pas d'horodatage, pas d'UUID.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any, Mapping

from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.lmstudio import LMStudioEngine
from app.ai.providers.ollama import OllamaEngine
from app.ai.providers.openai_engine import OpenAIEngine
from app.ai.settings import default_timeout_seconds, resolve_stage_settings
from app.ai.timeouts import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    diagnose_stage_timeout,
    resolve_ai_timeouts,
)
from app.file_utils import content_hash
from app.project_state import load_project_state
from app.source_analysis import state as state_module
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.schema import schema_fingerprint
from app.source_analysis.ultra_compact_schema import ultra_compact_schema_fingerprint
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.constants import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    REAL_CALL_TIMEOUT_SECONDS,
    STAGE,
)
from app.source_analysis_timeout_config.constants import (
    AUTHORIZATION_WAIT_CAUSED_TIMEOUT,
    BASELINE_PASSED,
    EDITORIAL_STAGES,
    EXACT_NEXT_READ_TIMEOUT_AUTHORIZED,
    FINAL_FAILED,
    FINAL_PASSED,
    FINAL_RETRY_AUTHORIZED,
    MODE,
    NEW_ANTHROPIC_CALL_AUTHORIZED,
    NEXT_PAID_CALL_AUTHORIZED,
    NEXT_PHASE,
    PHASE,
    PREVIOUS_CLASSIFICATION,
    PREVIOUS_EFFECTIVE_TIMEOUT_SECONDS,
    REQUIRES_HUMAN_REVIEW,
    SCHEMA_VERSION,
)
from app.source_analysis_ultra_compact_canary.architecture import (
    production_generation_c_schema,
)
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema

_EMPTY_NETWORK = {
    "anthropic": 0,
    "openai": 0,
    "whisper": 0,
    "ollama": 0,
    "lm_studio": 0,
    "other": 0,
}

_PACKAGE_DIR = Path(__file__).resolve().parent


def package_calls_generate_or_post() -> list[str]:
    hits: list[str] = []
    forbidden = {"generate", "post_json", "requests"}
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                if "requests" in names:
                    hits.append(f"{path.name}:import requests")
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root == "requests":
                    hits.append(f"{path.name}:from requests")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"generate", "post"}:
                    hits.append(f"{path.name}:{node.func.attr}")
    return hits


def assert_offline_package() -> None:
    hits = package_calls_generate_or_post()
    if hits:
        raise RuntimeError("Chemin réseau/generate interdit : " + ", ".join(hits))


def assert_source_map_absent(
    project_name: str, *, sortie_dir: Path | None = None
) -> None:
    path = source_map_path(project_name, sortie_dir=sortie_dir)
    if path.exists():
        raise RuntimeError(f"source_map de production présent : {path}")


def inspect_project_state(project_name: str) -> dict[str, Any]:
    state = load_project_state(project_name)
    block = state_module.load_state_block(state) or {}
    return {
        "status": block.get("status"),
        "error": block.get("error"),
        "path": block.get("path"),
    }


def runner_passes_hardcoded_timeout() -> bool:
    from app.source_analysis_global_clean import runner as runner_module

    source = inspect.getsource(runner_module._execute)
    return "timeout_seconds=REAL_CALL_TIMEOUT_SECONDS" in source


def sibling_real_run_passes_hardcoded_timeout() -> bool:
    from app.source_analysis import real_run as real_run_module

    source = inspect.getsource(real_run_module)
    return "timeout_seconds=REAL_CALL_TIMEOUT_SECONDS" in source


def http_uses_tuple_timeout() -> bool:
    from app.ai.providers import _http as http_module

    source = inspect.getsource(http_module.post_json)
    return "timeout_arg" in source and "requests_timeout_argument" in source


def generation_c_hashes() -> dict[str, str]:
    raw = production_generation_c_schema()
    adapted = prepare_anthropic_json_schema(raw)
    return {
        "raw_sha256": ultra_compact_schema_fingerprint(raw),
        "anthropic_sha256": schema_fingerprint(adapted),
        "raw_matches_historical": ultra_compact_schema_fingerprint(raw)
        == GENERATION_C_RAW_SHA256_3B43,
        "anthropic_matches_historical": schema_fingerprint(adapted)
        == GENERATION_C_ANTHROPIC_SHA256_3B43,
    }


def _stage_block(stage: str) -> dict[str, Any]:
    return diagnose_stage_timeout(stage)


def _provider_defaults() -> dict[str, Any]:
    from app.ai.contracts import AIRequest

    request = AIRequest(prompt="timeout-config-probe")
    engines = {
        "anthropic": AnthropicEngine(model=EXPECTED_MODEL, api_key="unused"),
        "openai": OpenAIEngine(model="gpt-5.6-terra"),
        "ollama": OllamaEngine(),
        "lmstudio": LMStudioEngine(),
    }
    resolved = {}
    for name, engine in engines.items():
        timeouts = engine.resolve_timeouts(request)
        resolved[name] = {
            "connect_seconds": timeouts.connect_seconds,
            "read_seconds": timeouts.read_seconds,
            "connect_source": timeouts.connect_source,
            "read_source": timeouts.read_source,
            "uses_http_helper": name != "openai",
        }
    return resolved


def build_timeout_config_audit() -> dict[str, Any]:
    assert_offline_package()
    defaults = resolve_ai_timeouts()
    stages = {stage: _stage_block(stage) for stage in EDITORIAL_STAGES}
    generation = generation_c_hashes()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "previous_failure": {
            "classification": PREVIOUS_CLASSIFICATION,
            "effective_timeout_seconds": PREVIOUS_EFFECTIVE_TIMEOUT_SECONDS,
            "authorization_wait_caused_timeout": AUTHORIZATION_WAIT_CAUSED_TIMEOUT,
        },
        "architecture": {
            "legacy_scalar_timeout": (
                "REAL_CALL_TIMEOUT_SECONDS=3600 was the 3B Final HTTP scalar; "
                "it is now historical and is not passed to get_ai_engine."
            ),
            "new_timeout_model": "AITimeoutConfig(connect_seconds, read_seconds)",
            "connect_read_separated": True,
            "stage_specific_supported": True,
            "legacy_constant_still_3600": float(REAL_CALL_TIMEOUT_SECONDS) == 3600.0,
            "legacy_constant_controls_runner": runner_passes_hardcoded_timeout(),
            "total_wall_clock_timeout": False,
        },
        "resolution": {
            "precedence": [
                "request.timeout_seconds → read only",
                "engine.timeout_seconds → read only",
                "env AI_<STAGE>_READ_TIMEOUT_SECONDS / CONNECT",
                "StageSettings.read_timeout_seconds / connect_timeout_seconds",
                "provider config_timeout() if it differs from the global default",
                "env AI_DEFAULT_READ_TIMEOUT_SECONDS / CONNECT",
                "AI_DEFAULT_TIMEOUT_SECONDS / AI_DEFAULT_CONNECT_TIMEOUT_SECONDS",
            ],
            "defaults": {
                "connect_seconds": defaults.connect_seconds,
                "read_seconds": defaults.read_seconds,
                "connect_source": defaults.connect_source,
                "read_source": defaults.read_source,
                "documented_connect_default": DEFAULT_CONNECT_TIMEOUT_SECONDS,
                "documented_read_default": default_timeout_seconds(),
            },
        },
        "stages": stages,
        "http": {
            "requests_timeout_shape": "tuple",
            "connect_read_distinct": True,
            "tuple_used": http_uses_tuple_timeout(),
            "total_timeout": None,
        },
        "providers": _provider_defaults(),
        "observability": {
            "monotonic_timing": True,
            "elapsed_available": True,
            "effective_timeout_available": True,
            "timeout_kind": ["connect", "read", "unknown"],
            "heartbeat_local": False,
            "streaming": False,
            "percent_progress": False,
        },
        "sibling_real_run": {
            "constant_exists": True,
            "constant_seconds": 3600.0,
            "passed_to_engine": sibling_real_run_passes_hardcoded_timeout(),
            "role": (
                "Historical sibling of the 3B Final runner. The constant remains "
                "as documentation; it is no longer passed to get_ai_engine."
            ),
        },
        "integrity": {
            "prompt_version": SOURCE_ANALYZER_PROMPT_VERSION,
            "generation_c": generation,
            "expected_provider": EXPECTED_PROVIDER,
            "expected_model": EXPECTED_MODEL,
            "expected_stage": STAGE,
        },
        "production_decision": {
            "exact_next_read_timeout_authorized": EXACT_NEXT_READ_TIMEOUT_AUTHORIZED,
            "next_paid_call_authorized": NEXT_PAID_CALL_AUTHORIZED,
            "new_anthropic_call_authorized": NEW_ANTHROPIC_CALL_AUTHORIZED,
            "final_retry_authorized": FINAL_RETRY_AUTHORIZED,
            "requires_human_review": REQUIRES_HUMAN_REVIEW,
            "next_phase": NEXT_PHASE,
            "architecture_ready_for_operational_long_read": True,
        },
        "tests": {
            "baseline_passed": BASELINE_PASSED,
            "final_passed": FINAL_PASSED,
            "failed": FINAL_FAILED,
        },
        "network": dict(_EMPTY_NETWORK),
        "engine_generate": 0,
    }
    return payload


def diagnostic_sha256(payload: Mapping[str, Any]) -> str:
    encoded = __import__("json").dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    return content_hash(encoded)


def build_deterministic_audit() -> tuple[dict[str, Any], str, str]:
    first = build_timeout_config_audit()
    second = build_timeout_config_audit()
    sha1 = diagnostic_sha256(first)
    sha2 = diagnostic_sha256(second)
    if sha1 != sha2:
        raise RuntimeError("Diagnostic 3B.5.1 non déterministe : SHA run1 ≠ run2.")
    return first, sha1, sha2
