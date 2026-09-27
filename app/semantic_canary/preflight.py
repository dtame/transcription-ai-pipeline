"""
Préflight Anthropic — AVANT RÉSEAU (§29).

Toutes les conditions de ce module sont vérifiées SANS ouvrir de connexion :
`resolve_api_key()` lit l'environnement/.env, `capabilities()` lit la
configuration, `prepare_anthropic_json_schema()` + `audit_unsupported_features()`
sont des transformations et un audit purement locaux (voir
app/ai/providers/_anthropic_schema.py). Si une seule condition échoue,
`run_preflight()` lève PreflightError : STOP AVANT RÉSEAU.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.errors import AIConfigurationError
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.semantic_canary.errors import PreflightError

EXPECTED_PROVIDER = "anthropic"
EXPECTED_MODEL = "claude-sonnet-5"


@dataclass(frozen=True)
class PreflightReport:
    """Résultat complet du préflight — publié tel quel dans le rapport (§29)."""

    provider: str
    model: str
    expected_provider: str
    expected_model: str
    credential_available: bool
    capability_structured_output: bool
    response_schema_present: bool
    provider_schema: dict = field(default_factory=dict)
    audit_findings: dict = field(default_factory=dict)

    @property
    def audit_clean(self) -> bool:
        return all(occurrences == [] for occurrences in self.audit_findings.values())

    @property
    def passed(self) -> bool:
        return (
            self.provider == self.expected_provider
            and self.model == self.expected_model
            and self.credential_available
            and self.capability_structured_output
            and self.response_schema_present
            and self.audit_clean
        )

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "expected_provider": self.expected_provider,
            "expected_model": self.expected_model,
            "credential_available": self.credential_available,
            "capability_structured_output": self.capability_structured_output,
            "response_schema_present": self.response_schema_present,
            "audit_findings": {
                key: list(value) for key, value in self.audit_findings.items()
            },
            "audit_clean": self.audit_clean,
            "passed": self.passed,
        }


def run_preflight(
    engine,
    model: str,
    response_schema: dict,
    *,
    expected_provider: str = EXPECTED_PROVIDER,
    expected_model: str = EXPECTED_MODEL,
) -> PreflightReport:
    """
    Exécute le préflight complet (§29) et lève PreflightError s'il échoue.

    `engine` est le moteur déjà construit. Aucune requête HTTP n'est émise
    ici. `expected_provider`/`expected_model` défaut au couple réel exigé
    par le canary (anthropic / claude-sonnet-5) ; les tests peuvent les
    surcharger pour exercer ce même préflight avec FakeAIEngine.
    """
    provider = engine.provider_name

    if not response_schema:
        raise PreflightError(
            "Préflight échoué : aucun response_schema fourni au canary."
        )

    resolve_api_key = getattr(engine, "resolve_api_key", None)

    if resolve_api_key is None:
        # Provider sans notion de clé API (local, ou moteur simulé de test) :
        # rien à vérifier, la condition est satisfaite par construction.
        credential_available = True
    else:
        try:
            resolve_api_key()
            credential_available = True
        except AIConfigurationError:
            credential_available = False

    capabilities = engine.capabilities(model)
    provider_schema = prepare_anthropic_json_schema(response_schema)
    findings = audit_unsupported_features(provider_schema)

    report = PreflightReport(
        provider=provider,
        model=model,
        expected_provider=expected_provider,
        expected_model=expected_model,
        credential_available=credential_available,
        capability_structured_output=bool(capabilities.supports_structured_output),
        response_schema_present=True,
        provider_schema=provider_schema,
        audit_findings=findings,
    )

    if not report.passed:
        raise PreflightError(
            "Préflight Anthropic échoué (§29) : " + str(report.to_dict())
        )

    return report
