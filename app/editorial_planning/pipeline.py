"""Assemblage offline transport → plan validé. Aucun appel provider."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.editorial_planning.constants import (
    EDITORIAL_PLAN_SCHEMA_VERSION,
    EDITORIAL_PLAN_TRANSPORT_VERSION,
    EDITORIAL_PLAN_VALIDATOR_VERSION,
    EDITORIAL_PLANNER_PROMPT_VERSION,
    IDEA_COVERAGE_POLICY_VERSION,
    STRATEGY_GLOBAL,
)
from app.editorial_planning.errors import EditorialPlanValidationError
from app.editorial_planning.models import EditorialPlan, EditorialPlanMetadata
from app.editorial_planning.preflight import load_source_map_file
from app.editorial_planning.reconstruct import reconstruct_editorial_plan
from app.editorial_planning.settings import PlannerSettings, frozen_production_settings
from app.editorial_planning.signature import (
    PlannerSignatureInputs,
    build_planner_signature,
    default_signature_inputs,
)
from app.editorial_planning.validator import (
    EditorialPlanValidation,
    validate_editorial_plan,
)
from app.editorial_planning.writer import editorial_plan_path, plan_sha256
from app.source_analysis.models import SourceMap
from app.source_analysis.writer import source_map_path


def provenance_for(
    signature: str,
    settings: PlannerSettings | None = None,
    *,
    source_map_path_value: str = "",
) -> EditorialPlanMetadata:
    settings = settings or frozen_production_settings()
    return EditorialPlanMetadata(
        prompt_version=EDITORIAL_PLANNER_PROMPT_VERSION,
        transport_version=EDITORIAL_PLAN_TRANSPORT_VERSION,
        schema_version=EDITORIAL_PLAN_SCHEMA_VERSION,
        coverage_policy_version=IDEA_COVERAGE_POLICY_VERSION,
        validator_version=EDITORIAL_PLAN_VALIDATOR_VERSION,
        provider=settings.provider,
        model=settings.model,
        strategy=settings.strategy or STRATEGY_GLOBAL,
        thinking_mode=settings.thinking_mode,
        effort=settings.effort or "",
        signature=signature,
        source_map_path=source_map_path_value,
    )


def signature_for_source_map(
    source_map_sha256: str,
    prompt_sha256: str,
    response_schema_sha256: str,
    settings: PlannerSettings | None = None,
) -> tuple[str, PlannerSignatureInputs]:
    settings = settings or frozen_production_settings()
    inputs = default_signature_inputs(
        source_map_sha256=source_map_sha256,
        prompt_sha256=prompt_sha256,
        response_schema_sha256=response_schema_sha256,
        provider=settings.provider,
        model=settings.model,
        thinking_mode=settings.thinking_mode,
        effort=settings.effort,
        max_output_tokens=settings.max_output_tokens,
        strategy=settings.strategy,
    )
    return build_planner_signature(inputs), inputs


def materialize_plan(
    transport: dict,
    source_map: SourceMap,
    *,
    source_map_sha256: str,
    source_map_bytes: int,
    prompt_sha256: str,
    response_schema_sha256: str,
    source_map_path_value: str = "",
    settings: PlannerSettings | None = None,
) -> tuple[EditorialPlan, EditorialPlanValidation, str]:
    settings = settings or frozen_production_settings()
    signature, _inputs = signature_for_source_map(
        source_map_sha256,
        prompt_sha256,
        response_schema_sha256,
        settings,
    )
    from app.editorial_planning.models import SourceMapIdentity

    identity = SourceMapIdentity(
        sha256=source_map_sha256,
        bytes=source_map_bytes,
        schema_version=source_map.schema_version,
        project=source_map.project_name,
        topic_count=len(source_map.topics),
        idea_count=len(source_map.ideas),
        example_count=len(source_map.examples),
        reference_count=len(source_map.references),
        uncertainty_count=len(source_map.uncertainties),
        repetition_count=len(source_map.repetitions),
    )
    plan = reconstruct_editorial_plan(
        transport,
        source_map,
        provenance=provenance_for(
            signature, settings, source_map_path_value=source_map_path_value
        ),
        source_map_identity=identity,
    )
    validation = validate_editorial_plan(plan, source_map, settings=settings)
    return plan, validation, plan_sha256(plan)


def load_published_source_map(
    project_name: str, *, sortie_dir: Path | None = None
) -> tuple[SourceMap, bytes, str, Path]:
    path = source_map_path(project_name, sortie_dir=sortie_dir)
    source_map, raw, digest = load_source_map_file(path)
    return source_map, raw, digest, path


def load_published_editorial_plan(
    project_name: str, *, sortie_dir: Path | None = None
) -> tuple[EditorialPlan, bytes, str, Path]:
    """Production reader for the published EditorialPlan. Not an audit parser."""
    path = editorial_plan_path(project_name, sortie_dir=sortie_dir)
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise EditorialPlanValidationError(
            ["editorial_plan.json n'est pas un objet JSON"]
        )
    return EditorialPlan.from_dict(payload), raw, digest, path
