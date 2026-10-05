"""
Couche IA commune — un seul contrat pour tous les fournisseurs.

Les étapes éditoriales à venir (Source Analyzer, Editorial Planner, Book
Generator, Book Validator, Visual Director) n'importent RIEN d'autre que ce
paquet. Aucune d'elles ne connaît openai, anthropic, requests ni une URL
d'API : elles construisent une AIRequest, appellent generate(), et lisent
une AIResponse.

    appelant (étape éditoriale)
        ↓  AIRequest
    registry.get_ai_engine(provider)
        ↓
    BaseAIEngine.generate()        latence, rejeu, sortie structurée, logs
        ↓
    provider                       OpenAI / Anthropic / Ollama / LM Studio / Fake
        ↓  AIResponse
    texte · parsed · usage tokens réels · modèle · latence
        ↓
    CostTracker                    coût par appel, étape, fournisseur, modèle
        ↓
    project_state.json → report.json["ai_usage"]

Le chemin V1 (`send_prompt`) reste disponible sur tous les moteurs et
retourne toujours une chaîne : voir app/ai_engine.py.
"""

from app.ai.capabilities import (
    ModelCapabilities,
    default_safety_ratio,
    resolve_capabilities,
    validate_safety_ratio,
)
from app.ai.contracts import (
    AIRequest,
    AIResponse,
    USAGE_FROM_PROVIDER,
    USAGE_UNAVAILABLE,
)
from app.ai.cost import (
    AICallRecord,
    CostTracker,
    KNOWN_STAGES,
    aggregate_records,
    cost_per_1000_words,
    empty_usage_block,
    format_call_id,
)
from app.ai.errors import (
    AIAuthenticationError,
    AIConfigurationError,
    AIConnectionError,
    AIError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AIRequestError,
    AIResponseError,
    AIServerError,
    AIStructuredOutputError,
    AITimeoutError,
    AITransientError,
    is_retryable,
)
from app.ai.estimation import (
    TokenEstimate,
    estimate_request_tokens,
    estimate_tokens,
    fits_in_context,
)
from app.ai.pricing import (
    COST_STATUS_BASE_ESTIMATE,
    COST_STATUS_KNOWN,
    COST_STATUS_LOCAL,
    COST_STATUS_UNKNOWN,
    REGIME_LONG_CONTEXT,
    CostBreakdown,
    ModelPricing,
    PricingCatalog,
    build_default_catalog,
)
from app.ai.provider_preflight import (
    ProviderCallAccounting,
    ProviderNotReadyError,
    ProviderReadiness,
    assert_provider_ready_for_authorization,
    check_provider_runtime_readiness,
)
from app.ai.providers import (
    AnthropicEngine,
    BaseAIEngine,
    FakeAIEngine,
    FakeReply,
    LMStudioEngine,
    OllamaEngine,
    OpenAIEngine,
    ProviderResult,
)
from app.ai.registry import (
    available_providers,
    get_ai_engine,
    get_ai_provider,
    get_engine_for_stage,
    register_ai_engine,
    unregister_ai_engine,
)
from app.ai.retry import RetryPolicy, RetryTrace, default_retry_policy, no_delay_policy
from app.ai.settings import StageSettings, resolve_stage_settings
from app.ai.timeouts import (
    AITimeoutConfig,
    diagnose_stage_timeout,
    resolve_ai_timeouts,
)
from app.ai.structured import parse_structured_output

__all__ = [
    # Contrats
    "AIRequest",
    "AIResponse",
    "USAGE_FROM_PROVIDER",
    "USAGE_UNAVAILABLE",
    # Moteurs
    "BaseAIEngine",
    "ProviderResult",
    "AnthropicEngine",
    "FakeAIEngine",
    "FakeReply",
    "LMStudioEngine",
    "OllamaEngine",
    "OpenAIEngine",
    # Registre
    "available_providers",
    "get_ai_engine",
    "get_ai_provider",
    "get_engine_for_stage",
    "register_ai_engine",
    "unregister_ai_engine",
    "ProviderCallAccounting",
    "ProviderNotReadyError",
    "ProviderReadiness",
    "assert_provider_ready_for_authorization",
    "check_provider_runtime_readiness",
    # Capacités et budget de contexte
    "ModelCapabilities",
    "resolve_capabilities",
    "default_safety_ratio",
    "validate_safety_ratio",
    # Estimation (jamais confondue avec l'usage réel)
    "TokenEstimate",
    "estimate_tokens",
    "estimate_request_tokens",
    "fits_in_context",
    # Sortie structurée
    "parse_structured_output",
    # Rejeu
    "RetryPolicy",
    "RetryTrace",
    "default_retry_policy",
    "no_delay_policy",
    # Coût
    "AICallRecord",
    "CostTracker",
    "CostBreakdown",
    "ModelPricing",
    "PricingCatalog",
    "build_default_catalog",
    "aggregate_records",
    "empty_usage_block",
    "cost_per_1000_words",
    "format_call_id",
    "KNOWN_STAGES",
    "COST_STATUS_BASE_ESTIMATE",
    "COST_STATUS_KNOWN",
    "COST_STATUS_LOCAL",
    "COST_STATUS_UNKNOWN",
    "REGIME_LONG_CONTEXT",
    # Configuration par étape
    "StageSettings",
    "resolve_stage_settings",
    # Timeouts connect/read
    "AITimeoutConfig",
    "diagnose_stage_timeout",
    "resolve_ai_timeouts",
    # Erreurs
    "AIError",
    "AIConfigurationError",
    "AIAuthenticationError",
    "AIProviderUnavailableError",
    "AIRequestError",
    "AIResponseError",
    "AIStructuredOutputError",
    "AITransientError",
    "AITimeoutError",
    "AIConnectionError",
    "AIRateLimitError",
    "AIServerError",
    "is_retryable",
]
