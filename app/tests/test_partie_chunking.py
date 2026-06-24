"""
Tests pour le chunking PARTIE-aware et la fonction is_real_transcript_content.

Critères de succès :
- Aucun chunk ne doit être généré à partir de simples séparateurs PARTIE.
- Aucun faux contenu ne doit être produit par l'IA à partir de chunks vides.
"""

from pathlib import Path

import pytest

from app.chunk_service import (
    parse_transcript_into_partie_blocks,
    create_project_chunks,
    is_real_transcript_content,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SEP = "=" * 80


def _partie_header(n: int, title: str) -> str:
    return f"{SEP}\nPARTIE {n} — {title}\n{SEP}"


class _FakeProject:
    """Objet projet minimal attendu par create_project_chunks."""

    def __init__(self, tmp_path: Path, transcript_text: str):
        self.name = "test_partie_project"
        self.output_dir = tmp_path / "sortie" / self.name
        self.merged_dir = self.output_dir / "merged"

        self.merged_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "chunks").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "processed").mkdir(parents=True, exist_ok=True)

        transcript = self.merged_dir / "transcript_complet.txt"
        transcript.write_text(transcript_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests : is_real_transcript_content
# ---------------------------------------------------------------------------

class TestIsRealTranscriptContent:

    def test_empty_string(self):
        assert is_real_transcript_content("") is False

    def test_whitespace_only(self):
        assert is_real_transcript_content("   \n  \n  ") is False

    def test_separator_lines_only(self):
        assert is_real_transcript_content(SEP + "\n" + SEP) is False

    def test_partie_header_alone(self):
        text = f"{SEP}\nPARTIE 1 — Pastoral Retreat 1\n{SEP}"
        assert is_real_transcript_content(text) is False

    def test_partie_title_line_alone(self):
        assert is_real_transcript_content("PARTIE 3 — Pastoral Retreat 3") is False

    def test_timestamps_without_text(self):
        text = "[00:00:00]\n[00:01:00]\n[00:02:00 -> 00:02:30]"
        assert is_real_transcript_content(text) is False

    def test_metadata_lines_only(self):
        text = (
            "# Projet : test\n"
            "# Partie source : PARTIE 1 — Retreat 1\n"
            "# Chunk : 001"
        )
        assert is_real_transcript_content(text) is False

    def test_real_transcript_line(self):
        text = "[00:00:00] Bonjour à tous, bienvenue à cette retraite pastorale."
        assert is_real_transcript_content(text) is True

    def test_real_text_without_timestamp(self):
        text = "Bonjour à tous, bienvenue à cette retraite pastorale."
        assert is_real_transcript_content(text) is True

    def test_partie_header_then_real_content(self):
        text = (
            "PARTIE 1 — Retreat 1\n\n"
            "[00:00:00] Bienvenue à cette retraite."
        )
        assert is_real_transcript_content(text) is True

    def test_metadata_then_real_content(self):
        text = (
            "# Partie source : PARTIE 1 — Retreat 1\n\n"
            "[00:00:00] Bonjour à tous."
        )
        assert is_real_transcript_content(text) is True

    def test_punctuation_only(self):
        assert is_real_transcript_content("... --- ===") is False

    def test_single_letter_not_enough(self):
        # Moins de 2 lettres → False
        assert is_real_transcript_content("[00:00:00] A") is False


# ---------------------------------------------------------------------------
# Tests : _parse_transcript_into_partie_blocks
# ---------------------------------------------------------------------------

class TestParseTranscriptIntoPartieBlocks:

    def test_no_partie_headers_returns_single_block(self):
        text = "[00:00:00] Hello everyone.\n\n[00:01:00] More content here."
        blocks = parse_transcript_into_partie_blocks(text)
        assert len(blocks) == 1
        assert blocks[0]["partie"] is None
        assert "Hello everyone" in blocks[0]["content"]

    def test_partie_header_only_returns_empty_content(self):
        text = f"{SEP}\nPARTIE 1 — Pastoral Retreat 1\n{SEP}"
        blocks = parse_transcript_into_partie_blocks(text)
        assert len(blocks) == 1
        assert blocks[0]["partie"] == "PARTIE 1 — Pastoral Retreat 1"
        assert blocks[0]["content"] == ""

    def test_partie_header_with_content(self):
        text = (
            f"{SEP}\nPARTIE 1 — Pastoral Retreat 1\n{SEP}\n\n"
            "[00:00:00] Hello everyone."
        )
        blocks = parse_transcript_into_partie_blocks(text)
        assert len(blocks) == 1
        assert blocks[0]["partie"] == "PARTIE 1 — Pastoral Retreat 1"
        assert "Hello everyone" in blocks[0]["content"]

    def test_multiple_parties(self):
        text = (
            f"{SEP}\nPARTIE 1 — Retreat 1\n{SEP}\n\n"
            "[00:00:00] Content 1.\n\n"
            f"{SEP}\nPARTIE 2 — Retreat 2\n{SEP}\n\n"
            "[00:01:00] Content 2."
        )
        blocks = parse_transcript_into_partie_blocks(text)
        assert len(blocks) == 2
        assert blocks[0]["partie"] == "PARTIE 1 — Retreat 1"
        assert "Content 1" in blocks[0]["content"]
        assert blocks[1]["partie"] == "PARTIE 2 — Retreat 2"
        assert "Content 2" in blocks[1]["content"]

    def test_pre_partie_content_is_preserved(self):
        """Contenu avant le premier en-tête PARTIE doit être conservé."""
        text = (
            "[00:00:00] Intro before any PARTIE.\n\n"
            f"{SEP}\nPARTIE 1 — Retreat 1\n{SEP}\n\n"
            "[00:01:00] Content 1."
        )
        blocks = parse_transcript_into_partie_blocks(text)
        assert len(blocks) == 2
        assert blocks[0]["partie"] is None
        assert "Intro before" in blocks[0]["content"]
        assert blocks[1]["partie"] == "PARTIE 1 — Retreat 1"


# ---------------------------------------------------------------------------
# Tests d'intégration : create_project_chunks
# ---------------------------------------------------------------------------

class TestCreateProjectChunksWithPartie:

    def test_header_only_creates_no_chunks(self, tmp_path):
        """
        Cas du critère de succès (test 1) :
        Un transcript contenant uniquement un en-tête PARTIE ne doit créer
        aucun chunk.
        """
        transcript = f"{SEP}\nPARTIE 1 — Pastoral Retreat 1\n{SEP}\n"
        project = _FakeProject(tmp_path, transcript)

        results = create_project_chunks(project)

        assert len(results) == 0, (
            "Un transcript avec uniquement un en-tête PARTIE ne doit créer aucun chunk."
        )
        chunks_dir = project.output_dir / "chunks"
        chunk_files = list(chunks_dir.glob("chunk_*.txt"))
        assert len(chunk_files) == 0, (
            "Aucun fichier chunk ne doit exister sur disque."
        )

    def test_header_with_real_content_creates_chunk_with_partie_context(self, tmp_path):
        """
        Cas du critère de succès (test 2) :
        Un transcript avec un en-tête PARTIE suivi de vrai texte doit créer
        un chunk contenant le titre de partie comme contexte + le texte réel.
        """
        transcript = (
            f"{SEP}\nPARTIE 1 — Pastoral Retreat 1\n{SEP}\n\n"
            "[00:00:00 -> 00:00:10] Bonjour à tous, bienvenue à cette retraite pastorale.\n"
            "[00:00:10 -> 00:00:20] Nous allons commencer par une prière.\n"
        )
        project = _FakeProject(tmp_path, transcript)

        results = create_project_chunks(project)

        assert len(results) >= 1, (
            "Un transcript avec du vrai contenu doit créer au moins un chunk."
        )

        first_chunk_text = results[0]["path"].read_text(encoding="utf-8")

        assert "PARTIE 1 — Pastoral Retreat 1" in first_chunk_text, (
            "Le chunk doit contenir la référence à la PARTIE source."
        )
        assert "Bonjour à tous" in first_chunk_text, (
            "Le chunk doit contenir le vrai texte transcrit."
        )
        assert is_real_transcript_content(first_chunk_text), (
            "Le chunk créé doit être reconnu comme contenant du vrai contenu."
        )

    def test_multiple_headers_only_creates_no_chunks(self, tmp_path):
        """Plusieurs en-têtes PARTIE sans contenu réel → aucun chunk."""
        transcript = (
            f"{SEP}\nPARTIE 1 — Pastoral Retreat 1\n{SEP}\n\n"
            f"{SEP}\nPARTIE 2 — Pastoral Retreat 2\n{SEP}\n"
        )
        project = _FakeProject(tmp_path, transcript)

        results = create_project_chunks(project)

        assert len(results) == 0, (
            "Des en-têtes PARTIE sans contenu réel ne doivent créer aucun chunk."
        )

    def test_mixed_empty_and_real_parties(self, tmp_path):
        """
        PARTIE 1 vide + PARTIE 2 avec contenu → seul un chunk pour PARTIE 2,
        portant le bon contexte.
        """
        transcript = (
            f"{SEP}\nPARTIE 1 — Pastoral Retreat 1\n{SEP}\n\n"
            f"{SEP}\nPARTIE 2 — Pastoral Retreat 2\n{SEP}\n\n"
            "[00:00:00 -> 00:00:15] Voici le contenu réel de la partie 2.\n"
            "[00:00:15 -> 00:00:30] Il contient du vrai texte transcrit.\n"
        )
        project = _FakeProject(tmp_path, transcript)

        results = create_project_chunks(project)

        assert len(results) >= 1

        chunk_text = results[0]["path"].read_text(encoding="utf-8")
        assert "PARTIE 2 — Pastoral Retreat 2" in chunk_text
        assert "contenu réel" in chunk_text
        assert "PARTIE 1" not in chunk_text, (
            "Le chunk de PARTIE 2 ne doit pas mentionner PARTIE 1."
        )

    def test_chunk_file_name_is_sequential(self, tmp_path):
        """Les chunks sont numérotés séquentiellement à partir de 001."""
        transcript = (
            f"{SEP}\nPARTIE 1 — Pastoral Retreat 1\n{SEP}\n\n"
            "[00:00:00 -> 00:00:10] Texte réel de la partie 1.\n"
            f"{SEP}\nPARTIE 2 — Pastoral Retreat 2\n{SEP}\n\n"
            "[00:01:00 -> 00:01:10] Texte réel de la partie 2.\n"
        )
        project = _FakeProject(tmp_path, transcript)

        results = create_project_chunks(project)

        names = [r["name"] for r in results]
        assert names[0] == "chunk_001.txt"
        if len(names) > 1:
            assert names[1] == "chunk_002.txt"
