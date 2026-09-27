"""
Phase 1 — Modèles du contrat Transcript V2.

Couvre app.transcript_models :

- création d'une source, d'un segment, d'un document ;
- forme exacte du JSON sérialisé (blocs obligatoires, ordre des clés) ;
- identifiants SRC / AUDIO ;
- politique de précision des timestamps ;
- UTF-8 lisible (ensure_ascii=False) ;
- absence de champ non déterministe.
"""

from __future__ import annotations

import json

import pytest

from app.file_utils import read_json, write_json_atomic
from app.transcript_models import (
    CAPTURE_MODE_SEGMENTED,
    DEFAULT_TRANSCRIPT_ID,
    SCHEMA_VERSION,
    AudioCapture,
    CapturedPart,
    CapturedSegment,
    TranscriptDocument,
    TranscriptSegment,
    TranscriptSource,
    TranscriptStats,
    format_audio_id,
    format_src_id,
    round_seconds,
)


def _source(order=1, filename="01-session.mp3", language="fr", duration=1200.45):
    return TranscriptSource(
        source_id=format_audio_id(order),
        order=order,
        filename=filename,
        duration_seconds=duration,
        detected_language=language,
    )


def _segment(index=1, order=1, start=0.0, end=11.42, text="Ceci est un test"):
    return TranscriptSegment(
        id=format_src_id(index),
        source_id=format_audio_id(order),
        source_order=order,
        start=start,
        end=end,
        text=text,
    )


def _document(sources=None, segments=None, primary="fr", detected=None):
    sources = sources if sources is not None else [_source()]
    segments = segments if segments is not None else [_segment()]

    return TranscriptDocument(
        project_name="demo_conference",
        sources=sources,
        segments=segments,
        stats=TranscriptStats(
            source_count=len(sources),
            segment_count=len(segments),
            duration_seconds=round_seconds(
                sum(s.duration_seconds for s in sources)
            ),
            word_count=sum(len(s.text.split()) for s in segments),
        ),
        primary_language=primary,
        detected_languages=detected if detected is not None else ["fr"],
    )


# ---------------------------------------------------------------------------
# 37 — Création des objets
# ---------------------------------------------------------------------------

class TestSourceCreation:

    def test_source_exposes_its_provenance(self):
        source = _source(order=3, filename="03-conclusion.mp3", language="en")

        assert source.source_id == "AUDIO003"
        assert source.order == 3
        assert source.filename == "03-conclusion.mp3"
        assert source.detected_language == "en"

    def test_source_serializes_all_contract_fields(self):
        assert _source().to_dict() == {
            "source_id": "AUDIO001",
            "order": 1,
            "filename": "01-session.mp3",
            "duration_seconds": 1200.45,
            "detected_language": "fr",
        }


class TestSegmentCreation:

    def test_segment_exposes_its_coordinates(self):
        segment = _segment(index=347, order=3, start=428.37, end=441.92)

        assert segment.id == "SRC000347"
        assert segment.source_id == "AUDIO003"
        assert segment.source_order == 3
        assert segment.start == 428.37
        assert segment.end == 441.92

    def test_segment_duration_is_derived(self):
        assert _segment(start=10.0, end=15.5).duration_seconds == pytest.approx(5.5)

    def test_segment_serializes_all_contract_fields(self):
        assert _segment().to_dict() == {
            "id": "SRC000001",
            "source_id": "AUDIO001",
            "source_order": 1,
            "start": 0.0,
            "end": 11.42,
            "text": "Ceci est un test",
        }


# ---------------------------------------------------------------------------
# 37 — Sérialisation du document
# ---------------------------------------------------------------------------

class TestDocumentSerialization:

    def test_all_mandatory_blocks_are_present_in_order(self):
        payload = _document().to_dict()

        assert list(payload) == [
            "schema_version",
            "transcript_id",
            "project",
            "language",
            "sources",
            "segments",
            "stats",
        ]

    def test_schema_version_and_transcript_id_are_stable(self):
        payload = _document().to_dict()

        assert payload["schema_version"] == "1.0" == SCHEMA_VERSION
        assert payload["transcript_id"] == "TR001" == DEFAULT_TRANSCRIPT_ID

    def test_project_and_language_blocks(self):
        payload = _document(primary="fr", detected=["en", "fr"]).to_dict()

        assert payload["project"] == {"name": "demo_conference"}
        assert payload["language"] == {"primary": "fr", "detected": ["en", "fr"]}

    def test_stats_block(self):
        payload = _document().to_dict()

        assert payload["stats"] == {
            "source_count": 1,
            "segment_count": 1,
            "duration_seconds": 1200.45,
            "word_count": 4,
        }

    def test_no_editorial_notion_leaks_into_the_contract(self):
        payload = json.dumps(_document().to_dict())

        for editorial in ("chapter", "chapitre", "section", "theme", "summary",
                         "résumé", "idea", "idée", "importance", "title"):
            assert editorial not in payload

    def test_no_non_deterministic_field(self):
        payload = json.dumps(_document().to_dict())

        for volatile in ("generated_at", "timestamp", "uuid", "created_at"):
            assert volatile not in payload

    def test_two_identical_documents_serialize_identically(self):
        assert _document().to_dict() == _document().to_dict()

    def test_helpers_expose_segments_by_source(self):
        document = _document(
            sources=[_source(order=1), _source(order=2, filename="02.mp3")],
            segments=[_segment(1, order=1), _segment(2, order=2), _segment(3, order=2)],
        )

        assert document.source_by_id("AUDIO002").filename == "02.mp3"
        assert document.source_by_id("AUDIO404") is None
        assert [s.id for s in document.segments_for("AUDIO002")] == [
            "SRC000002",
            "SRC000003",
        ]


