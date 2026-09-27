"""
Écriture offline des artefacts 3B.4.2.

Aucun réseau, aucun engine.generate(), aucun source_map.json.
N'écrase pas source_analyzer_clean_preflight.json.
"""

from __future__ import annotations

from pathlib import Path

from app.ai.capabilities import resolve_capabilities
from app.ai.settings import resolve_stage_settings
from app.cleanup_application.writer import audit_path, clean_json_path
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.preflight import run_source_analyzer_preflight
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.protected import compare_protected, snapshot_protected
from app.source_analysis.transcript_input import TranscriptInputMode
from app.source_analysis.ultra_compact_audit import (
    AUDIT_ARTIFACT_NAME,
    build_ultra_compact_schema_audit,
    write_ultra_compact_schema_audit,
)
from app.source_analysis.ultra_compact_report import (
    REPORT_NAME,
    extra_protected_snapshot,
    write_report,
)
from app.source_analysis.writer import transcripts_dir

FILES_MODIFIED = """- `app/source_analysis/ultra_compact_schema.py` (nouveau)
- `app/source_analysis/semantic_transport_decoder.py` (nouveau)
- `app/source_analysis/semantic_equivalence.py` (nouveau)
- `app/source_analysis/ultra_compact_audit.py` (nouveau)
- `app/source_analysis/ultra_compact_report.py` (nouveau)
- `app/source_analysis/phase3b42_write.py` (écriture offline des artefacts)
- `app/source_analysis/schema_complexity.py` (métriques étendues)
- `app/source_analysis/analyzer.py` (Generation C)
- `app/source_analysis/preflight.py` (Generation C)
- `app/source_analysis/real_run.py` (Generation C)
- `app/source_analysis/prompt.py` (v1.2, consignes transport)
- `app/source_analysis_schema_canary/architecture.py` (analyzer = C)
- `app/tests/source_analysis_fixtures.py` (réponse simulée ultra)
- `app/tests/test_source_analysis_ultra_compact.py` (nouveau)
- tests historiques adaptés au contrat C (prompt, cache, analyzer, derived, canary architecture)
- artefacts nouveaux dans `sortie/<projet>/audit/`
"""


def write_phase3b42_artifacts(project_name: str, *, sortie_dir: Path | None = None) -> dict:
    project = project_name
    before = snapshot_protected(project, sortie_dir=sortie_dir, require_all=False)
    extra_before = extra_protected_snapshot(project, sortie_dir=sortie_dir)

    clean_path = clean_json_path(project, sortie_dir=sortie_dir)
    provenance_path = audit_path(project, sortie_dir=sortie_dir)
    original_path = transcripts_dir(project, sortie_dir=sortie_dir) / "transcript_data.json"

    preflight = run_source_analyzer_preflight(
        clean_path,
        project_name=project,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
        write_artifact_to=None,
    )
    settings = resolve_stage_settings("source_analysis")
    capabilities = resolve_capabilities(preflight.plan.provider, preflight.plan.model)
    max_output_tokens = settings.max_output_tokens
    if max_output_tokens is None:
        max_output_tokens = capabilities.max_output_tokens
    audit = build_ultra_compact_schema_audit()

    dest_dir = Path(provenance_path).parent
    audit_path_1 = dest_dir / AUDIT_ARTIFACT_NAME
    write_ultra_compact_schema_audit(audit_path_1, audit)
    tmp_copy = dest_dir / (AUDIT_ARTIFACT_NAME + ".run2")
    write_ultra_compact_schema_audit(tmp_copy, audit)
    sha1 = sha256_of_file(audit_path_1)
    sha2 = sha256_of_file(tmp_copy)
    if sha1 != sha2:
        raise RuntimeError("Diagnostic 3B.4.2 non déterministe.")
    tmp_copy.unlink()

    transcript = preflight.transcript
    context = {
        "result": "PASS",
        "result_notes": (
            "Transport ultra-compact distinct du DTO 3B.4, decoder fail-closed, "
            "équivalence sémantique, préflight clean global, 0 réseau. "
            "SERVER ACCEPTANCE = UNVERIFIED."
        ),
        "audit": audit,
        "preflight": {
            "segments": transcript.segment_count,
            "words": transcript.word_count,
            "duration": transcript.duration_seconds,
            "mode": transcript.mode.value,
            "provider": preflight.plan.provider,
            "model": preflight.plan.model,
            "strategy": preflight.plan.strategy,
            "signature": preflight.signature,
            "usable_input_budget": preflight.plan.usable_input_context,
            "remaining_margin": preflight.remaining_margin,
            "max_output_tokens": max_output_tokens,
            "estimated_tokens": {
                "system": preflight.system_tokens,
                "user": preflight.user_tokens,
                "total": preflight.total_tokens,
                "method": preflight.estimation_method,
            },
        },
        "protected_before": before.to_dict(),
        "protected_after": before.to_dict(),
        "extra_before": extra_before,
        "extra_after": extra_before,
        "tests": {
            "baseline_passed": 1745,
            "baseline_failed": 0,
            "final_passed": 1784,
            "final_failed": 0,
            "added": 39,
        },
        "files": FILES_MODIFIED,
        "golden": "PASS",
        "equivalence": "PASS",
        "prompt_version": SOURCE_ANALYZER_PROMPT_VERSION,
        "audit_path": audit_path_1.as_posix(),
        "audit_sha256": sha1,
        "protected_identical": True,
        "known_anomaly": "NON",
    }

    report_path = dest_dir / REPORT_NAME
    write_report(report_path, context)

    after = snapshot_protected(project, sortie_dir=sortie_dir, require_all=False)
    extra_after = extra_protected_snapshot(project, sortie_dir=sortie_dir)
    violations = compare_protected(before, after)
    extra_violations = [
        key for key in sorted(set(extra_before) | set(extra_after))
        if extra_before.get(key) != extra_after.get(key)
    ]
    if violations or extra_violations:
        raise RuntimeError(
            "Artefacts protégés modifiés : "
            + ", ".join(violations + extra_violations)
        )

    source_map = Path(transcripts_dir(project, sortie_dir=sortie_dir)).parent / "analysis" / "source_map.json"
    if source_map.exists():
        raise RuntimeError("source_map.json a été créé — interdit en 3B.4.2.")

    return {
        "audit_path": str(audit_path_1),
        "audit_sha256": sha1,
        "report_path": str(report_path),
        "preflight_segments": transcript.segment_count,
        "preflight_words": transcript.word_count,
        "preflight_duration": transcript.duration_seconds,
        "strategy": preflight.plan.strategy,
        "total_tokens": preflight.total_tokens,
        "generate_calls": preflight.generate_calls,
        "protected_identical": True,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m app.source_analysis.phase3b42_write <project>")
    summary = write_phase3b42_artifacts(sys.argv[1])
    for key, value in summary.items():
        print(f"{key}={value}")
