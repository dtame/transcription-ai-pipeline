"""
État projet et rapport de l'étape source_analysis.

Module volontairement SANS dépendance à app.ai ni à l'analyseur : il est importé
par app/report_service.py, et générer un rapport ne doit pas charger la couche
IA ni, a fortiori, pouvoir déclencher quoi que ce soit.

L'étape s'inscrit dans project_state.json sous la clé `source_analysis`, à côté
de `final_document` et `publication`, et suit la même convention que la V1 :
la clé n'existe qu'à partir du moment où l'étape a tourné. Aucune modification
de ensure_state_structure() n'est donc nécessaire — les projets existants
gardent exactement l'état qu'ils avaient.

La comptabilité financière ne passe PAS par ici : les tokens et les coûts vivent
dans `ai_usage`, un seul endroit. Ce bloc ne porte que le statut, la signature,
le chemin et des compteurs descriptifs.
"""

from __future__ import annotations

from typing import Any, Mapping

STATE_KEY = "source_analysis"

STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def load_state_block(state: Mapping[str, Any] | None) -> dict:
    """Bloc `source_analysis` de l'état projet, ou un dictionnaire vide."""
    if not isinstance(state, Mapping):
        return {}

    block = state.get(STATE_KEY)

    return dict(block) if isinstance(block, Mapping) else {}


def build_completed_block(
    *,
    signature: str,
    path: str,
    provider: str,
    model: str,
    strategy: str,
    prompt_version: str,
    schema_version: str,
    cached: bool,
    stats: Mapping[str, Any],
    updated_at: str,
) -> dict:
    """
    Bloc d'état d'une analyse publiée et valide.

    `cached=True` signale une réutilisation sans appel : c'est l'information qui
    explique pourquoi `ai_usage` n'a pas bougé alors que l'étape a « tourné ».
    """
    return {
        "status": STATUS_COMPLETED,
        "cached": bool(cached),
        "signature": signature,
        "path": path,
        "provider": provider,
        "model": model,
        "strategy": strategy,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "topics": int(stats.get("topic_count", 0)),
        "ideas": int(stats.get("idea_count", 0)),
        "examples": int(stats.get("example_count", 0)),
        "references": int(stats.get("reference_count", 0)),
        "uncertainties": int(stats.get("uncertainty_count", 0)),
        "repetitions": int(stats.get("repetition_count", 0)),
        "source_coverage_ratio": float(stats.get("source_coverage_ratio", 0.0)),
        "updated_at": updated_at,
        "error": None,
    }


def build_failed_block(
    *,
    signature: str,
    provider: str,
    model: str,
    strategy: str,
    prompt_version: str,
    schema_version: str,
    error_type: str,
    updated_at: str,
    previous: Mapping[str, Any] | None = None,
) -> dict:
    """
    Bloc d'état d'un échec.

    `path` retient le chemin de l'analyse valide précédente si elle existe : le
    fichier n'a pas été touché, et prétendre le contraire brouillerait le
    diagnostic. Le statut, lui, passe bien à `failed` — il n'y a pas d'analyse à
    jour.
    """
    previous_block = dict(previous or {})
    previous_path = previous_block.get("path") if previous_block.get(
        "status"
    ) == STATUS_COMPLETED else None

    return {
        "status": STATUS_FAILED,
        "cached": False,
        "signature": signature,
        "path": previous_path,
        "provider": provider,
        "model": model,
        "strategy": strategy,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "error": error_type,
        "updated_at": updated_at,
    }


def build_source_analysis_report(state: Mapping[str, Any] | None) -> dict:
    """
    Section additive `source_analysis` de report.json.

    Toujours présente et de forme stable, comme `ai_usage` : un projet purement
    transcrit affiche status="pending", ce qui est une information, alors qu'une
    section absente n'en serait pas une.

    Aucun token, aucun coût : cette comptabilité reste dans `ai_usage`, et la
    dupliquer ici garantirait à terme deux chiffres divergents.
    """
    block = load_state_block(state)

    return {
        "status": str(block.get("status") or STATUS_PENDING),
        "cached": bool(block.get("cached", False)),
        "path": block.get("path"),
        "provider": str(block.get("provider") or ""),
        "model": str(block.get("model") or ""),
        "strategy": str(block.get("strategy") or ""),
        "prompt_version": str(block.get("prompt_version") or ""),
        "schema_version": str(block.get("schema_version") or ""),
        "topics": int(block.get("topics", 0) or 0),
        "ideas": int(block.get("ideas", 0) or 0),
        "examples": int(block.get("examples", 0) or 0),
        "references": int(block.get("references", 0) or 0),
        "uncertainties": int(block.get("uncertainties", 0) or 0),
        "repetitions": int(block.get("repetitions", 0) or 0),
        "source_coverage_ratio": float(block.get("source_coverage_ratio", 0.0) or 0.0),
        "error": block.get("error"),
    }