# ---------------------------------------------------------------------------
# 37 — UTF-8
# ---------------------------------------------------------------------------

class TestUtf8:

    def test_french_text_stays_readable_on_disk(self, tmp_path):
        document = _document(
            segments=[_segment(text="épreuve de fidélité au cœur du récit")]
        )
        path = tmp_path / "transcript_data.json"

        write_json_atomic(path, document.to_dict())
        raw = path.read_text(encoding="utf-8")

        assert "épreuve de fidélité au cœur du récit" in raw
        assert "\\u00e9" not in raw

    def test_non_latin_text_survives_a_round_trip(self, tmp_path):
        document = _document(segments=[_segment(text="混乱を避けるため")])
        path = tmp_path / "transcript_data.json"

        write_json_atomic(path, document.to_dict())

        assert read_json(path)["segments"][0]["text"] == "混乱を避けるため"


# ---------------------------------------------------------------------------
# 38 — Identifiants
# ---------------------------------------------------------------------------

class TestIdentifiers:

    @pytest.mark.parametrize(
        "index, expected",
        [
            (1, "SRC000001"),
            (2, "SRC000002"),
            (347, "SRC000347"),
            (999999, "SRC999999"),
            (1000000, "SRC1000000"),
        ],
    )
    def test_src_id_uses_six_digits(self, index, expected):
        assert format_src_id(index) == expected

    @pytest.mark.parametrize(
        "order, expected",
        [(1, "AUDIO001"), (2, "AUDIO002"), (10, "AUDIO010"), (123, "AUDIO123")],
    )
    def test_audio_id_uses_three_digits(self, order, expected):
        assert format_audio_id(order) == expected

    def test_src_ids_sort_in_creation_order(self):
        ids = [format_src_id(i) for i in range(1, 15)]
        assert sorted(ids) == ids, "Le zéro-padding doit rendre le tri texte fiable."


# ---------------------------------------------------------------------------
# 13 / 42 — Politique de précision
# ---------------------------------------------------------------------------

class TestTimestampPrecision:

    @pytest.mark.parametrize(
        "value, expected",
        [
            (12.37, 12.37),
            (18.94, 18.94),
            (0.0, 0.0),
            (441.9187, 441.919),
            (3725.5, 3725.5),
        ],
    )
    def test_precision_is_kept_to_the_millisecond(self, value, expected):
        assert round_seconds(value) == expected

    def test_timestamps_are_never_truncated_to_whole_seconds(self):
        payload = _document(segments=[_segment(start=12.37, end=18.94)]).to_dict()

        assert payload["segments"][0]["start"] == 12.37
        assert payload["segments"][0]["end"] == 18.94

    def test_timestamps_are_numbers_not_formatted_strings(self):
        payload = _document().to_dict()

        assert isinstance(payload["segments"][0]["start"], float)
        assert isinstance(payload["segments"][0]["end"], float)


# ---------------------------------------------------------------------------
# 26 — Modèles de capture
# ---------------------------------------------------------------------------

class TestCaptureModels:

    def _capture(self):
        return AudioCapture(
            filename="Retreat 1.mp3",
            duration_seconds=1900.0,
            mode=CAPTURE_MODE_SEGMENTED,
            parts=[
                CapturedPart(
                    id="part_001",
                    start_seconds=0.0,
                    end_seconds=910.0,
                    effective_start_local=0.0,
                    detected_language="fr",
                    segments=[CapturedSegment(0.0, 5.0, "début")],
                ),
                CapturedPart(
                    id="part_002",
                    start_seconds=900.0,
                    end_seconds=1810.0,
                    effective_start_local=10.0,
                    detected_language="fr",
                    segments=[CapturedSegment(12.345, 18.912, "suite")],
                ),
            ],
        )

    def test_capture_round_trip_preserves_everything(self):
        original = self._capture()

        restored = AudioCapture.from_dict(original.to_dict())

        assert restored == original

    def test_capture_keeps_precise_local_timestamps(self):
        payload = self._capture().to_dict()

        assert payload["parts"][1]["segments"][0] == {
            "start": 12.345,
            "end": 18.912,
            "text": "suite",
        }

    def test_capture_keeps_only_the_portable_filename(self):
        assert self._capture().to_dict()["filename"] == "Retreat 1.mp3"

    def test_capture_records_the_technical_offsets(self):
        payload = self._capture().to_dict()

        assert payload["parts"][1]["start_seconds"] == 900.0
        assert payload["parts"][1]["effective_start_local"] == 10.0
