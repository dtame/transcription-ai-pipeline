"""
Phase 1 — Test d'intégration du contrat Transcript V2 (§27, §45, §48, §52).

Scénario synthétique complet, avec faux Whisper et sans ffmpeg :

    projet retreat
      ├── audio 1.mp3    court            (fr)
      ├── audio 2.mp3    long / segmenté  (fr, 3 segments techniques)
      └── audio 10.mp3   court            (sw — langue hors fr/en)

Vérifie de bout en bout :

    ordre naturel des sources          AUDIO IDs
    SRC IDs                            provenance
    timestamps relatifs à chaque audio langues
    stats                              absence de duplication d'overlap
    validation                         artefacts V1 conservés

Puis la propriété centrale de reprise (§27) :

    run unique  ==  run interrompu + reprise

au niveau du contrat V2 lui-même.
"""

from __future__ import annotations

import json
import shutil

import pytest

import app.pipeline_runner as pipeline_runner
import app.segmented_transcription_service as sts
import app.transcription_service as transcription_service
from app.transcript_capture import audio_capture_path, capture_dir
from app.transcript_writer import (
    INVALIDATED_JSON_NAME,
    TRANSCRIPT_JSON_NAME,
    TRANSCRIPT_TXT_NAME,
)

from app.tests.whisper_fakes import FakeWhisperModel

LONG_AUDIO = "audio 2.mp3"
LONG_DURATION = 1900.0    # → part_001 0-910, part_002 900-1810, part_003 1800-1900
SHORT_DURATION = 600.0

# « phrase B » est prononcée à 900-908 s : vue par part_001 en fin de segment ET
# par part_002 dans son overlap entrant.
# « phrase D » est prononcée à 1795-1805 s : même situation entre part_002 et
# part_003. Le contrat final ne doit contenir chacune qu'une seule fois.
WHISPER_PAYLOAD = {
    "audio 1.mp3": [(0.0, 11.42, "intro courte")],
    "audio 10.mp3": [(0.0, 9.5, "habari za asubuhi")],
    "part_001.mp3": [(0.0, 5.0, "phrase A"), (900.0, 908.0, "phrase B")],
    "part_002.mp3": [
        (0.0, 8.0, "phrase B"),
        (20.0, 30.0, "phrase C"),
        (895.0, 905.0, "phrase D"),
    ],
    "part_003.mp3": [(0.0, 5.0, "phrase D"), (12.0, 20.0, "phrase E")],
}

EXPECTED_SEGMENTS = [
    ("SRC000001", "AUDIO001", 1, 0.0, 11.42, "intro courte"),
    ("SRC000002", "AUDIO002", 2, 0.0, 5.0, "phrase A"),
    ("SRC000003", "AUDIO002", 2, 900.0, 908.0, "phrase B"),
    ("SRC000004", "AUDIO002", 2, 920.0, 930.0, "phrase C"),
    ("SRC000005", "AUDIO002", 2, 1795.0, 1805.0, "phrase D"),
    ("SRC000006", "AUDIO002", 2, 1812.0, 1820.0, "phrase E"),
    ("SRC000007", "AUDIO003", 3, 0.0, 9.5, "habari za asubuhi"),
]


def _model(**kwargs) -> FakeWhisperModel:
    return FakeWhisperModel(segments_by_name=WHISPER_PAYLOAD, **kwargs)


@pytest.fixture
def v2_project(monkeypatch, segmented_env, make_audio_project):
    """
    Projet complet prêt pour une transcription hermétique.

    Les langues sont attribuées par fichier audio : « audio 10.mp3 » est en
    swahili afin de prouver qu'une langue hors fr/en n'est plus retranscrite de
    force en anglais.
    """
    project = make_audio_project(
        name="retreat",
        audio_files={
            "audio 1.mp3": b"court-un",
            "audio 2.mp3": b"long-deux",
            "audio 10.mp3": b"court-dix",
        },
    )

    segmented_env.duration = LONG_DURATION

    monkeypatch.setattr(
        sts, "should_segment_audio", lambda audio_path: audio_path.name == LONG_AUDIO
    )
    monkeypatch.setattr(
        pipeline_runner, "get_audio_duration_seconds", lambda path: SHORT_DURATION
    )
    monkeypatch.setattr(transcription_service, "print_progress", lambda **kwargs: None)

    return project


