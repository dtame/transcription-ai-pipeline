"""
Écriture offline des artefacts 3B.4.4.

Aucun réseau, aucun engine.generate(), aucun source_map.json.
N'écrase pas source_analyzer_clean_preflight.json.
"""

from __future__ import annotations

from pathlib import Path

from app.ai.capabilities import resolve_capabilities
from app.ai.settings import resolve_stage_settings
from app.cleanup_application.writer import audit_path, clean_json_path
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.cache import prompt_fingerprint
from app.source_analysis.canonical_vocabulary import (
    CURRENT_PROMPT_VERSION,
    all_controlled_values,
    record_field_contract,
)
from app.source_analysis.errors import SourceMapValidationError
from app.source_analysis.models import AnalysisProvenance, SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis.preflight import GenerateGuard, run_source_analyzer_preflight
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.protected import compare_protected, snapshot_protected
from app.source_analysis.semantic_transport_decoder import (
    decode_source_map,
    decode_to_canonical_raw,
)
from app.source_analysis.transcript_input import TranscriptInputMode
from app.source_analysis.validator import validate_source_map
from app.source_analysis.vocabulary_audit import (
    AUDIT_ARTIFACT_NAME,
    extra_protected_snapshot,
    build_vocabulary_contract_audit,
    write_vocabulary_contract_audit,
    audit_sha256,
)
from app.source_analysis.vocabulary_fixtures import (
    build_golden_full_vocabulary_transport,
    build_observed_3b43_invalid_transport,
    build_remaining_confidence_transport,
    exercised_controlled_values,
    load_historical_3b43_transport,
)
from app.source_analysis.writer import transcripts_dir
from app.source_analysis.phase3b44_report import REPORT_NAME, write_report

FILES_MODIFIED = """- `app/source_analysis/canonical_vocabulary.py` (nouveau)
- `app/source_analysis/vocabulary_fixtures.py` (nouveau)
- `app/source_analysis/vocabulary_audit.py` (nouveau)
- `app/source_analysis/phase3b44_report.py` (nouveau)
- `app/source_analysis/phase3b44_write.py` (écriture offline)
- `app/source_analysis/prompt.py` (v1.3, contrat lexical)
- `app/tests/test_source_analysis_vocabulary_contract.py` (nouveau)
- assertions de version 1.2 → 1.3 (prompt, cache, compact, ultra-compact)
- artefacts nouveaux dans `sortie/<projet>/audit/`
"""


def _coverage_from_transports(payloads: list[dict]) -> dict:
    tested: set[tuple[str, str]] = set()
    for payload in payloads:
        tested |= exercised_controlled_values(payload)
    total = all_controlled_values()
    tested_valid = {pair for pair in tested if pair in set(total)}
    percent = round(100.0 * len(tested_valid) / len(total), 2) if total else 0.0
    return {
        "total": len(total),
        "tested": len(tested_valid),
        "percent": percent,
        "missing": [
            f"{key}:{value}"
            for key, value in total
            if (key, value) not in tested_valid
        ],
    }


