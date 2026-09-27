"""
Préflight du Source Analyzer — tout ce qui précède engine.generate().

Reproduit le chemin d'analyse jusqu'à la construction d'un AIRequest,
puis S'ARRÊTE. Aucun appel réseau, aucun engine.generate().

Utilisé pour valider qu'un transcript DERIVED (ou SOURCE) peut être chargé,
planifié et signé avant un éventuel appel réel (phase suivante).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.ai.capabilities import resolve_capabilities
from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.ai.settings import StageSettings, resolve_stage_settings
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis import cache as cache_module
from app.source_analysis import prompt as prompt_module
from app.source_analysis.context_strategy import ContextPlan, plan_context
from app.source_analysis.errors import SourceAnalysisContextExceeded
from app.source_analysis.models import SOURCE_MAP_SCHEMA_VERSION, STRATEGY_GLOBAL
from app.source_analysis.ultra_compact_schema import (
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.transcript_input import (
    TranscriptInput,
    TranscriptInputMode,
    coerce_transcript_mode,
    load_transcript_input,
)
from app.source_analysis.writer import transcripts_dir

PREFLIGHT_SCHEMA_VERSION = "1.0"
PREFLIGHT_ARTIFACT_NAME = "source_analyzer_clean_preflight.json"
STAGE = "source_analysis"


@dataclass
class GenerateGuard:
    """
    Sentinelle : tout appel à generate() est une violation du préflight.

    `calls` reste à 0 si le préflight respecte son contrat. provider/modèle
    sont lisibles pour construire le plan, sans jamais ouvrir de connexion.
    """

    calls: int = 0
    provider_name: str = "anthropic"
    model_name: str = "claude-sonnet-5"

    def resolve_model(self) -> str:
        return self.model_name

    def capabilities(self, model: str):
        return resolve_capabilities(self.provider_name, model)

    def generate(self, request) -> None:
        self.calls += 1
        raise AssertionError(
            "Préflight Source Analyzer : engine.generate() est interdit."
        )


@dataclass(frozen=True)
class SourceAnalyzerPreflight:
    """Diagnostic déterministe — aucun horodatage, aucun UUID."""

    transcript: TranscriptInput
    plan: ContextPlan
    signature: str
    request: AIRequest
    system_tokens: int
    user_tokens: int
    total_tokens: int
    estimation_method: str
    provider_schema: dict
    schema_audit: dict
    generate_calls: int
    provenance: dict | None = None
    original_sha256: str | None = None

    @property
    def remaining_margin(self) -> int:
        return int(self.plan.usable_input_context) - int(self.total_tokens)

    def to_artifact(self) -> dict:
        transcript = self.transcript
        return {
            "schema_version": PREFLIGHT_SCHEMA_VERSION,
            "input": {
                "mode": transcript.mode.value,
                "transcript_path": _portable(transcript.path),
                "transcript_sha256": sha256_of_file(transcript.path),
                "provenance_path": (
                    _portable(transcript.provenance_path)
                    if transcript.provenance_path is not None
                    else None
                ),
                "original_transcript_sha256": self.original_sha256,
            },
            "provenance_validation": self.provenance,
            "source_analysis": {
                "provider": self.plan.provider,
                "model": self.plan.model,
                "prompt_version": prompt_module.SOURCE_ANALYZER_PROMPT_VERSION,
                "schema_version": SOURCE_MAP_SCHEMA_VERSION,
                "estimated_tokens": {
                    "system": self.system_tokens,
                    "user": self.user_tokens,
                    "total": self.total_tokens,
                    "method": self.estimation_method,
                    "estimated": True,
                },
                "usable_input_budget": self.plan.usable_input_context,
                "context_strategy": self.plan.strategy,
                "remaining_margin": self.remaining_margin,
                "signature": self.signature,
                "would_call_ai": False,
                "structured_output": {
                    "response_schema": True,
                    "anthropic_native": True,
                    "prepare_anthropic_json_schema": True,
                },
            },
            "anthropic_schema_audit": {
                key: list(value) for key, value in self.schema_audit.items()
            },
            "network_calls": 0,
            "engine_generate_calls": self.generate_calls,
        }


def run_source_analyzer_preflight(
    transcript_path: Path,
    *,
    project_name: str | None = None,
    mode: TranscriptInputMode | str = TranscriptInputMode.SOURCE,
    provenance_path: Path | None = None,
    original_transcript_path: Path | None = None,
    settings: StageSettings | None = None,
    engine=None,
    write_artifact_to: Path | None = None,
) -> SourceAnalyzerPreflight:
    """
    Charge, valide, planifie, signe — puis STOP.

    `engine`, s'il est fourni, n'est utilisé que pour lire provider/modèle/
    capacités. `engine.generate()` n'est jamais appelé. Sans moteur, le
    routage vient de resolve_stage_settings(source_analysis).
    """
    resolved_mode = coerce_transcript_mode(mode)
    guard = GenerateGuard()

    transcript = load_transcript_input(
        Path(transcript_path),
        project_name=project_name,
        mode=resolved_mode,
        provenance_path=provenance_path,
        original_transcript_path=original_transcript_path,
    )

    provenance_block = None
    original_sha = None

    if resolved_mode is TranscriptInputMode.DERIVED:
        from app.source_analysis.provenance import validate_derived_provenance

        proven = validate_derived_provenance(
            derived_path=Path(transcript_path),
            provenance_path=Path(provenance_path),
            original_transcript_path=(
                Path(original_transcript_path)
                if original_transcript_path is not None
                else transcript.original_transcript_path
            ),
        )
        provenance_block = proven.to_dict()
        original_sha = proven.original_sha256

    system_prompt = prompt_module.build_system_prompt(transcript.primary_language)
    user_prompt = prompt_module.build_user_prompt(transcript)
    response_schema = build_ultra_compact_response_schema()

    resolved_settings = settings or resolve_stage_settings(STAGE)

    if engine is not None:
        provider = engine.provider_name
        model = engine.resolve_model()
        capabilities = engine.capabilities(model)
    else:
        provider = resolved_settings.provider
        model = resolved_settings.model or ""
        capabilities = resolve_capabilities(provider, model)

    system_estimate = estimate_tokens(system_prompt, model=model)
    user_estimate = estimate_tokens(user_prompt, model=model)

    plan = plan_context(
        transcript,
        capabilities,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        safety_ratio=resolved_settings.context_safety_ratio,
    )

    signature = cache_module.build_signature(
        cache_module.SignatureInputs(
            transcript_sha256=transcript.content_sha256,
            transcript_id=transcript.transcript_id,
            prompt_version=prompt_module.SOURCE_ANALYZER_PROMPT_VERSION,
            prompt_sha256=cache_module.prompt_fingerprint(system_prompt, user_prompt),
            schema_version=SOURCE_MAP_SCHEMA_VERSION,
            response_schema_sha256=ultra_compact_schema_fingerprint(response_schema),
            provider=provider,
            model=model,
            temperature=resolved_settings.temperature,
            max_output_tokens=resolved_settings.max_output_tokens,
            context_safety_ratio=float(resolved_settings.context_safety_ratio),
            output_language=transcript.primary_language,
        )
    )

    request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=resolved_settings.temperature,
        max_output_tokens=resolved_settings.max_output_tokens,
        response_schema=response_schema,
        metadata={"stage": STAGE, "project": transcript.project_name, "preflight": True},
    )

    provider_schema = prepare_anthropic_json_schema(response_schema)
    schema_audit = audit_unsupported_features(provider_schema)

    result = SourceAnalyzerPreflight(
        transcript=transcript,
        plan=plan,
        signature=signature,
        request=request,
        system_tokens=system_estimate.tokens,
        user_tokens=user_estimate.tokens,
        total_tokens=plan.estimated_input_tokens,
        estimation_method=plan.estimation_method,
        provider_schema=provider_schema,
        schema_audit=schema_audit,
        generate_calls=guard.calls,
        provenance=provenance_block,
        original_sha256=original_sha,
    )

    if plan.strategy != STRATEGY_GLOBAL:
        raise SourceAnalysisContextExceeded(
            "Préflight : le transcript ne tient pas dans une analyse globale. "
            f"{plan.budget_summary()}. La consolidation multi-fenêtres n'est "
            "pas implémentée dans cette phase.",
            plan=plan,
        )

    if write_artifact_to is not None:
        write_preflight_artifact(Path(write_artifact_to), result.to_artifact())

    return result


def run_project_derived_preflight(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write: bool = True,
) -> SourceAnalyzerPreflight:
    """
    Préflight DERIVED d'un projet : transcripts/clean + cleanup_application.

    Chemins canoniques, Pathlib uniquement. Aucun nom de projet réel n'est
    codé ici.
    """
    from app.cleanup_application.writer import audit_path, clean_json_path
    from app.language_cleanup.transcript_source import audit_dir

    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    provenance_path = audit_path(project_name, sortie_dir=sortie_dir)
    original_path = transcripts_dir(project_name, sortie_dir=sortie_dir) / "transcript_data.json"
    artifact_path = audit_dir(project_name, sortie_dir=sortie_dir) / PREFLIGHT_ARTIFACT_NAME

    return run_source_analyzer_preflight(
        clean_path,
        project_name=project_name,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
        write_artifact_to=artifact_path if write else None,
    )


def write_preflight_artifact(path: Path, payload: dict) -> Path:
    """
    Écriture atomique déterministe :

        .partial  →  valider  →  replace

    Pas de generated_at, pas d'UUID. write_bytes pour éviter la traduction
    Windows \\n → \\r\\n, afin que deux runs soient byte-identiques.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")

    try:
        partial.write_bytes(encoded)
        on_disk = partial.read_bytes()
        if on_disk != encoded:
            raise ValueError(
                f"Octets partiels ≠ contenu canonique pour {path.name}."
            )
        loaded = json.loads(on_disk.decode("utf-8"))
        if not isinstance(loaded, dict) or loaded.get("schema_version") != PREFLIGHT_SCHEMA_VERSION:
            raise ValueError(f"Préflight partiel invalide : {path.name}.")
        if loaded.get("network_calls") != 0 or loaded.get("engine_generate_calls") != 0:
            raise ValueError("Préflight partiel : un compteur réseau/IA n'est pas à 0.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()

    return path


def _portable(path: Path) -> str:
    """Chemin en POSIX pour un artefact déterministe, indépendant de l'OS."""
    return Path(path).as_posix()