def _language_of(audio_name: str) -> str:
    return "sw" if audio_name == "audio 10.mp3" else "fr"


class _MultiLanguageModel(FakeWhisperModel):
    """Rapporte une langue différente selon le fichier audio transcrit."""

    def transcribe(self, audio_path, **kwargs):
        from pathlib import Path

        self.language = _language_of(Path(audio_path).name)
        return super().transcribe(audio_path, **kwargs)


def transcribe_everything(project, model=None) -> dict:
    model = model if model is not None else _MultiLanguageModel(
        segments_by_name=WHISPER_PAYLOAD
    )
    return pipeline_runner._run_transcription(model, project)


def build_v2(project):
    return pipeline_runner._run_transcript_v2(project)


def published_data(project) -> dict:
    return json.loads(
        (project.transcripts_dir / TRANSCRIPT_JSON_NAME).read_text(encoding="utf-8")
    )


@pytest.fixture
def transcribed(v2_project):
    result = transcribe_everything(v2_project)
    assert result["status"] == "success"
    build_v2(v2_project)
    return v2_project


# ---------------------------------------------------------------------------
# 48 — Contrat produit de bout en bout
# ---------------------------------------------------------------------------

class TestEndToEndContract:

    def test_both_v2_artifacts_are_published(self, transcribed):
        assert (transcribed.transcripts_dir / TRANSCRIPT_TXT_NAME).exists()
        assert (transcribed.transcripts_dir / TRANSCRIPT_JSON_NAME).exists()

    def test_contract_header(self, transcribed):
        payload = published_data(transcribed)

        assert payload["schema_version"] == "1.0"
        assert payload["transcript_id"] == "TR001"
        assert payload["project"] == {"name": "retreat"}

    def test_sources_follow_the_natural_order(self, transcribed):
        payload = published_data(transcribed)

        assert [(s["source_id"], s["order"], s["filename"]) for s in payload["sources"]] == [
            ("AUDIO001", 1, "audio 1.mp3"),
            ("AUDIO002", 2, "audio 2.mp3"),
            ("AUDIO003", 3, "audio 10.mp3"),
        ]

    def test_natural_order_differs_from_the_v1_discovery_order(self, transcribed):
        """V1 traite les fichiers dans l'ordre lexicographique : 1, 10, 2."""
        assert [path.name for path in transcribed.audio_files] == [
            "audio 1.mp3",
            "audio 10.mp3",
            "audio 2.mp3",
        ]

        assert [s["filename"] for s in published_data(transcribed)["sources"]] == [
            "audio 1.mp3",
            "audio 2.mp3",
            "audio 10.mp3",
        ]

    def test_segments_ids_provenance_and_timestamps(self, transcribed):
        payload = published_data(transcribed)

        assert [
            (s["id"], s["source_id"], s["source_order"], s["start"], s["end"], s["text"])
            for s in payload["segments"]
        ] == EXPECTED_SEGMENTS

    def test_overlap_produced_no_duplicate(self, transcribed):
        texts = [s["text"] for s in published_data(transcribed)["segments"]]

        assert texts.count("phrase B") == 1
        assert texts.count("phrase D") == 1
        assert texts == [
            "intro courte",
            "phrase A",
            "phrase B",
            "phrase C",
            "phrase D",
            "phrase E",
            "habari za asubuhi",
        ]

    def test_technical_segments_are_not_editorial_sources(self, transcribed):
        payload = published_data(transcribed)

        assert payload["stats"]["source_count"] == 3
        assert "part_001" not in json.dumps(payload)

    def test_languages(self, transcribed):
        payload = published_data(transcribed)

        assert payload["language"] == {"primary": "fr", "detected": ["fr", "sw"]}
        assert [s["detected_language"] for s in payload["sources"]] == ["fr", "fr", "sw"]

    def test_language_outside_fr_en_was_never_forced_to_english(self, v2_project):
        model = _MultiLanguageModel(segments_by_name=WHISPER_PAYLOAD)
        transcribe_everything(v2_project, model)
        build_v2(v2_project)

        assert all(kwargs == {} for _, kwargs in model.calls), (
            "Aucun appel Whisper ne doit forcer language='en'."
        )
        assert published_data(v2_project)["sources"][2]["detected_language"] == "sw"
        assert "habari za asubuhi" in (
            v2_project.transcripts_dir / TRANSCRIPT_TXT_NAME
        ).read_text(encoding="utf-8")

    def test_stats(self, transcribed):
        assert published_data(transcribed)["stats"] == {
            "source_count": 3,
            "segment_count": 7,
            "duration_seconds": 3100.0,
            "word_count": 15,
        }

    def test_human_transcript_has_one_section_per_source(self, transcribed):
        rendered = (transcribed.transcripts_dir / TRANSCRIPT_TXT_NAME).read_text(
            encoding="utf-8"
        )

        assert "SOURCE 1 — audio 1.mp3" in rendered
        assert "SOURCE 2 — audio 2.mp3" in rendered
        assert "SOURCE 3 — audio 10.mp3" in rendered
        assert rendered.index("SOURCE 2") < rendered.index("SOURCE 3")
        assert "[30:12 -> 30:20] phrase E" in rendered

    def test_published_contract_is_valid(self, transcribed):
        from app.transcript_builder import build_project_transcript
        from app.transcript_validator import validate_transcript_document

        document = build_project_transcript(
            transcribed.name, transcribed.output_dir
        )

        assert validate_transcript_document(document) == []