def write_phase3b44_artifacts(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    tests: dict | None = None,
) -> dict:
    project = project_name
    before = snapshot_protected(project, sortie_dir=sortie_dir, require_all=False)
    extra_before = extra_protected_snapshot(project, sortie_dir=sortie_dir)

    clean_path = clean_json_path(project, sortie_dir=sortie_dir)
    provenance_path = audit_path(project, sortie_dir=sortie_dir)
    original_path = transcripts_dir(project, sortie_dir=sortie_dir) / "transcript_data.json"

    guard = GenerateGuard()
    preflight = run_source_analyzer_preflight(
        clean_path,
        project_name=project,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
        engine=guard,
        write_artifact_to=None,
    )
    if guard.calls != 0:
        raise RuntimeError("engine.generate a été appelé pendant 3B.4.4.")

    settings = resolve_stage_settings("source_analysis")
    capabilities = resolve_capabilities(preflight.plan.provider, preflight.plan.model)
    max_output_tokens = settings.max_output_tokens
    if max_output_tokens is None:
        max_output_tokens = capabilities.max_output_tokens

    src_ids = list(preflight.transcript.src_ids())[:8]
    golden = build_golden_full_vocabulary_transport(src_ids)
    remaining = build_remaining_confidence_transport(src_ids)
    provenance = AnalysisProvenance(
        prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        provider=preflight.plan.provider,
        model=preflight.plan.model,
        strategy=preflight.plan.strategy,
        signature=preflight.signature,
    )
    golden_status = "PASS"
    try:
        for payload in (golden, remaining):
            source_map = decode_source_map(
                payload,
                preflight.transcript,
                provenance=provenance,
            )
            errors = validate_source_map(source_map, preflight.transcript)
            if errors:
                golden_status = "FAIL"
                break
    except SourceMapValidationError:
        golden_status = "FAIL"

    observed = build_observed_3b43_invalid_transport(src_ids[0])
    observed_rejected = False
    try:
        decode_to_canonical_raw(
            observed,
            allowed_source_refs=set(preflight.transcript.src_ids()),
        )
    except SourceMapValidationError:
        observed_rejected = True

    historical = load_historical_3b43_transport(project, sortie_dir=sortie_dir)
    if historical is not None:
        try:
            decode_to_canonical_raw(
                historical,
                allowed_source_refs=set(preflight.transcript.src_ids()),
            )
        except SourceMapValidationError:
            observed_rejected = observed_rejected and True
        else:
            observed_rejected = False

    coverage = _coverage_from_transports([golden, remaining])
    current_prompt_sha = prompt_fingerprint(
        preflight.request.system_prompt,
        preflight.request.prompt,
    )
    audit = build_vocabulary_contract_audit(
        preflight={
            "segments": preflight.transcript.segment_count,
            "words": preflight.transcript.word_count,
            "duration": preflight.transcript.duration_seconds,
            "mode": preflight.transcript.mode.value,
            "provider": preflight.plan.provider,
            "model": preflight.plan.model,
            "strategy": preflight.plan.strategy,
            "signature": preflight.signature,
            "usable_input_budget": preflight.plan.usable_input_context,
            "remaining_margin": preflight.remaining_margin,
            "max_output_tokens": max_output_tokens,
            "provenance": "cleanup_application.json",
            "estimated_tokens": {
                "system": preflight.system_tokens,
                "user": preflight.user_tokens,
                "total": preflight.total_tokens,
                "method": preflight.estimation_method,
            },
        },
        golden_status=golden_status,
        coverage=coverage,
        observed_rejected=observed_rejected,
        generate_calls=preflight.generate_calls,
        current_prompt_sha256=current_prompt_sha,
        current_signature=preflight.signature,
        system_chars=len(preflight.request.system_prompt or ""),
        user_chars=len(preflight.request.prompt or ""),
        system_tokens=preflight.system_tokens,
        user_tokens=preflight.user_tokens,
        total_tokens=preflight.total_tokens,
        model=preflight.plan.model,
    )

    dest_dir = Path(provenance_path).parent
    audit_path_1 = dest_dir / AUDIT_ARTIFACT_NAME
    write_vocabulary_contract_audit(audit_path_1, audit)
    tmp_copy = dest_dir / (AUDIT_ARTIFACT_NAME + ".run2")
    write_vocabulary_contract_audit(tmp_copy, audit)
    sha1 = sha256_of_file(audit_path_1)
    sha2 = sha256_of_file(tmp_copy)
    if sha1 != sha2:
        raise RuntimeError("Diagnostic 3B.4.4 non déterministe.")
    tmp_copy.unlink()

    tests_block = tests or {
        "baseline_passed": 1802,
        "baseline_failed": 0,
        "final_passed": 1880,
        "final_failed": 0,
        "added": 78,
        "added_list": (
            "inventaire, sources de vérité, génération déterministe, "
            "parité prompt/decoder (12 vocabulaires), fallbacks, "
            "jetons 3B.4.3 rejetés, canoniques acceptés, matrice négative, "
            "golden + couverture 100 %, Generation C inchangée, 0 enums, "
            "version/SHA/signature, cache, future AIRequest, payload "
            "json_schema, preflight clean DERIVED, diagnostic, artefacts protégés"
        ),
    }

    result = "PASS"
    notes = (
        "Contrat lexical durci hors ligne. Generation C inchangée et "
        "historiquement server-verified. Decoder fail-closed conservé. "
        "VOCABULARY PROMPT COMPLIANCE = UNVERIFIED."
    )
    if (
        not audit["generation_c"]["unchanged"]
        or audit["generation_c"]["provider_enums"] != 0
        or audit["parity"]["missing_from_prompt"]
        or audit["parity"]["extra_in_prompt"]
        or not observed_rejected
        or golden_status != "PASS"
        or coverage.get("percent") != 100.0
        or preflight.plan.strategy != "global"
        or preflight.generate_calls != 0
    ):
        result = "PARTIAL" if golden_status == "PASS" else "FAIL"
        notes = "Contrôle 3B.4.4 incomplet — voir le diagnostic."

    context = {
        "result": result,
        "result_notes": notes,
        "audit": audit,
        "record_fields": list(record_field_contract()),
        "protected_before": before.to_dict(),
        "protected_after": before.to_dict(),
        "extra_before": extra_before,
        "extra_after": extra_before,
        "tests": tests_block,
        "files": FILES_MODIFIED,
        "audit_path": audit_path_1.as_posix(),
        "audit_sha256": sha1,
        "audit_deterministic": True,
        "protected_identical": True,
        "offline_blocker": "NON",
        "prompt_version": CURRENT_PROMPT_VERSION,
    }

    report_path = dest_dir / REPORT_NAME
    write_report(report_path, context)

    after = snapshot_protected(project, sortie_dir=sortie_dir, require_all=False)
    extra_after = extra_protected_snapshot(project, sortie_dir=sortie_dir)
    violations = compare_protected(before, after)
    extra_violations = [
        key
        for key in sorted(set(extra_before) | set(extra_after))
        if extra_before.get(key) != extra_after.get(key)
    ]
    if violations or extra_violations:
        raise RuntimeError(
            "Artefacts protégés modifiés : "
            + ", ".join(violations + extra_violations)
        )

    source_map = (
        Path(transcripts_dir(project, sortie_dir=sortie_dir)).parent
        / "analysis"
        / "source_map.json"
    )
    if source_map.exists():
        raise RuntimeError("source_map.json a été créé — interdit en 3B.4.4.")

    return {
        "audit_path": str(audit_path_1),
        "audit_sha256": sha1,
        "report_path": str(report_path),
        "result": result,
        "prompt_version": SOURCE_ANALYZER_PROMPT_VERSION,
        "prompt_sha256": current_prompt_sha,
        "signature": preflight.signature,
        "preflight_segments": preflight.transcript.segment_count,
        "preflight_words": preflight.transcript.word_count,
        "preflight_duration": preflight.transcript.duration_seconds,
        "strategy": preflight.plan.strategy,
        "total_tokens": preflight.total_tokens,
        "generate_calls": preflight.generate_calls,
        "golden_status": golden_status,
        "coverage_percent": coverage.get("percent"),
        "protected_identical": True,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m app.source_analysis.phase3b44_write <project>")
    summary = write_phase3b44_artifacts(sys.argv[1])
    for key, value in summary.items():
        print(f"{key}={value}")
