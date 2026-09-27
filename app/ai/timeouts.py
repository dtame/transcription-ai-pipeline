"""
Timeouts IA : connect et read distincts, résolution par étape.

requests n'offre pas de timeout total wall-clock sur le chemin HTTP actuel.
Un scalaire `timeout=3600` valait connect=3600 ET read=3600 — c'est la cause
locale du 3B Final (voir Phase 3B.5). Ce module sépare les deux horloges.

Précédence réelle (read) :

    1. AIRequest.timeout_seconds          source = request
    2. engine timeout_seconds             source = engine
    3. env AI_<STAGE>_READ_TIMEOUT_SECONDS
                                          source = stage_env
    4. StageSettings.read_timeout_seconds source = stage
    5. provider config_timeout()          source = provider
       (seulement si le provider surcharge le défaut global,
        ex. OLLAMA_TIMEOUT_SECONDS)
    6. env AI_DEFAULT_READ_TIMEOUT_SECONDS
                                          source = env
    7. AI_DEFAULT_TIMEOUT_SECONDS         source = default

Précédence réelle (connect) — le scalaire request/engine NE s'applique PAS
au connect, pour qu'un read long ne rallonge pas l'établissement TCP/TLS :

    1. engine connect_timeout_seconds     source = engine
    2. env AI_<STAGE>_CONNECT_TIMEOUT_SECONDS
                                          source = stage_env
    3. StageSettings.connect_timeout_seconds
                                          source = stage
    4. env AI_DEFAULT_CONNECT_TIMEOUT_SECONDS
                                          source = env
    5. AI_DEFAULT_CONNECT_TIMEOUT_SECONDS source = default

Aucune valeur invalide n'est silencieusement remplacée.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any, Mapping

import app.config as config

from app.ai.errors import AIConfigurationError

TIMEOUT_KIND_CONNECT = "connect"
TIMEOUT_KIND_READ = "read"
TIMEOUT_KIND_UNKNOWN = "unknown"
TIMEOUT_KINDS = (TIMEOUT_KIND_CONNECT, TIMEOUT_KIND_READ, TIMEOUT_KIND_UNKNOWN)

SOURCE_REQUEST = "request"
SOURCE_ENGINE = "engine"
SOURCE_STAGE_ENV = "stage_env"
SOURCE_STAGE = "stage"
SOURCE_ENV = "env"
SOURCE_PROVIDER = "provider"
SOURCE_DEFAULT = "default"

ENV_DEFAULT_CONNECT = "AI_DEFAULT_CONNECT_TIMEOUT_SECONDS"
ENV_DEFAULT_READ = "AI_DEFAULT_READ_TIMEOUT_SECONDS"

EDITORIAL_TIMEOUT_STAGES = (
    "source_analysis",
    "editorial_planning",
    "book_generation",
    "book_validation",
)

# Établissement TCP/TLS uniquement — pas une durée de génération.
# Aucune convention connect existait dans le projet ; 30 s est un budget
# opérationnel de connexion, pas un plafond de génération.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class AITimeoutConfig:
    """
    Timeouts HTTP réellement contrôlés par l'application.

    `connect_seconds` et `read_seconds` sont distincts. Il n'existe pas de
    timeout total wall-clock sur le chemin requests actuel.
    """

    connect_seconds: float
    read_seconds: float
    connect_source: str = SOURCE_DEFAULT
    read_source: str = SOURCE_DEFAULT

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "connect_seconds",
            validate_timeout_seconds(self.connect_seconds, name="connect_seconds"),
        )
        object.__setattr__(
            self,
            "read_seconds",
            validate_timeout_seconds(self.read_seconds, name="read_seconds"),
        )

    def as_requests_timeout(self) -> tuple[float, float]:
        """Forme attendue par requests.post : (connect, read)."""
        return (self.connect_seconds, self.read_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "connect_seconds": self.connect_seconds,
            "connect_source": self.connect_source,
            "read_seconds": self.read_seconds,
            "read_source": self.read_source,
            "requests_timeout_shape": "tuple",
        }


def validate_timeout_seconds(value: Any, *, name: str) -> float:
    """
    Valide une durée de timeout.

    Refuse None, bool, chaînes, 0, négatif, NaN, inf. Accepte int et float > 0.
    """
    if value is None:
        raise AIConfigurationError(f"{name} est obligatoire et ne peut pas être None.")

    if type(value) is bool:
        raise AIConfigurationError(f"{name} ne peut pas être un booléen : {value!r}.")

    if isinstance(value, str):
        raise AIConfigurationError(f"{name} doit être un nombre, pas une chaîne : {value!r}.")

    if isinstance(value, (int, float)):
        number = float(value)
    else:
        raise AIConfigurationError(
            f"{name} doit être un nombre > 0, reçu {type(value).__name__} : {value!r}."
        )

    if math.isnan(number) or math.isinf(number) or number <= 0:
        raise AIConfigurationError(
            f"{name} doit être un nombre fini > 0 : {value!r}."
        )

    return number


def parse_timeout_seconds(value: Any, *, name: str) -> float:
    """
    Parse une valeur de configuration (env, dict d'étape).

    Une chaîne numérique honnête (« 30 », « 30.0 ») est acceptée.
    Une chaîne vide, un booléen, NaN, inf, 0 ou une valeur négative échouent.
    """
    if value is None:
        raise AIConfigurationError(f"{name} est obligatoire et ne peut pas être None.")

    if type(value) is bool:
        raise AIConfigurationError(f"{name} ne peut pas être un booléen : {value!r}.")

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise AIConfigurationError(f"{name} est vide.")
        value = stripped

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AIConfigurationError(
            f"{name} doit être un nombre fini > 0 : {value!r}."
        ) from exc

    if math.isnan(number) or math.isinf(number) or number <= 0:
        raise AIConfigurationError(
            f"{name} doit être un nombre fini > 0 : {value!r}."
        )

    return number


def optional_parsed_timeout(value: Any, *, name: str) -> float | None:
    """None ou chaîne vide → None. Toute autre valeur est validée."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return parse_timeout_seconds(value, name=name)


def default_connect_timeout_seconds(*, environ: Mapping[str, str] | None = None) -> float:
    """Connect timeout global : env, sinon constante de configuration, sinon 30 s."""
    env = _environ(environ)
    parsed = optional_parsed_timeout(
        env.get(ENV_DEFAULT_CONNECT),
        name=ENV_DEFAULT_CONNECT,
    )
    if parsed is not None:
        return parsed
    return validate_timeout_seconds(
        getattr(config, "AI_DEFAULT_CONNECT_TIMEOUT_SECONDS", DEFAULT_CONNECT_TIMEOUT_SECONDS),
        name="AI_DEFAULT_CONNECT_TIMEOUT_SECONDS",
    )


def default_read_timeout_seconds(*, environ: Mapping[str, str] | None = None) -> float:
    """Read timeout global : env dédiée, sinon AI_DEFAULT_TIMEOUT_SECONDS (300)."""
    env = _environ(environ)
    parsed = optional_parsed_timeout(
        env.get(ENV_DEFAULT_READ),
        name=ENV_DEFAULT_READ,
    )
    if parsed is not None:
        return parsed
    return validate_timeout_seconds(
        getattr(config, "AI_DEFAULT_TIMEOUT_SECONDS", 300),
        name="AI_DEFAULT_TIMEOUT_SECONDS",
    )


def stage_timeout_env_name(stage: str, kind: str) -> str:
    """AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS, etc."""
    token = str(stage).strip().upper()
    kind_token = str(kind).strip().upper()
    return f"AI_{token}_{kind_token}_TIMEOUT_SECONDS"


def _environ(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def _stage_env_timeout(
    stage: str | None,
    kind: str,
    *,
    environ: Mapping[str, str] | None,
) -> float | None:
    if not stage:
        return None
    name = stage_timeout_env_name(stage, kind)
    return optional_parsed_timeout(_environ(environ).get(name), name=name)


def resolve_ai_timeouts(
    *,
    stage: str | None = None,
    request_timeout_seconds: float | None = None,
    engine_read_timeout_seconds: float | None = None,
    engine_connect_timeout_seconds: float | None = None,
    stage_read_timeout_seconds: float | None = None,
    stage_connect_timeout_seconds: float | None = None,
    provider_read_timeout_seconds: float | None = None,
    environ: Mapping[str, str] | None = None,
) -> AITimeoutConfig:
    """
    Résout connect et read sans appeler de fournisseur.

    `request_timeout_seconds` et `engine_read_timeout_seconds` ne portent
    que le read : un override long ne devient jamais un connect long.
    """
    if stage_read_timeout_seconds is None and stage_connect_timeout_seconds is None and stage:
        from app.ai.settings import resolve_stage_settings

        settings = resolve_stage_settings(stage)
        stage_read_timeout_seconds = settings.read_timeout_seconds
        stage_connect_timeout_seconds = settings.connect_timeout_seconds

    read_seconds, read_source = _resolve_read(
        request_timeout_seconds=request_timeout_seconds,
        engine_read_timeout_seconds=engine_read_timeout_seconds,
        stage=stage,
        stage_read_timeout_seconds=stage_read_timeout_seconds,
        provider_read_timeout_seconds=provider_read_timeout_seconds,
        environ=environ,
    )
    connect_seconds, connect_source = _resolve_connect(
        engine_connect_timeout_seconds=engine_connect_timeout_seconds,
        stage=stage,
        stage_connect_timeout_seconds=stage_connect_timeout_seconds,
        environ=environ,
    )
    return AITimeoutConfig(
        connect_seconds=connect_seconds,
        read_seconds=read_seconds,
        connect_source=connect_source,
        read_source=read_source,
    )


def _resolve_read(
    *,
    request_timeout_seconds: float | None,
    engine_read_timeout_seconds: float | None,
    stage: str | None,
    stage_read_timeout_seconds: float | None,
    provider_read_timeout_seconds: float | None,
    environ: Mapping[str, str] | None,
) -> tuple[float, str]:
    if request_timeout_seconds is not None:
        return validate_timeout_seconds(
            request_timeout_seconds, name="AIRequest.timeout_seconds"
        ), SOURCE_REQUEST

    if engine_read_timeout_seconds is not None:
        return validate_timeout_seconds(
            engine_read_timeout_seconds, name="engine.timeout_seconds"
        ), SOURCE_ENGINE

    stage_env = _stage_env_timeout(stage, "READ", environ=environ)
    if stage_env is not None:
        return stage_env, SOURCE_STAGE_ENV

    if stage_read_timeout_seconds is not None:
        return validate_timeout_seconds(
            stage_read_timeout_seconds, name="StageSettings.read_timeout_seconds"
        ), SOURCE_STAGE

    if provider_read_timeout_seconds is not None:
        return validate_timeout_seconds(
            provider_read_timeout_seconds, name="provider.read_timeout_seconds"
        ), SOURCE_PROVIDER

    env_default = optional_parsed_timeout(
        _environ(environ).get(ENV_DEFAULT_READ),
        name=ENV_DEFAULT_READ,
    )
    if env_default is not None:
        return env_default, SOURCE_ENV

    return default_read_timeout_seconds(environ={}), SOURCE_DEFAULT


def _resolve_connect(
    *,
    engine_connect_timeout_seconds: float | None,
    stage: str | None,
    stage_connect_timeout_seconds: float | None,
    environ: Mapping[str, str] | None,
) -> tuple[float, str]:
    if engine_connect_timeout_seconds is not None:
        return validate_timeout_seconds(
            engine_connect_timeout_seconds, name="engine.connect_timeout_seconds"
        ), SOURCE_ENGINE

    stage_env = _stage_env_timeout(stage, "CONNECT", environ=environ)
    if stage_env is not None:
        return stage_env, SOURCE_STAGE_ENV

    if stage_connect_timeout_seconds is not None:
        return validate_timeout_seconds(
            stage_connect_timeout_seconds,
            name="StageSettings.connect_timeout_seconds",
        ), SOURCE_STAGE

    env_default = optional_parsed_timeout(
        _environ(environ).get(ENV_DEFAULT_CONNECT),
        name=ENV_DEFAULT_CONNECT,
    )
    if env_default is not None:
        return env_default, SOURCE_ENV

    return default_connect_timeout_seconds(environ={}), SOURCE_DEFAULT


def requests_timeout_argument(
    timeout: float | tuple[float, float] | AITimeoutConfig,
) -> tuple[float, float]:
    """
    Normalise l'argument timeout de requests.

    Un scalaire historique est interprété comme READ seulement : le connect
    reste le défaut court. C'est volontaire — ne pas recréer le bug 3B Final.
    """
    if isinstance(timeout, AITimeoutConfig):
        return timeout.as_requests_timeout()

    if isinstance(timeout, tuple) and len(timeout) == 2:
        return (
            validate_timeout_seconds(timeout[0], name="connect_timeout"),
            validate_timeout_seconds(timeout[1], name="read_timeout"),
        )

    return (
        default_connect_timeout_seconds(),
        validate_timeout_seconds(timeout, name="timeout"),
    )


def classify_requests_timeout(exc: BaseException) -> str:
    """
    Classe un timeout requests sans inventer.

    ConnectTimeout → connect, ReadTimeout → read, Timeout générique → unknown.
    """
    import requests

    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return TIMEOUT_KIND_CONNECT
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return TIMEOUT_KIND_READ
    if isinstance(exc, requests.exceptions.Timeout):
        return TIMEOUT_KIND_UNKNOWN
    return TIMEOUT_KIND_UNKNOWN


def diagnose_stage_timeout(
    stage: str,
    *,
    provider_read_timeout_seconds: float | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Préflight offline : timeouts effectifs d'une étape, sans réseau."""
    from app.ai.settings import resolve_stage_settings

    settings = resolve_stage_settings(stage)
    resolved = resolve_ai_timeouts(
        stage=stage,
        stage_read_timeout_seconds=settings.read_timeout_seconds,
        stage_connect_timeout_seconds=settings.connect_timeout_seconds,
        provider_read_timeout_seconds=provider_read_timeout_seconds,
        environ=environ,
    )
    return {
        "stage": settings.stage,
        "provider": settings.provider,
        "model": settings.model,
        "connect_seconds": resolved.connect_seconds,
        "connect_source": resolved.connect_source,
        "read_seconds": resolved.read_seconds,
        "read_source": resolved.read_source,
        "long_read_override_supported": True,
    }