# ---------------------------------------------------------------------------
# 28 — Idempotence
# ---------------------------------------------------------------------------

class TestIdempotence:

    def test_rebuilding_produces_a_byte_identical_contract(self, transcribed):
        first = (transcribed.transcripts_dir / TRANSCRIPT_JSON_NAME).read_text(
            encoding="utf-8"
        )

        build_v2(transcribed)

        assert (transcribed.transcripts_dir / TRANSCRIPT_JSON_NAME).read_text(
            encoding="utf-8"
        ) == first

    def test_a_second_pipeline_run_transcribes_nothing_and_keeps_the_contract(
        self, transcribed
    ):
        before = published_data(transcribed)

        model = _MultiLanguageModel(segments_by_name=WHISPER_PAYLOAD)
        transcribe_everything(transcribed, model)
        build_v2(transcribed)

        assert model.call_count == 0
        assert published_data(transcribed) == before

    def test_src_ids_do_not_shift_between_runs(self, transcribed):
        before = [s["id"] for s in published_data(transcribed)["segments"]]

        build_v2(transcribed)

        assert [s["id"] for s in published_data(transcribed)["segments"]] == before


# ---------------------------------------------------------------------------
# 36 — Artefacts V1 conservés
# ---------------------------------------------------------------------------

class TestV1ArtifactsArePreserved:

    def test_individual_transcripts_still_exist(self, transcribed):
        for stem in ("audio 1", "audio 2", "audio 10"):
            assert (transcribed.transcripts_dir / f"{stem}.txt").exists()

    def test_segment_transcripts_still_exist(self, transcribed):
        segment_dir = (
            transcribed.output_dir / "segment_transcripts" / "audio 2"
        )

        assert sorted(path.name for path in segment_dir.glob("*.txt")) == [
            "part_001.txt",
            "part_002.txt",
            "part_003.txt",
        ]

    def test_v1_merge_ignores_the_v2_human_transcript(self, transcribed, silence_logs):
        from app.transcript_merger import merge_project_transcripts

        merged = merge_project_transcripts(transcribed)
        content = merged.read_text(encoding="utf-8")

        assert content.count("intro courte") == 1, (
            "transcript.txt V2 contient déjà tout le projet : il ne doit pas "
            "être fusionné une seconde fois."
        )
        assert "PARTIE 1" in content
        assert "SOURCE 1 —" not in content

    def test_project_state_still_tracks_every_audio_file(self, transcribed):
        from app.project_state import load_project_state

        state = load_project_state(transcribed)

        for audio_path in transcribed.audio_files:
            entry = state["files"][str(audio_path.resolve())]
            assert entry["status"] == "transcribed"


# ---------------------------------------------------------------------------
# 27 / 45 — Reprise
# ---------------------------------------------------------------------------

