"""
Cache par fenêtre — identité = WindowAnalysisSignature 3B.7.2.

Un fichier existant n'est jamais un HIT à lui seul.
Chaque entrée est revalidée. Le transport est obligatoire pour un HIT
de production. Les ``.partial`` ne comptent pas.
"""

from __future__ import annotations

from pathlib import Path
from app.ai.settings import StageSettings
from app.source_analysis.models import forbidden_editorial_fields
from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    WindowCacheAmbiguityError,
    WindowResultValidationError,
    WindowSourceRefError,
    WindowTransportValidationError,
)
from app.source_analysis.orchestration_models import (
    CACHE_CORRUPT,
    CACHE_HIT,
    CACHE_INVALID,
    CACHE_MISS,
    CACHE_STALE,
    WindowCacheInspection,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_analyzer import (
    recover_window_from_transport,
    resolve_window_execution,
)
from app.source_analysis.window_models import (
    WindowSemanticResult,
    window_semantic_result_from_dict,
)
from app.source_analysis.window_validator import validate_window_result
from app.source_analysis.window_writer import (
    ambiguous_window_artifacts,
    artifact_sha256,
    leftover_partial,
    metadata_path,
    read_json_artifact,
    result_path,
    transport_path,
    window_dir,
)
from app.source_analysis_hybrid.contracts import WindowInput


def expected_window_signature(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    settings: StageSettings | None = None,
    engine=None,
    prompt_version: str | None = None,
) -> str:
    """Réutilise la formule 3B.7.2. Pas de seconde identité concurrente."""
    return resolve_window_execution(
        window,
        transcript,
        settings=settings,
        engine=engine,
        prompt_version=prompt_version,
    ).signature


def inspect_window_cache(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    windows_root: Path,
    project_name: str = "fixture",
    expected_signature: str,
    settings: StageSettings | None = None,
    engine=None,
) -> WindowCacheInspection:
    """
    Revalidation obligatoire. Pas de confiance en un statut historique.

    HIT seulement si :
    artefacts présents, signature attendue, window_id, input hash,
    prompt/transport/provider, parse, WindowResultValidator PASS,
    SRC encore valides, IDs intermédiaires, pas de fuite éditoriale,
    transport présent et hash cohérent.
    """
    t_path = transport_path(project_name, window.window_id, root=windows_root)
    r_path = result_path(project_name, window.window_id, root=windows_root)
    m_path = metadata_path(project_name, window.window_id, root=windows_root)
    directory = window_dir(project_name, window.window_id, root=windows_root)
    extras = ambiguous_window_artifacts(directory)
    if extras:
        raise WindowCacheAmbiguityError(
            f"{window.window_id} : artefacts ambigus {extras} — "
            "aucun choix par mtime / plus récent."
        )

    t_status, transport = read_json_artifact(t_path)
    r_status, result_payload = read_json_artifact(r_path)
    m_status, metadata = read_json_artifact(m_path)
    transport_present = t_status == "ok"
    result_present = r_status == "ok"
    metadata_present = m_status == "ok"
    partial_only = (
        leftover_partial(t_path) is not None
        or leftover_partial(r_path) is not None
        or leftover_partial(m_path) is not None
    ) and not (transport_present or result_present or metadata_present)

    base = dict(
        window_id=window.window_id,
        expected_signature=expected_signature,
        transport_present=transport_present,
        metadata_present=metadata_present,
        result_present=result_present,
        transport_hash_matches=False,
        signature_matches=False,
        recoverable=False,
        transport_path=str(t_path),
        result_path=str(r_path),
        metadata_path=str(m_path),
    )

    if t_status == "corrupt" or r_status == "corrupt" or m_status == "corrupt":
        base["recoverable"] = _transport_binding_ok(
            window,
            expected_signature=expected_signature,
            metadata=metadata if m_status == "ok" else None,
            transport_path=t_path,
            transport_ok=transport_present,
        )
        return WindowCacheInspection(
            cache_state=CACHE_CORRUPT,
            error_classification="CACHE_CORRUPT",
            **base,
        )

    if partial_only or (
        t_status == "missing"
        and r_status == "missing"
        and m_status in {"missing", "partial"}
    ):
        return WindowCacheInspection(
            cache_state=CACHE_MISS,
            error_classification="CACHE_MISS",
            **base,
        )

    identity = (metadata or {}).get("identity") if metadata_present else None
    if not isinstance(identity, dict):
        identity = None

    recorded_signature = None
    if isinstance(identity, dict):
        recorded_signature = identity.get("window_analysis_signature")
    result_signature = None
    loaded_result: WindowSemanticResult | None = None
    result_error: str | None = None
    if result_present and result_payload is not None:
        leaked = forbidden_editorial_fields(result_payload)
        if leaked or any(
            field in result_payload
            for field in (
                "chapters",
                "sections",
                "book_title",
                "book_subtitle",
                "editorial_plan",
                "source_map",
            )
        ):
            result_error = "EDITORIAL_LEAKAGE"
            loaded_result = None
        else:
            try:
                loaded_result = window_semantic_result_from_dict(result_payload)
                result_signature = loaded_result.window_analysis_signature
            except WindowResultValidationError:
                result_error = "RESULT_PARSE"
                loaded_result = None

    observed_signature = recorded_signature or result_signature
    signature_matches = observed_signature == expected_signature
    base["signature_matches"] = bool(signature_matches)

    transport_hash_matches = False
    if transport_present and isinstance(identity, dict) and identity.get(
        "transport_sha256"
    ):
        try:
            transport_hash_matches = (
                artifact_sha256(t_path) == identity["transport_sha256"]
            )
        except OSError:
            transport_hash_matches = False
    base["transport_hash_matches"] = transport_hash_matches

    if observed_signature and observed_signature != expected_signature:
        return WindowCacheInspection(
            cache_state=CACHE_STALE,
            error_classification="SIGNATURE_MISMATCH",
            **base,
        )

    if not transport_present:
        return WindowCacheInspection(
            cache_state=CACHE_INVALID,
            error_classification="TRANSPORT_MISSING",
            **base,
        )

    recoverable = _transport_binding_ok(
        window,
        expected_signature=expected_signature,
        metadata=metadata if metadata_present else None,
        transport_path=t_path,
        transport_ok=True,
    )
    base["recoverable"] = recoverable

    if loaded_result is None:
        classification = result_error or (
            "RESULT_MISSING" if r_status == "missing" else "RESULT_INVALID"
        )
        return WindowCacheInspection(
            cache_state=CACHE_INVALID,
            error_classification=classification,
            **base,
        )

    try:
        _assert_result_matches_contract(
            loaded_result, window, expected_signature=expected_signature
        )
        validate_window_result(loaded_result, window)
    except (
        WindowResultValidationError,
        WindowSourceRefError,
        WindowTransportValidationError,
        SourceMapEditorialLeakError,
        SourceMapValidationError,
    ) as exc:
        return WindowCacheInspection(
            cache_state=CACHE_INVALID,
            error_classification=_classify_validation(exc),
            **base,
        )

    if not metadata_present or not transport_hash_matches:
        return WindowCacheInspection(
            cache_state=CACHE_INVALID,
            error_classification=(
                "METADATA_MISSING" if not metadata_present else "TRANSPORT_HASH_MISMATCH"
            ),
            recoverable=recoverable,
            **{k: v for k, v in base.items() if k != "recoverable"},
        )

    if not _identity_matches_expected(
        identity if isinstance(identity, dict) else {},
        window,
        transcript,
        expected_signature=expected_signature,
        settings=settings,
        engine=engine,
    ):
        return WindowCacheInspection(
            cache_state=CACHE_STALE,
            error_classification="IDENTITY_MISMATCH",
            **base,
        )

    return WindowCacheInspection(
        cache_state=CACHE_HIT,
        result=loaded_result,
        recoverable=False,
        **{k: v for k, v in base.items() if k != "recoverable"},
    )


def recover_cached_window(
    window: WindowInput,
    transcript: TranscriptInput,
    inspection: WindowCacheInspection,
    *,
    windows_root: Path,
    project_name: str = "fixture",
    settings: StageSettings | None = None,
    engine=None,
    prompt_version: str | None = None,
) -> WindowSemanticResult:
    """Recovery offline. 0 engine.generate."""
    if not inspection.recoverable:
        raise WindowResultValidationError(
            f"{window.window_id} : recovery transport interdite "
            f"({inspection.error_classification})."
        )
    t_status, transport = read_json_artifact(Path(inspection.transport_path))
    m_status, metadata = read_json_artifact(Path(inspection.metadata_path))
    if t_status != "ok" or m_status != "ok" or transport is None or metadata is None:
        raise WindowResultValidationError(
            f"{window.window_id} : transport/metadata illisibles pour recovery."
        )
    return recover_window_from_transport(
        window,
        transcript,
        windows_root=windows_root,
        project_name=project_name,
        expected_signature=inspection.expected_signature,
        settings=settings,
        engine=engine,
        metadata=metadata,
        transport=transport,
        prompt_version=prompt_version,
    )


def _transport_binding_ok(
    window: WindowInput,
    *,
    expected_signature: str,
    metadata: dict | None,
    transport_path: Path,
    transport_ok: bool,
) -> bool:
    if not transport_ok or not isinstance(metadata, dict):
        return False
    identity = metadata.get("identity")
    if not isinstance(identity, dict):
        return False
    if identity.get("window_analysis_signature") != expected_signature:
        return False
    if identity.get("window_id") != window.window_id:
        return False
    if identity.get("window_input_hash") != window.input_hash:
        return False
    recorded = identity.get("transport_sha256")
    if not recorded:
        return False
    try:
        return artifact_sha256(transport_path) == recorded
    except OSError:
        return False


def _assert_result_matches_contract(
    result: WindowSemanticResult,
    window: WindowInput,
    *,
    expected_signature: str,
) -> None:
    if result.window_id != window.window_id:
        raise WindowResultValidationError(
            f"window_id cache {result.window_id!r} ≠ {window.window_id!r}"
        )
    if result.window_input_hash != window.input_hash:
        raise WindowResultValidationError("window_input_hash cache ≠ WindowInput")
    if result.window_analysis_signature != expected_signature:
        raise WindowResultValidationError("signature cache ≠ signature attendue")


def _identity_matches_expected(
    identity: dict,
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    expected_signature: str,
    settings: StageSettings | None,
    engine,
) -> bool:
    if identity.get("window_analysis_signature") != expected_signature:
        return False
    if identity.get("window_id") != window.window_id:
        return False
    if identity.get("window_input_hash") != window.input_hash:
        return False
    bundle = resolve_window_execution(
        window, transcript, settings=settings, engine=engine
    )
    inputs = bundle.signature_inputs
    checks = (
        identity.get("prompt_version") == inputs.prompt_version,
        identity.get("prompt_sha256") == inputs.prompt_sha256,
        identity.get("transport_version") == inputs.transport_version,
        identity.get("response_schema_sha256") == inputs.response_schema_sha256,
        identity.get("provider") == inputs.provider,
        identity.get("model") == inputs.model,
        identity.get("max_output_tokens") == inputs.max_output_tokens,
        identity.get("output_language") == inputs.output_language,
        identity.get("planner_version") == inputs.planner_version,
    )
    return all(checks)


def _classify_validation(exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc)
    if "fuite" in text or "éditorial" in text or name == "SourceMapEditorialLeakError":
        return "EDITORIAL_LEAKAGE"
    if "SRC" in text or name == "WindowSourceRefError":
        return "INVALID_SRC"
    if "identifiant" in text:
        return "INVALID_INTERMEDIATE_ID"
    if "window_id" in text:
        return "WINDOW_ID_MISMATCH"
    if "window_input_hash" in text:
        return "INPUT_HASH_MISMATCH"
    return "VALIDATION_FAILED"


__all__ = [
    "expected_window_signature",
    "inspect_window_cache",
    "recover_cached_window",
]
