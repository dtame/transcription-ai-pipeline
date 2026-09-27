"""
Phase 3A.2C — corpus réel : transcript clean en mode DERIVED.

Lecture seule des artefacts protégés. Le préflight peut écrire uniquement
source_analyzer_clean_preflight.json. Ignoré si le projet n'est pas présent.
"""

from __future__ import annotations

import pytest

from app.cleanup_application.writer import audit_path, clean_json_path
from app.language_cleanup.transcript_source import transcript_data_file
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.preflight import (
    GenerateGuard,
    run_source_analyzer_preflight,
)
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)

PROJECT = "pastoral_retreat_v2_validation"

_original = transcript_data_file(PROJECT)
_clean = clean_json_path(PROJECT)
_provenance = audit_path(PROJECT)

pytestmark = pytest.mark.skipif(
    not (_original.exists() and _clean.exists() and _provenance.exists()),
    reason=f"corpus réel {PROJECT} absent de cette machine",
)


def test_real_clean_loads_as_derived():
    sha_original = sha256_of_file(_original)
    sha_clean = sha256_of_file(_clean)
    sha_audit = sha256_of_file(_provenance)

    transcript = load_transcript_input(
        _clean,
        project_name=PROJECT,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=_provenance,
        original_transcript_path=_original,
    )

    assert transcript.segment_count == 8298
    assert transcript.word_count == 38313
    assert transcript.duration_seconds == 19954.601
    assert transcript.transcript_id == "TR001"
    assert transcript.mode is TranscriptInputMode.DERIVED

    from app.source_analysis.provenance import validate_derived_provenance

    proven = validate_derived_provenance(
        derived_path=_clean,
        provenance_path=_provenance,
        original_transcript_path=_original,
    )

    assert proven.original_segment_count == 8415
    assert proven.derived_segment_count == 8298
    assert proven.removed_count == 117
    assert proven.removed_set_matches is True
    assert proven.survivors_unchanged is True
    assert proven.original_sha256 == sha_original
    assert proven.derived_sha256 == sha_clean

    assert sha256_of_file(_original) == sha_original
    assert sha256_of_file(_clean) == sha_clean
    assert sha256_of_file(_provenance) == sha_audit


def test_real_clean_preflight_stops_before_generate():
    guard = GenerateGuard()

    result = run_source_analyzer_preflight(
        _clean,
        project_name=PROJECT,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=_provenance,
        original_transcript_path=_original,
        engine=guard,
        write_artifact_to=None,
    )

    assert guard.calls == 0
    assert result.generate_calls == 0
    assert result.plan.strategy == "global"
    assert result.transcript.segment_count == 8298
    assert result.transcript.word_count == 38313
    assert result.request.response_schema is not None
    assert result.to_artifact()["network_calls"] == 0
    assert result.to_artifact()["source_analysis"]["would_call_ai"] is False