class TestResumeEquivalence:

    def _reset_output(self, project):
        shutil.rmtree(project.output_dir)
        project.transcripts_dir.mkdir(parents=True, exist_ok=True)

    def test_interrupted_run_then_resume_gives_the_same_contract(self, v2_project):
        # RUN 1 — interruption brutale pendant le 2e segment technique
        with pytest.raises(KeyboardInterrupt):
            transcribe_everything(
                v2_project,
                _MultiLanguageModel(
                    segments_by_name=WHISPER_PAYLOAD,
                    interrupt_on={"part_002.mp3"},
                ),
            )

        # RUN 2 — reprise
        resumed = _MultiLanguageModel(segments_by_name=WHISPER_PAYLOAD)
        assert transcribe_everything(v2_project, resumed)["status"] == "success"
        assert resumed.names_called == ["part_002.mp3", "part_003.mp3"], (
            "La reprise ne doit retranscrire que les segments manquants."
        )

        build_v2(v2_project)
        after_resume = published_data(v2_project)

        # RUN unique, à données Whisper identiques
        self._reset_output(v2_project)
        assert transcribe_everything(v2_project)["status"] == "success"
        build_v2(v2_project)

        assert published_data(v2_project) == after_resume

    def test_restored_segments_keep_their_capture(self, v2_project):
        with pytest.raises(KeyboardInterrupt):
            transcribe_everything(
                v2_project,
                _MultiLanguageModel(
                    segments_by_name=WHISPER_PAYLOAD,
                    interrupt_on={"part_002.mp3"},
                ),
            )

        segment_dir = v2_project.output_dir / "segment_transcripts" / "audio 2"

        assert (segment_dir / "part_001.json").exists(), (
            "La capture d'un segment terminé doit survivre à l'interruption."
        )
        assert not (segment_dir / "part_002.json").exists()

    def test_no_contract_is_published_while_a_file_is_incomplete(self, v2_project):
        with pytest.raises(KeyboardInterrupt):
            transcribe_everything(
                v2_project,
                _MultiLanguageModel(
                    segments_by_name=WHISPER_PAYLOAD,
                    interrupt_on={"part_002.mp3"},
                ),
            )

        with pytest.raises(RuntimeError, match="incomplète"):
            build_v2(v2_project)

        assert not (v2_project.transcripts_dir / TRANSCRIPT_JSON_NAME).exists()


# ---------------------------------------------------------------------------
# 52 — Gestion d'erreur de la couche V2
# ---------------------------------------------------------------------------

class TestV2FailureDoesNotDestroyV1:

    def test_missing_capture_fails_explicitly_and_keeps_v1(self, transcribed):
        audio_capture_path(transcribed.output_dir, "audio 2").unlink()

        with pytest.raises(RuntimeError, match="audio 2"):
            build_v2(transcribed)

        assert (transcribed.transcripts_dir / "audio 2.txt").exists(), (
            "La transcription V1 ne doit pas être détruite par un échec V2."
        )

    def test_stale_contract_is_invalidated_on_failure(self, transcribed):
        assert (transcribed.transcripts_dir / TRANSCRIPT_JSON_NAME).exists()

        audio_capture_path(transcribed.output_dir, "audio 2").unlink()

        with pytest.raises(RuntimeError):
            build_v2(transcribed)

        assert not (transcribed.transcripts_dir / TRANSCRIPT_JSON_NAME).exists(), (
            "Un ancien contrat ne doit pas être pris pour le résultat courant."
        )
        assert (transcribed.transcripts_dir / INVALIDATED_JSON_NAME).exists()

    def test_project_without_any_capture_skips_the_step(self, transcribed):
        """
        Projet transcrit avant la Phase 1 : aucune capture disponible. L'étape est
        ignorée sans erreur et sans publier de contrat, la transcription V1
        restant intacte.
        """
        (transcribed.transcripts_dir / TRANSCRIPT_JSON_NAME).unlink()
        shutil.rmtree(capture_dir(transcribed.output_dir))

        assert build_v2(transcribed) is None
        assert not (transcribed.transcripts_dir / TRANSCRIPT_JSON_NAME).exists()
        assert (transcribed.transcripts_dir / "audio 2.txt").exists()
