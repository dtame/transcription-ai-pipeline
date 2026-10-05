"""
Generic provider runtime preflight.

Must run before a one-shot execution lock is consumed. Never opens a
provider HTTP connection. Never serializes API keys.
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from app.ai.contracts import AIRequest
from app.ai.errors import AIConfigurationError, AIProviderUnavailableError
from app.ai.openai_compat import (
    CONFIDENCE_UNKNOWN,
    PRODUCTION_OPENAI_ENDPOINT,
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    assert_no_conflicting_token_fields,
    conflicting_token_fields,
    production_openai_endpoint,
    resolve_openai_token_contract,
)
from app.ai.registry import available_providers, get_ai_engine, get_engine_class
from app.ai.settings import (
    ENV_ANTHROPIC_API_KEY,
    ENV_OPENAI_API_KEY,
    get_api_key,
)

REASON_PROVIDER_RUNTIME_NOT_READY = "PROVIDER_RUNTIME_NOT_READY"
REASON_PROVIDER_CREDENTIAL_NOT_READY = "PROVIDER_CREDENTIAL_NOT_READY"
REASON_PROVIDER_NOT_REGISTERED = "PROVIDER_NOT_REGISTERED"
REASON_PROVIDER_REQUEST_INCOMPATIBLE = "PROVIDER_REQUEST_INCOMPATIBLE"

READY = "READY"
READY_WITH_SERVER_UNVERIFIED_FIELDS = "READY_WITH_SERVER_UNVERIFIED_FIELDS"
NOT_READY = "NOT_READY"

SECRET_FIELD_NAMES = frozenset(
    {
        "api_key",
        "openai_api_key",
        "anthropic_api_key",
        "authorization",
        "x-api-key",
        "x_api_key",
        "token",
        "secret",
        "password",
    }
)

REMOTE_OPENAI_METHODS = (
    "chat.completions.create",
    "responses.create",
    "models.list",
    "completions.create",
)


@dataclass(frozen=True)
class ProviderRuntimeSpec:
    name: str
    env_var: str | None
    config_fallback: str | None
    required_module: str | None
    required_symbol: str | None
    min_major: int | None
    uses_official_sdk: bool
    default_output_mode: str | None = None


PROVIDER_SPECS: dict[str, ProviderRuntimeSpec] = {
    "openai": ProviderRuntimeSpec(
        name="openai",
        env_var=ENV_OPENAI_API_KEY,
        config_fallback="OPENAI_API_KEY",
        required_module="openai",
        required_symbol="OpenAI",
        min_major=1,
        uses_official_sdk=True,
        default_output_mode="json_object",
    ),
    "anthropic": ProviderRuntimeSpec(
        name="anthropic",
        env_var=ENV_ANTHROPIC_API_KEY,
        config_fallback=None,
        required_module="requests",
        required_symbol=None,
        min_major=None,
        uses_official_sdk=False,
        default_output_mode=None,
    ),
    "ollama": ProviderRuntimeSpec(
        name="ollama",
        env_var=None,
        config_fallback=None,
        required_module="requests",
        required_symbol=None,
        min_major=None,
        uses_official_sdk=False,
    ),
    "lmstudio": ProviderRuntimeSpec(
        name="lmstudio",
        env_var=None,
        config_fallback=None,
        required_module="requests",
        required_symbol=None,
        min_major=None,
        uses_official_sdk=False,
    ),
    "fake": ProviderRuntimeSpec(
        name="fake",
        env_var=None,
        config_fallback=None,
        required_module=None,
        required_symbol=None,
        min_major=None,
        uses_official_sdk=False,
    ),
}


@dataclass
class ProviderCallAccounting:
    """Future counters. Do not retroactively rewrite historical 4B.2.4 metrics."""

    authorized_calls: int = 0
    execution_attempts: int = 0
    remote_invocations: int = 0
    http_requests: int = 0
    provider_responses: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class ProviderReadiness:
    ready: bool
    primary_reason: str | None
    reasons: list[str] = field(default_factory=list)
    provider: str = ""
    provider_registered: bool = False
    sdk_import: str = "NOT_REQUIRED"
    sdk_version: str | None = None
    sdk_supported: str = "NOT_REQUIRED"
    credential_available: str = "NO"
    client_construction: str = "SKIPPED"
    provider_initialization: str = "FAIL"
    model_resolution: str = "SKIPPED"
    request_construction: str = "SKIPPED"
    output_mode_supported: str = "SKIPPED"
    endpoint_selected: str = "SKIPPED"
    token_parameter: str | None = None
    token_parameter_supported: str = "SKIPPED"
    request_serializable: str = "SKIPPED"
    unsupported_optional_parameters: str = "SKIPPED"
    readiness_class: str = NOT_READY
    network_calls: int = 0
    remote_invocations: int = 0
    http_requests: int = 0
    secrets_included: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "ready": self.ready,
            "primary_reason": self.primary_reason,
            "reasons": list(self.reasons),
            "provider": self.provider,
            "provider_registered": self.provider_registered,
            "SDK_IMPORT": self.sdk_import,
            "sdk_version": self.sdk_version,
            "sdk_supported": self.sdk_supported,
            "CREDENTIAL_AVAILABLE": self.credential_available,
            "CLIENT_CONSTRUCTION": self.client_construction,
            "PROVIDER_INITIALIZATION": self.provider_initialization,
            "MODEL_RESOLUTION": self.model_resolution,
            "REQUEST_CONSTRUCTION": self.request_construction,
            "output_mode_supported": self.output_mode_supported,
            "ENDPOINT_SELECTED": self.endpoint_selected,
            "token_parameter": self.token_parameter,
            "token_parameter_supported": self.token_parameter_supported,
            "REQUEST_SERIALIZABLE": self.request_serializable,
            "unsupported_optional_parameters": self.unsupported_optional_parameters,
            "readiness_class": self.readiness_class,
            "NETWORK_CALLS": self.network_calls,
            "remote_invocations": self.remote_invocations,
            "http_requests": self.http_requests,
            "secrets_included": False,
            "details": dict(self.details),
        }
        return redact_secrets(payload)


def parse_version(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    parts: list[int] = []
    for token in str(version).split("."):
        digits = ""
        for char in token:
            if char.isdigit():
                digits += char
            else:
                break
        if digits:
            parts.append(int(digits))
    return tuple(parts)


def sdk_version_supported(version: str | None, *, min_major: int | None) -> bool:
    if min_major is None:
        return True
    parsed = parse_version(version)
    return bool(parsed) and parsed[0] >= int(min_major)


def collect_known_secrets(*values: str | None) -> list[str]:
    secrets: list[str] = []
    for value in values:
        text = str(value or "")
        if len(text) >= 8:
            secrets.append(text)
    return secrets


def redact_secrets(payload: Any, secrets: Sequence[str] | None = None) -> Any:
    hidden = [item for item in (secrets or ()) if item]
    if isinstance(payload, Mapping):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            if str(key).lower() in SECRET_FIELD_NAMES:
                redacted[key] = "REDACTED"
            else:
                redacted[key] = redact_secrets(value, hidden)
        return redacted
    if isinstance(payload, list):
        return [redact_secrets(item, hidden) for item in payload]
    if isinstance(payload, tuple):
        return [redact_secrets(item, hidden) for item in payload]
    if isinstance(payload, str):
        text = payload
        for secret in hidden:
            if secret and secret in text:
                text = text.replace(secret, "REDACTED")
        return text
    return payload


def import_provider_sdk(module_name: str) -> Any:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        raise ImportError(f"module {module_name!r} is not installed")
    return importlib.import_module(module_name)


def inspect_sdk(spec: ProviderRuntimeSpec) -> dict[str, Any]:
    if not spec.required_module:
        return {
            "status": "NOT_REQUIRED",
            "module": None,
            "importable": True,
            "version": None,
            "symbol_present": True,
            "supported": True,
        }
    try:
        module = import_provider_sdk(spec.required_module)
    except Exception as exc:
        return {
            "status": "FAIL",
            "module": spec.required_module,
            "importable": False,
            "version": None,
            "symbol_present": False,
            "supported": False,
            "error_class": type(exc).__name__,
        }
    version = getattr(module, "__version__", None)
    symbol_present = spec.required_symbol is None or hasattr(module, spec.required_symbol)
    supported = symbol_present and sdk_version_supported(version, min_major=spec.min_major)
    return {
        "status": "PASS" if supported else "FAIL",
        "module": spec.required_module,
        "importable": True,
        "version": version,
        "symbol_present": symbol_present,
        "supported": supported,
        "required_symbol": spec.required_symbol,
        "min_major": spec.min_major,
        "uses_official_sdk": spec.uses_official_sdk,
    }


def credential_is_available(
    spec: ProviderRuntimeSpec,
    *,
    engine: Any | None = None,
) -> bool:
    injected = getattr(engine, "_api_key", None)
    if isinstance(injected, str) and injected.strip():
        return True
    if not spec.env_var:
        return True
    return bool(get_api_key(spec.env_var, config_fallback=spec.config_fallback))


def _probe_client(engine: Any) -> dict[str, Any]:
    if hasattr(engine, "client"):
        client = engine.client()
        return {
            "status": "PASS",
            "client_type": type(client).__name__,
            "remote_methods_invoked": False,
        }
    if hasattr(engine, "resolve_api_key"):
        engine.resolve_api_key()
    if hasattr(engine, "base_url"):
        engine.base_url()
    return {
        "status": "PASS",
        "client_type": type(engine).__name__,
        "remote_methods_blocked": True,
        "http_client": "not_invoked",
    }


def wrap_remote_openai_methods(client: Any) -> Any:
    """Replace remote SDK methods so accidental invocation fails locally."""

    def _block(name: str):
        def _raiser(*_args: Any, **_kwargs: Any) -> None:
            raise AssertionError(
                f"PROVIDER NETWORK FORBIDDEN: {name} must not be invoked "
                "during runtime preflight."
            )

        return _raiser

    chat = getattr(client, "chat", None)
    completions = getattr(chat, "completions", None) if chat is not None else None
    if completions is not None and hasattr(completions, "create"):
        setattr(completions, "create", _block("chat.completions.create"))
    responses = getattr(client, "responses", None)
    if responses is not None and hasattr(responses, "create"):
        setattr(responses, "create", _block("responses.create"))
    models = getattr(client, "models", None)
    if models is not None and hasattr(models, "list"):
        setattr(models, "list", _block("models.list"))
    completions_root = getattr(client, "completions", None)
    if completions_root is not None and hasattr(completions_root, "create"):
        setattr(completions_root, "create", _block("completions.create"))
    return client


def _openai_compatibility(
    engine: Any,
    *,
    model: str,
    request: AIRequest | None,
    output_mode: str | None,
) -> dict[str, Any]:
    """
    Local request/endpoint compatibility. Never opens a provider connection.
    Server-only fields remain UNKNOWN.
    """
    endpoint = production_openai_endpoint()
    contract = resolve_openai_token_contract(model, endpoint=endpoint)
    result: dict[str, Any] = {
        "endpoint": endpoint,
        "endpoint_selected": "PASS",
        "token_parameter": contract.parameter,
        "token_parameter_supported": (
            "PASS" if contract.confidence != CONFIDENCE_UNKNOWN else "UNKNOWN"
        ),
        "token_parameter_confidence": contract.confidence,
        "token_parameter_server_acceptance": contract.server_acceptance,
        "request_serializable": "SKIPPED",
        "unsupported_optional_parameters": "SKIPPED",
        "output_mode_server_acceptance": CONFIDENCE_UNKNOWN,
        "unknown_server_fields": [
            "json_object_server_acceptance",
            "max_completion_tokens_server_acceptance",
            "temperature_server_behavior",
            "reasoning_or_thinking_server_behavior",
        ],
        "payload_keys": [],
        "reasons": [],
    }
    if request is None:
        return result
    if not hasattr(engine, "build_payload"):
        result["request_serializable"] = "SKIPPED"
        return result
    try:
        payload = engine.build_payload(request, model)
    except (AIConfigurationError, AIProviderUnavailableError) as exc:
        result["request_serializable"] = "FAIL"
        result["unsupported_optional_parameters"] = "FAIL"
        result["reasons"].append(REASON_PROVIDER_REQUEST_INCOMPATIBLE)
        result["error_class"] = type(exc).__name__
        result["error"] = str(exc)
        return result
    except Exception as exc:
        result["request_serializable"] = "FAIL"
        result["reasons"].append(REASON_PROVIDER_RUNTIME_NOT_READY)
        result["error_class"] = type(exc).__name__
        return result

    result["payload_keys"] = sorted(payload)
    result["request_serializable"] = "PASS"
    result["unsupported_optional_parameters"] = "PASS"
    try:
        assert_no_conflicting_token_fields(payload)
    except AIConfigurationError as exc:
        result["token_parameter_supported"] = "FAIL"
        result["reasons"].append(REASON_PROVIDER_REQUEST_INCOMPATIBLE)
        result["error"] = str(exc)
        return result

    present = conflicting_token_fields(payload)
    if request.max_output_tokens is not None:
        if contract.parameter not in payload:
            result["token_parameter_supported"] = "FAIL"
            result["reasons"].append(REASON_PROVIDER_REQUEST_INCOMPATIBLE)
        if any(name != contract.parameter for name in present):
            result["token_parameter_supported"] = "FAIL"
            result["reasons"].append(REASON_PROVIDER_REQUEST_INCOMPATIBLE)
        if TOKEN_PARAM_MAX_TOKENS in payload and contract.parameter == TOKEN_PARAM_MAX_COMPLETION_TOKENS:
            result["token_parameter_supported"] = "FAIL"
            result["reasons"].append(REASON_PROVIDER_REQUEST_INCOMPATIBLE)

    if output_mode == "json_object":
        if payload.get("response_format") != {"type": "json_object"}:
            result["reasons"].append(REASON_PROVIDER_REQUEST_INCOMPATIBLE)
            result["output_mode_local"] = "FAIL"
        else:
            result["output_mode_local"] = "PASS"
            result["output_mode_server_acceptance"] = CONFIDENCE_UNKNOWN
    return result


def _check_output_mode(engine: Any, model: str, output_mode: str | None) -> str:
    if not output_mode:
        return "SKIPPED"
    request = AIRequest(
        prompt="provider runtime preflight output-mode probe",
        model=model,
        response_schema={"type": "object"},
    )
    if not hasattr(engine, "build_payload"):
        return "SKIPPED"
    payload = engine.build_payload(request, model)
    if output_mode == "json_object":
        if payload.get("response_format") == {"type": "json_object"}:
            return "PASS"
        return "FAIL"
    return "PASS"


def check_provider_runtime_readiness(
    provider: str,
    *,
    model: str | None = None,
    request: AIRequest | None = None,
    output_mode: str | None = None,
    engine: Any | None = None,
    construct_client: bool = True,
) -> ProviderReadiness:
    """
    Local readiness only. A missing SDK or key must surface here, before
    EXECUTION_ATTEMPT / lock consumption.
    """
    name = str(provider or "").strip().lower()
    spec = PROVIDER_SPECS.get(name)
    result = ProviderReadiness(ready=False, primary_reason=None, provider=name)
    secrets: list[str] = []

    registered = name in available_providers()
    result.provider_registered = registered
    if not registered:
        result.reasons.append(REASON_PROVIDER_NOT_REGISTERED)
        result.primary_reason = REASON_PROVIDER_RUNTIME_NOT_READY
        result.details = redact_secrets(
            {"registered_providers": available_providers()}, secrets
        )
        return result

    if spec is None:
        spec = ProviderRuntimeSpec(
            name=name,
            env_var=None,
            config_fallback=None,
            required_module=None,
            required_symbol=None,
            min_major=None,
            uses_official_sdk=False,
        )

    try:
        if engine is None:
            engine = get_ai_engine(name)
        result.provider_initialization = "PASS"
        result.details["engine_class"] = type(engine).__name__
    except Exception as exc:
        result.reasons.append(REASON_PROVIDER_RUNTIME_NOT_READY)
        result.primary_reason = REASON_PROVIDER_RUNTIME_NOT_READY
        result.provider_initialization = "FAIL"
        result.details = redact_secrets(
            {"init_error_class": type(exc).__name__}, secrets
        )
        return result

    sdk = inspect_sdk(spec)
    result.sdk_import = sdk["status"]
    result.sdk_version = sdk.get("version")
    if spec.required_module:
        result.sdk_supported = "PASS" if sdk.get("supported") else "FAIL"
    result.details["sdk"] = sdk
    if sdk["status"] == "FAIL":
        result.reasons.append(REASON_PROVIDER_RUNTIME_NOT_READY)
        result.primary_reason = REASON_PROVIDER_RUNTIME_NOT_READY
        result.details = redact_secrets(result.details, secrets)
        return result

    available = credential_is_available(spec, engine=engine)
    result.credential_available = "YES" if available else "NO"
    injected = getattr(engine, "_api_key", None)
    secrets.extend(collect_known_secrets(injected if isinstance(injected, str) else None))
    if spec.env_var:
        live = get_api_key(spec.env_var, config_fallback=spec.config_fallback)
        secrets.extend(collect_known_secrets(live))
    if not available:
        result.reasons.append(REASON_PROVIDER_CREDENTIAL_NOT_READY)
        result.primary_reason = REASON_PROVIDER_CREDENTIAL_NOT_READY
        result.details = redact_secrets(result.details, secrets)
        return result

    resolved_model = model or getattr(request, "model", None)
    try:
        if not resolved_model and hasattr(engine, "resolve_model"):
            resolved_model = engine.resolve_model()
        if not resolved_model:
            raise AIConfigurationError("model missing")
        result.model_resolution = "PASS"
        result.details["model"] = str(resolved_model)
    except Exception as exc:
        result.model_resolution = "FAIL"
        result.reasons.append(REASON_PROVIDER_RUNTIME_NOT_READY)
        result.primary_reason = REASON_PROVIDER_RUNTIME_NOT_READY
        result.details["model_error_class"] = type(exc).__name__
        result.details = redact_secrets(result.details, secrets)
        return result

    if request is not None:
        result.request_construction = "PASS" if str(request.prompt or "").strip() else "FAIL"
        if result.request_construction == "FAIL":
            result.reasons.append(REASON_PROVIDER_RUNTIME_NOT_READY)
            result.primary_reason = REASON_PROVIDER_RUNTIME_NOT_READY
            result.details = redact_secrets(result.details, secrets)
            return result

    required_mode = output_mode or spec.default_output_mode
    try:
        result.output_mode_supported = _check_output_mode(
            engine, str(resolved_model), required_mode
        )
    except Exception as exc:
        result.output_mode_supported = "FAIL"
        result.details["output_mode_error_class"] = type(exc).__name__
    if result.output_mode_supported == "FAIL":
        result.reasons.append(REASON_PROVIDER_RUNTIME_NOT_READY)
        result.primary_reason = REASON_PROVIDER_RUNTIME_NOT_READY
        result.details = redact_secrets(result.details, secrets)
        return result

    if name == "openai":
        compat = _openai_compatibility(
            engine,
            model=str(resolved_model),
            request=request,
            output_mode=required_mode,
        )
        result.endpoint_selected = compat.get("endpoint_selected") or "FAIL"
        result.token_parameter = compat.get("token_parameter")
        result.token_parameter_supported = str(
            compat.get("token_parameter_supported") or "SKIPPED"
        )
        result.request_serializable = str(
            compat.get("request_serializable") or "SKIPPED"
        )
        result.unsupported_optional_parameters = str(
            compat.get("unsupported_optional_parameters") or "SKIPPED"
        )
        result.details["endpoint"] = compat.get("endpoint") or PRODUCTION_OPENAI_ENDPOINT
        result.details["compatibility"] = compat
        if compat.get("reasons"):
            result.reasons.extend(str(item) for item in compat["reasons"])
            result.primary_reason = compat["reasons"][0]
            result.details = redact_secrets(result.details, secrets)
            return result
    else:
        result.endpoint_selected = "NOT_APPLICABLE"
        result.token_parameter_supported = "NOT_APPLICABLE"
        result.request_serializable = "SKIPPED" if request is None else "PASS"
        result.unsupported_optional_parameters = "NOT_APPLICABLE"

    if construct_client:
        try:
            probe = _probe_client(engine)
            result.client_construction = probe["status"]
            result.details["client"] = {
                "client_type": probe.get("client_type"),
                "remote_methods_blocked": probe.get("remote_methods_blocked"),
                "http_client": probe.get("http_client"),
            }
        except AIProviderUnavailableError:
            result.client_construction = "FAIL"
            result.reasons.append(REASON_PROVIDER_RUNTIME_NOT_READY)
            result.primary_reason = REASON_PROVIDER_RUNTIME_NOT_READY
            result.details = redact_secrets(result.details, secrets)
            return result
        except AIConfigurationError:
            result.client_construction = "FAIL"
            result.reasons.append(REASON_PROVIDER_CREDENTIAL_NOT_READY)
            result.primary_reason = REASON_PROVIDER_CREDENTIAL_NOT_READY
            result.details = redact_secrets(result.details, secrets)
            return result
        except Exception as exc:
            result.client_construction = "FAIL"
            result.reasons.append(REASON_PROVIDER_RUNTIME_NOT_READY)
            result.primary_reason = REASON_PROVIDER_RUNTIME_NOT_READY
            result.details["client_error_class"] = type(exc).__name__
            result.details = redact_secrets(result.details, secrets)
            return result
    else:
        result.client_construction = "SKIPPED"

    result.ready = True
    result.primary_reason = None
    unknown_fields = list(
        ((result.details.get("compatibility") or {}).get("unknown_server_fields")) or []
    )
    if name == "openai" and unknown_fields:
        result.readiness_class = READY_WITH_SERVER_UNVERIFIED_FIELDS
    else:
        result.readiness_class = READY
    result.details = redact_secrets(result.details, secrets)
    return result


def assert_provider_ready_for_authorization(
    readiness: ProviderReadiness,
) -> ProviderReadiness:
    """Fail-closed gate used before consuming a one-shot lock."""
    if readiness.ready:
        return readiness
    reason = readiness.primary_reason or REASON_PROVIDER_RUNTIME_NOT_READY
    raise ProviderNotReadyError(reason, readiness)


class ProviderNotReadyError(RuntimeError):
    def __init__(self, reason: str, readiness: ProviderReadiness) -> None:
        super().__init__(reason)
        self.reason = reason
        self.readiness = readiness


def future_call_accounting_contract() -> dict[str, Any]:
    return {
        "do_not_redefine_historical_4b24_metrics": True,
        "historical_4b24_attempt_2": {
            "recorded_actual_terra_calls": 1,
            "authorized_calls": 1,
            "execution_attempts": 1,
            "remote_invocations": 0,
            "http_requests": 0,
            "provider_responses": 0,
            "note": (
                "Historical ACTUAL TERRA CALLS = 1 because the one-shot "
                "lock and OneShotCallGuard were consumed. HTTP never left "
                "the machine. Future phases should count that as "
                "EXECUTION_ATTEMPT, not REMOTE_PROVIDER_INVOCATION."
            ),
        },
        "future_counters": {
            "authorized_calls": (
                "Human-authorized remote slots for the phase."
            ),
            "execution_attempts": (
                "Local generate/_invoke entries after preflight PASS."
            ),
            "remote_invocations": (
                "SDK create / HTTP execute crossed the provider boundary."
            ),
            "http_requests": "Actual HTTP requests observed.",
            "provider_responses": "Provider HTTP responses received.",
        },
        "preflight_before_execution_authorization": True,
        "missing_sdk_must_not_consume_lock": True,
    }


__all__ = [
    "PROVIDER_SPECS",
    "ProviderCallAccounting",
    "ProviderNotReadyError",
    "ProviderReadiness",
    "ProviderRuntimeSpec",
    "NOT_READY",
    "READY",
    "READY_WITH_SERVER_UNVERIFIED_FIELDS",
    "REASON_PROVIDER_CREDENTIAL_NOT_READY",
    "REASON_PROVIDER_NOT_REGISTERED",
    "REASON_PROVIDER_REQUEST_INCOMPATIBLE",
    "REASON_PROVIDER_RUNTIME_NOT_READY",
    "REMOTE_OPENAI_METHODS",
    "assert_provider_ready_for_authorization",
    "check_provider_runtime_readiness",
    "collect_known_secrets",
    "credential_is_available",
    "future_call_accounting_contract",
    "get_engine_class",
    "import_provider_sdk",
    "inspect_sdk",
    "parse_version",
    "redact_secrets",
    "sdk_version_supported",
    "wrap_remote_openai_methods",
]
