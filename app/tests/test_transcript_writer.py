"""
Phase 1 — Publication des artefacts Transcript V2 (§14, §30, §31, §35, §47, §52).

Couvre app.transcript_writer :

- rendu humain de transcript.txt (séparateurs, sections, timestamps lisibles) ;
- option de diagnostic affichant les identifiants SRC ;
- écriture atomique de transcript.txt et transcript_data.json ;
- crash pendant l'écriture : aucun artefact tronqué, artefact valide préservé ;
- échec de validation : rien n'est publié et l'artefact antérieur est invalidé.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.transcript_models import (
    TranscriptDocument,
    TranscriptSegment,
    TranscriptSource,
    TranscriptStats,
)
from app.transcript_validator import TranscriptValidationError
from app.transcript_writer import (
    INVALIDATED_JSON_NAME,
    TRANSCRIPT_JSON_NAME,
    TRANSCRIPT_TXT_NAME,
    invalidate_published_transcript,
    publish_transcript_artifacts,
    render_transcript_text,
)


def _stats(sources, segments):
    return TranscriptStats(
        source_count=len(sources),
        segment_count=len(segments),
        duration_seconds=round(sum(s.duration_seconds for s in sources), 3),
        word_count=sum(len(s.text.split()) for s in segments),
    )


def document(sources=None, segments=None, primary="fr", detected=None):
    sources = sources if sources is not None else [
        TranscriptSource("AUDIO001", 1, "01-Nouvel enregistrement.m4a", 300.0, "fr"),
        TranscriptSource("AUDIO002", 2, "02-Nouvel enregistrement.m4a", 600.0, "fr"),
    ]
    segments = segments if segments is not None else [
        TranscriptSegment("SRC000001", "AUDIO001", 1, 0.0, 11.42, "Ceci est un test"),
        TranscriptSegment("SRC000002", "AUDIO001", 1, 12.37, 28.94, "Suite du test"),
        TranscriptSegment("SRC000003", "AUDIO002", 2, 0.0, 8.5, "Bonjour"),
    ]

    return TranscriptDocument(
        project_name="demo_conference",
        sources=sources,
        segments=segments,
        stats=_stats(sources, segments),
        primary_language=primary,
        detected_languages=detected if detected is not None else ["fr"],
    )


@pytest.fixture
def transcripts_dir(tmp_path):
    directory = tmp_path / "sortie" / "demo_conference" / "transcripts"
    directory.mkdir(parents=True)
    return directory


def _leftovers(directory: Path) -> list[str]:
    return sorted(
        path.name for path in directory.iterdir()
        if path.name.endswith(".partial")
    )


# ---------------------------------------------------------------------------
# 14 / 35 — Rendu humain
# ---------------------------------------------------------------------------

class TestRenderTranscriptText:

    def test_each_source_gets_an_explicit_separated_section(self):
        rendered = render_transcript_text(document())

        assert rendered.splitlines() == [
            "=" * 80,
            "SOURCE 1 — 01-Nouvel enregistrement.m4a",
            "=" * 80,
            "",
            "[00:00 -> 00:11] Ceci est un test",
            "[00:12 -> 00:28] Suite du test",
            "",
            "=" * 80,
            "SOURCE 2 — 02-Nouvel enregistrement.m4a",
            "=" * 80,
            "",
            "[00:00 -> 00:08] Bonjour",
        ]

    def test_timestamps_are_relative_to_each_source(self):
        rendered = render_transcript_text(document())
        sections = rendered.split("=" * 80)

        assert "[00:00 -> 00:08] Bonjour" in sections[-1], (
            "La deuxième source redémarre à 00:00 : aucune timeline globale."
        )

    def test_long_timestamps_use_the_hour_format(self):
        rendered = render_transcript_text(
            document(
                sources=[TranscriptSource("AUDIO001", 1, "a.mp3", 7200.0, "fr")],
                segments=[
                    TranscriptSegment(
                        "SRC000001", "AUDIO001", 1, 3612.37, 3618.94, "après une heure"
                    )
                ],
            )
        )

        assert "[01:00:12 -> 01:00:18] après une heure" in rendered

    def test_src_ids_are_absent_by_default(self):
        assert "SRC000001" not in render_transcript_text(document())

    def test_src_ids_can_be_shown_for_diagnosis(self):
        rendered = render_transcript_text(document(), include_src_ids=True)

        assert "SRC000001 [00:00 -> 00:11] Ceci est un test" in rendered

    def test_empty_document_renders_empty_text(self):
        rendered = render_transcript_text(document(sources=[], segments=[]))

        assert rendered == ""

    def test_source_without_segment_still_appears(self):
        rendered = render_transcript_text(
            document(
                sources=[TranscriptSource("AUDIO001", 1, "muet.mp3", 30.0, "fr")],
                segments=[],
            )
        )

        assert "SOURCE 1 — muet.mp3" in rendered

    def test_rendering_is_deterministic(self):
        assert render_transcript_text(document()) == render_transcript_text(document())


# ---------------------------------------------------------------------------
# 30 / 31 — Publication
# ---------------------------------------------------------------------------

class TestPublication:

    def test_both_artifacts_are_published(self, transcripts_dir):
        published = publish_transcript_artifacts(document(), transcripts_dir)

        assert published["text"] == transcripts_dir / TRANSCRIPT_TXT_NAME
        assert published["data"] == transcripts_dir / TRANSCRIPT_JSON_NAME
        assert published["text"].exists()
        assert published["data"].exists()

    def test_published_json_matches_the_document(self, transcripts_dir):
        doc = document()
        published = publish_transcript_artifacts(doc, transcripts_dir)

        assert json.loads(published["data"].read_text(encoding="utf-8")) == doc.to_dict()

    def test_no_temporary_file_survives_a_successful_publication(self, transcripts_dir):
        publish_transcript_artifacts(document(), transcripts_dir)

        assert _leftovers(transcripts_dir) == []

    def test_json_is_utf8_readable_and_indented(self, transcripts_dir):
        doc = document(
            segments=[
                TranscriptSegment(
                    "SRC000001", "AUDIO001", 1, 0.0, 5.0, "épreuve de fidélité au cœur"
                )
            ],
            sources=[TranscriptSource("AUDIO001", 1, "a.mp3", 300.0, "fr")],
        )

        published = publish_transcript_artifacts(doc, transcripts_dir)
        raw = published["data"].read_text(encoding="utf-8")

        assert "épreuve de fidélité au cœur" in raw
        assert "\\u00e9" not in raw
        assert '\n  "schema_version"' in raw, "Indentation lisible et diffable."

    def test_republishing_identical_data_produces_an_identical_file(self, transcripts_dir):
        publish_transcript_artifacts(document(), transcripts_dir)
        first = (transcripts_dir / TRANSCRIPT_JSON_NAME).read_text(encoding="utf-8")

        publish_transcript_artifacts(document(), transcripts_dir)
        second = (transcripts_dir / TRANSCRIPT_JSON_NAME).read_text(encoding="utf-8")

        assert first == second, "Aucun champ non déterministe dans le contrat."

    def test_publication_creates_the_directory_if_missing(self, tmp_path):
        target = tmp_path / "sortie" / "p" / "transcripts"

        publish_transcript_artifacts(document(), target)

        assert (target / TRANSCRIPT_JSON_NAME).exists()


# ---------------------------------------------------------------------------
# 47 — Écriture atomique
# ---------------------------------------------------------------------------

class TestAtomicWriting:

    @pytest.fixture
    def truncating_write(self, monkeypatch):
        """
        Simule un crash en cours d'écriture : le fichier temporaire ne reçoit
        que la moitié du contenu, puis l'écriture échoue.
        """
        real_write_text = Path.write_text

        def _install(target_suffix: str):
            def _write_text(self, content, *args, **kwargs):
                if self.name.endswith(target_suffix + ".partial"):
                    real_write_text(self, content[: len(content) // 2], *args, **kwargs)
                    raise OSError("disque plein")
                return real_write_text(self, content, *args, **kwargs)

            monkeypatch.setattr(Path, "write_text", _write_text)

        return _install

    def test_crash_while_writing_json_leaves_no_truncated_contract(
        self, transcripts_dir, truncating_write
    ):
        truncating_write(TRANSCRIPT_JSON_NAME)

        with pytest.raises(OSError, match="disque plein"):
            publish_transcript_artifacts(document(), transcripts_dir)

        assert not (transcripts_dir / TRANSCRIPT_JSON_NAME).exists()
        assert _leftovers(transcripts_dir) == []

    def test_a_previous_valid_json_survives_a_crashed_write(
        self, transcripts_dir, truncating_write
    ):
        publish_transcript_artifacts(document(), transcripts_dir)
        previous = (transcripts_dir / TRANSCRIPT_JSON_NAME).read_text(encoding="utf-8")

        truncating_write(TRANSCRIPT_JSON_NAME)

        with pytest.raises(OSError):
            publish_transcript_artifacts(document(), transcripts_dir)

        current = (transcripts_dir / TRANSCRIPT_JSON_NAME).read_text(encoding="utf-8")
        assert current == previous
        assert json.loads(current)["schema_version"] == "1.0"
        assert _leftovers(transcripts_dir) == []

    def test_crash_while_writing_text_leaves_no_truncated_transcript(
        self, transcripts_dir, truncating_write
    ):
        truncating_write(TRANSCRIPT_TXT_NAME)

        with pytest.raises(OSError):
            publish_transcript_artifacts(document(), transcripts_dir)

        assert not (transcripts_dir / TRANSCRIPT_TXT_NAME).exists()
        assert _leftovers(transcripts_dir) == []

    def test_a_previous_valid_text_survives_a_crashed_write(
        self, transcripts_dir, truncating_write
    ):
        publish_transcript_artifacts(document(), transcripts_dir)
        previous = (transcripts_dir / TRANSCRIPT_TXT_NAME).read_text(encoding="utf-8")

        truncating_write(TRANSCRIPT_TXT_NAME)

        with pytest.raises(OSError):
            publish_transcript_artifacts(document(), transcripts_dir)

        assert (transcripts_dir / TRANSCRIPT_TXT_NAME).read_text(
            encoding="utf-8"
        ) == previous

    def test_json_is_not_published_when_the_text_write_fails(
        self, transcripts_dir, truncating_write
    ):
        """
        transcript.txt est écrit en premier : un JSON publié implique toujours un
        transcript.txt correspondant.
        """
        truncating_write(TRANSCRIPT_TXT_NAME)

        with pytest.raises(OSError):
            publish_transcript_artifacts(document(), transcripts_dir)

        assert not (transcripts_dir / TRANSCRIPT_JSON_NAME).exists()


# ---------------------------------------------------------------------------
# 29 / 52 — Échec de validation et invalidation
# ---------------------------------------------------------------------------

class TestValidationGateAndInvalidation:

    def _invalid_document(self):
        doc = document()
        doc.sources[1] = TranscriptSource("AUDIO001", 1, "b.m4a", 600.0, "fr")
        return doc

    def test_an_invalid_document_is_never_published(self, transcripts_dir):
        with pytest.raises(TranscriptValidationError):
            publish_transcript_artifacts(self._invalid_document(), transcripts_dir)

        assert not (transcripts_dir / TRANSCRIPT_JSON_NAME).exists()
        assert not (transcripts_dir / TRANSCRIPT_TXT_NAME).exists()
        assert _leftovers(transcripts_dir) == []

    def test_a_stale_contract_is_invalidated_after_a_validation_failure(
        self, transcripts_dir
    ):
        publish_transcript_artifacts(document(), transcripts_dir)

        with pytest.raises(TranscriptValidationError):
            publish_transcript_artifacts(self._invalid_document(), transcripts_dir)

        assert not (transcripts_dir / TRANSCRIPT_JSON_NAME).exists(), (
            "Aucun fichier transcript_data.json ne doit prétendre être le "
            "résultat courant après un échec."
        )
        assert (transcripts_dir / INVALIDATED_JSON_NAME).exists(), (
            "Les données précédentes restent consultables pour inspection."
        )

    def test_invalidation_is_a_no_op_without_previous_contract(self, transcripts_dir):
        assert invalidate_published_transcript(transcripts_dir) is None

    def test_invalidation_moves_the_file_without_losing_data(self, transcripts_dir):
        publish_transcript_artifacts(document(), transcripts_dir)
        previous = (transcripts_dir / TRANSCRIPT_JSON_NAME).read_text(encoding="utf-8")

        invalidated = invalidate_published_transcript(transcripts_dir)

        assert invalidated.read_text(encoding="utf-8") == previous
