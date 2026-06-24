"""
Tests d'idempotence du service de chunking.

Vérifie que :
- Cas 1 : Premier lancement → tous les chunks sont "created".
- Cas 2 : Deuxième lancement sans changement → tous "unchanged", timestamps intacts.
- Les fichiers processed/ existants ne sont pas supprimés si le chunk est inchangé.
- Cas 3 : Modification d'un seul passage du transcript → seul le chunk concerné
  est "updated", son processed/ est supprimé, les autres restent "unchanged".
- Cas 4 : Suppression d'une partie du transcript → chunks obsolètes déplacés
  vers chunks/obsolete/ et processed/obsolete/.
- Cas 5 : Transcript contenant uniquement un en-tête PARTIE → aucun chunk généré.
- force_regenerate_chunks=True force tous les chunks à "updated"/"created".
- Les nouveaux champs (partie_source, char_count, word_count, updated_at) sont présents.
"""

import hashlib
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.chunk_service import create_project_chunks, split_text_into_chunks
from app.file_utils import content_hash
from app.project_state import update_chunk_state


# ---------------------------------------------------------------------------
# Fixture : projet factice en répertoire temporaire
# ---------------------------------------------------------------------------

class _FakeProject:
    """Objet projet minimal attendu par create_project_chunks."""

    def __init__(self, tmp_path: Path, transcript_text: str):
        self.name       = "test_project"
        self.output_dir = tmp_path / "sortie" / self.name
        self.merged_dir = self.output_dir / "merged"

        self.merged_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "chunks").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "processed").mkdir(parents=True, exist_ok=True)

        transcript = self.merged_dir / "transcript_complet.txt"
        transcript.write_text(transcript_text, encoding="utf-8")


def _make_long_transcript(n_paragraphs: int = 20, chars_per_para: int = 600) -> str:
    """Génère un transcript assez long pour produire plusieurs chunks."""
    paragraphs = []
    for i in range(n_paragraphs):
        para = f"[00:{i:02d}:00] " + (
            f"Paragraphe {i + 1}. " * (chars_per_para // 14)
        )
        paragraphs.append(para.strip())
    return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChunkingIdempotency:

    def test_first_run_creates_all_chunks(self, tmp_path):
        """Premier lancement : tous les chunks sont marqués 'created'."""
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        results = create_project_chunks(project, max_chars=2000)

        assert len(results) > 1, "Le transcript devrait produire plusieurs chunks."
        for r in results:
            assert r["generation_status"] == "created", (
                f"{r['name']} devrait être 'created' au premier lancement."
            )
            assert r["needs_ai_processing"] is True
            assert r["path"].exists()
            assert len(r["hash"]) == 64  # SHA256 hex

    def test_second_run_unchanged(self, tmp_path):
        """
        Second lancement sans changement :
        - generation_status == 'unchanged' pour tous les chunks
        - timestamps des fichiers inchangés (aucune réécriture)
        - needs_ai_processing == True car aucun fichier processed/ n'existe
          (un chunk inchangé mais sans processed doit être retraité par l'IA)
        """
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        create_project_chunks(project, max_chars=2000)

        chunks_dir = project.output_dir / "chunks"
        mtimes_before = {
            f.name: f.stat().st_mtime
            for f in chunks_dir.glob("chunk_*.txt")
        }

        time.sleep(1.1)

        results = create_project_chunks(project, max_chars=2000)

        for r in results:
            assert r["generation_status"] == "unchanged", (
                f"{r['name']} devrait être 'unchanged'."
            )
            # Sans processed/, le chunk doit quand même être signalé à l'IA
            assert r["needs_ai_processing"] is True, (
                f"{r['name']} : unchanged sans processed/ → needs_ai doit être True."
            )

        # Les fichiers chunk ne doivent pas avoir été réécrits
        for name, mtime_before in mtimes_before.items():
            mtime_after = (chunks_dir / name).stat().st_mtime
            assert mtime_after == mtime_before, (
                f"{name} a été réécrit alors que le contenu n'a pas changé."
            )

    def test_second_run_unchanged_with_processed(self, tmp_path):
        """
        Second lancement sans changement ET avec processed/ présents :
        - generation_status == 'unchanged'
        - needs_ai_processing == False (le processed existe déjà)
        """
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        results_1 = create_project_chunks(project, max_chars=2000)

        # Simuler processed/ pour tous les chunks
        processed_dir = project.output_dir / "processed"
        for r in results_1:
            md = processed_dir / r["name"].replace(".txt", ".md")
            md.write_text(f"# IA {r['name']}", encoding="utf-8")

        results_2 = create_project_chunks(project, max_chars=2000)

        for r in results_2:
            assert r["generation_status"] == "unchanged"
            assert r["needs_ai_processing"] is False, (
                f"{r['name']} : unchanged avec processed/ → needs_ai doit être False."
            )

    def test_processed_files_preserved_when_unchanged(self, tmp_path):
        """Les fichiers processed/ existants ne sont pas supprimés si le chunk est inchangé."""
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        results_1 = create_project_chunks(project, max_chars=2000)

        # Simuler l'existence de fichiers processed/
        processed_dir = project.output_dir / "processed"
        for r in results_1:
            md_path = processed_dir / r["name"].replace(".txt", ".md")
            md_path.write_text(f"# Résultat IA pour {r['name']}\n", encoding="utf-8")

        results_2 = create_project_chunks(project, max_chars=2000)

        for r in results_2:
            assert r["generation_status"] == "unchanged"
            md_path = processed_dir / r["name"].replace(".txt", ".md")
            assert md_path.exists(), (
                f"{md_path.name} a été supprimé alors que le chunk est inchangé."
            )

    def test_modified_chunk_becomes_updated(self, tmp_path):
        """
        Après corruption d'un seul fichier chunk sur disque
        (simule une modification ciblée du transcript qui n'affecte que ce chunk) :
        - ce chunk est détecté 'updated'
        - son processed/ est supprimé
        - les autres chunks restent 'unchanged' et leurs processed/ sont préservés
        """
        text    = _make_long_transcript(n_paragraphs=30, chars_per_para=600)
        project = _FakeProject(tmp_path, text)

        results_1 = create_project_chunks(project, max_chars=2000)
        assert len(results_1) >= 3, "Le transcript devrait produire ≥ 3 chunks."

        # Simuler processed/ pour tous les chunks
        processed_dir = project.output_dir / "processed"
        for r in results_1:
            md = processed_dir / r["name"].replace(".txt", ".md")
            md.write_text(f"# IA {r['name']}", encoding="utf-8")

        # Corrompre manuellement le deuxième chunk sur disque
        # (simule une modification du transcript qui affecterait uniquement ce chunk)
        target_chunk = results_1[1]  # chunk_002.txt
        target_chunk["path"].write_text(
            target_chunk["path"].read_text(encoding="utf-8") + "\n[MODIFICATION]",
            encoding="utf-8",
        )

        # Relancer la génération depuis le même transcript (inchangé)
        results_2 = create_project_chunks(project, max_chars=2000)

        statuses = {r["name"]: r["generation_status"] for r in results_2}

        # chunk_002 doit être 'updated' (son contenu sur disque diffère)
        assert statuses[target_chunk["name"]] == "updated", (
            f"{target_chunk['name']} devrait être 'updated'."
        )

        # Tous les autres doivent être 'unchanged'
        for r in results_2:
            if r["name"] == target_chunk["name"]:
                continue
            assert r["generation_status"] == "unchanged", (
                f"{r['name']} devrait rester 'unchanged'."
            )

        # Le processed/ du chunk modifié est supprimé
        md_updated = processed_dir / target_chunk["name"].replace(".txt", ".md")
        assert not md_updated.exists(), (
            f"{md_updated.name} devrait être supprimé car le chunk est 'updated'."
        )

        # Les processed/ des autres chunks sont préservés
        for r in results_2:
            if r["name"] == target_chunk["name"]:
                continue
            md = processed_dir / r["name"].replace(".txt", ".md")
            assert md.exists(), (
                f"{md.name} a été supprimé alors que le chunk est 'unchanged'."
            )

    def test_force_regenerate_rewrites_all(self, tmp_path):
        """force_regenerate_chunks=True force tous les chunks à updated/created."""
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        create_project_chunks(project, max_chars=2000)

        results = create_project_chunks(
            project, max_chars=2000, force_regenerate_chunks=True
        )

        for r in results:
            assert r["generation_status"] in ("created", "updated"), (
                f"{r['name']} devrait être updated avec force_regenerate_chunks=True."
            )
            assert r["needs_ai_processing"] is True

    def test_obsolete_chunks_moved_not_deleted(self, tmp_path):
        """
        Quand le transcript raccourcit, les anciens chunks sont déplacés
        vers chunks/obsolete/, pas supprimés.
        """
        long_text = _make_long_transcript(n_paragraphs=40, chars_per_para=600)
        project   = _FakeProject(tmp_path, long_text)

        results_long = create_project_chunks(project, max_chars=2000)
        long_names   = {r["name"] for r in results_long}

        # Simuler processed/ pour tous
        processed_dir = project.output_dir / "processed"
        for r in results_long:
            md = processed_dir / r["name"].replace(".txt", ".md")
            md.write_text(f"# IA {r['name']}", encoding="utf-8")

        # Réduire drastiquement le transcript
        short_text = _make_long_transcript(n_paragraphs=5, chars_per_para=600)
        (project.merged_dir / "transcript_complet.txt").write_text(
            short_text, encoding="utf-8"
        )

        results_short = create_project_chunks(project, max_chars=2000)
        short_names   = {r["name"] for r in results_short}

        obsolete_names = long_names - short_names
        assert len(obsolete_names) > 0, "Il devrait y avoir des chunks obsolètes."

        obsolete_dir           = project.output_dir / "chunks" / "obsolete"
        obsolete_processed_dir = project.output_dir / "processed" / "obsolete"

        for name in obsolete_names:
            # Chunk déplacé dans obsolete/, pas supprimé
            assert (obsolete_dir / name).exists(), (
                f"{name} devrait être dans chunks/obsolete/."
            )
            # processed/ déplacé dans processed/obsolete/
            md_name = name.replace(".txt", ".md")
            assert (obsolete_processed_dir / md_name).exists(), (
                f"{md_name} devrait être dans processed/obsolete/."
            )

    def test_content_hash_sha256(self, tmp_path):
        """Le hash retourné est un SHA256 valide sur le contenu du chunk."""
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        results = create_project_chunks(project, max_chars=2000)

        for r in results:
            raw_text    = r["path"].read_text(encoding="utf-8")
            expected    = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            assert r["hash"] == expected, (
                f"Hash incorrect pour {r['name']}."
            )

    def test_result_dict_contains_all_metadata_fields(self, tmp_path):
        """
        Chaque entrée du résultat doit contenir tous les champs de métadonnées
        définis par la spec : path, name, hash, generation_status,
        needs_ai_processing, partie_source, char_count, word_count, updated_at.
        """
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        results = create_project_chunks(project, max_chars=2000)

        required_fields = {
            "path", "name", "hash", "generation_status",
            "needs_ai_processing", "partie_source",
            "char_count", "word_count", "updated_at",
        }
        for r in results:
            missing = required_fields - r.keys()
            assert not missing, (
                f"{r['name']} manque les champs : {missing}"
            )
            assert isinstance(r["char_count"], int) and r["char_count"] > 0
            assert isinstance(r["word_count"], int) and r["word_count"] > 0
            assert isinstance(r["updated_at"], str) and "T" in r["updated_at"]

    def test_unchanged_without_processed_requires_ai(self, tmp_path):
        """
        Cas : chunk 'unchanged' mais fichier processed/ absent
        → needs_ai_processing doit être True (le processed a été supprimé manuellement
          ou n'a jamais été produit par l'IA).
        """
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        # Premier lancement : tous created
        results_1 = create_project_chunks(project, max_chars=2000)
        assert all(r["generation_status"] == "created" for r in results_1)
        assert all(r["needs_ai_processing"] is True for r in results_1)

        # Deuxième lancement sans processed/ → unchanged mais needs_ai=True
        results_2 = create_project_chunks(project, max_chars=2000)
        for r in results_2:
            assert r["generation_status"] == "unchanged"
            assert r["needs_ai_processing"] is True, (
                f"{r['name']} : unchanged sans processed → needs_ai_processing devrait être True."
            )

        # Simuler processed/ pour tous les chunks
        processed_dir = project.output_dir / "processed"
        for r in results_2:
            md = processed_dir / r["name"].replace(".txt", ".md")
            md.write_text(f"# IA {r['name']}", encoding="utf-8")

        # Troisième lancement avec processed/ présent → needs_ai=False
        results_3 = create_project_chunks(project, max_chars=2000)
        for r in results_3:
            assert r["generation_status"] == "unchanged"
            assert r["needs_ai_processing"] is False, (
                f"{r['name']} : unchanged avec processed → needs_ai_processing devrait être False."
            )

    def test_processed_path_present_in_result(self, tmp_path):
        """
        processed_path doit être renseigné si processed/ existe,
        sinon None.
        """
        text    = _make_long_transcript()
        project = _FakeProject(tmp_path, text)

        results_1 = create_project_chunks(project, max_chars=2000)
        for r in results_1:
            assert r["processed_path"] is None, (
                f"{r['name']} : processed_path devrait être None (pas encore traité)."
            )

        # Créer les processed/
        processed_dir = project.output_dir / "processed"
        for r in results_1:
            md = processed_dir / r["name"].replace(".txt", ".md")
            md.write_text(f"# IA", encoding="utf-8")

        results_2 = create_project_chunks(project, max_chars=2000)
        for r in results_2:
            assert r["processed_path"] is not None, (
                f"{r['name']} : processed_path devrait pointer vers le fichier .md."
            )
            assert r["processed_path"].endswith(".md")

    def test_update_chunk_state_uses_pending_ai(self, tmp_path):
        """
        update_chunk_state doit stocker status='pending_ai' pour les chunks
        qui nécessitent un traitement IA, et 'done' pour les inchangés avec processed.
        """
        state: dict = {"chunks": {}}

        # Chunk créé → pending_ai
        update_chunk_state(
            state, "chunk_001.txt", "abc123", "created", True,
            path="/tmp/chunk_001.txt",
        )
        assert state["chunks"]["chunk_001.txt"]["status"] == "pending_ai"

        # Chunk inchangé sans processed → pending_ai
        update_chunk_state(
            state, "chunk_002.txt", "def456", "unchanged", True,
            path="/tmp/chunk_002.txt",
            processed_path=None,
        )
        assert state["chunks"]["chunk_002.txt"]["status"] == "pending_ai"

        # Chunk inchangé avec processed → done
        update_chunk_state(
            state, "chunk_003.txt", "ghi789", "unchanged", False,
            path="/tmp/chunk_003.txt",
            processed_path="/tmp/processed/chunk_003.md",
        )
        assert state["chunks"]["chunk_003.txt"]["status"] == "done"
        assert state["chunks"]["chunk_003.txt"]["processed_path"] == "/tmp/processed/chunk_003.md"

    def test_cas3_transcript_modification_updates_only_affected_chunks(self, tmp_path):
        """
        Cas 3 (spec PHASE 7) :
        La modification d'un seul passage du transcript ne doit déclencher
        que la régénération des chunks issus de ce passage.
        Tous les autres chunks doivent rester 'unchanged' et leurs
        fichiers processed/ doivent être préservés.

        Architecture du transcript :
            PARTIE 1 — Session 1  →  chunk_001 … chunk_N   (inchangée)
            PARTIE 2 — Session 2  →  chunk_N+1 … chunk_M   (modifiée)
        """
        SEP = "=" * 80

        def _partie_content(label: str, n_paragraphs: int = 8) -> str:
            return "\n\n".join(
                f"[00:{i:02d}:00] " + f"Texte {label}. " * 30
                for i in range(n_paragraphs)
            )

        partie1 = _partie_content("stable-P1")
        partie2 = _partie_content("stable-P2")

        transcript_v1 = (
            f"{SEP}\nPARTIE 1 — Session 1\n{SEP}\n\n{partie1}\n\n"
            f"{SEP}\nPARTIE 2 — Session 2\n{SEP}\n\n{partie2}"
        )
        project = _FakeProject(tmp_path, transcript_v1)

        results_v1 = create_project_chunks(project, max_chars=2000)
        assert len(results_v1) >= 2, "Le transcript doit produire au moins 2 chunks."

        # Vérifier que les deux parties produisent bien des chunks
        p1_names = {r["name"] for r in results_v1 if r["partie_source"] == "PARTIE 1 — Session 1"}
        p2_names = {r["name"] for r in results_v1 if r["partie_source"] == "PARTIE 2 — Session 2"}
        assert p1_names, "PARTIE 1 doit avoir au moins un chunk."
        assert p2_names, "PARTIE 2 doit avoir au moins un chunk."

        # Simuler les fichiers processed/ pour tous les chunks
        processed_dir = project.output_dir / "processed"
        for r in results_v1:
            md = processed_dir / r["name"].replace(".txt", ".md")
            md.write_text(f"# IA {r['name']}", encoding="utf-8")

        # Modifier uniquement PARTIE 2 (même nombre de paragraphes, contenu différent)
        partie2_modified = _partie_content("MODIFIÉ-P2")
        transcript_v2 = (
            f"{SEP}\nPARTIE 1 — Session 1\n{SEP}\n\n{partie1}\n\n"
            f"{SEP}\nPARTIE 2 — Session 2\n{SEP}\n\n{partie2_modified}"
        )
        (project.merged_dir / "transcript_complet.txt").write_text(
            transcript_v2, encoding="utf-8"
        )

        results_v2 = create_project_chunks(project, max_chars=2000)
        statuses = {r["name"]: r["generation_status"] for r in results_v2}

        p1_names_v2 = {r["name"] for r in results_v2 if r["partie_source"] == "PARTIE 1 — Session 1"}
        p2_names_v2 = {r["name"] for r in results_v2 if r["partie_source"] == "PARTIE 2 — Session 2"}

        # PARTIE 1 : tous les chunks doivent rester 'unchanged'
        for name in p1_names_v2:
            assert statuses[name] == "unchanged", (
                f"{name} (PARTIE 1, inchangée) devrait être 'unchanged'."
            )

        # PARTIE 2 : tous les chunks doivent devenir 'updated'
        for name in p2_names_v2:
            assert statuses[name] == "updated", (
                f"{name} (PARTIE 2, modifiée) devrait être 'updated'."
            )

        # processed/ de PARTIE 1 : préservés
        for name in p1_names_v2:
            md = processed_dir / name.replace(".txt", ".md")
            assert md.exists(), (
                f"{md.name} a été supprimé alors que PARTIE 1 est inchangée."
            )

        # processed/ de PARTIE 2 : supprimés (chunk modifié → invalidation IA)
        for name in p2_names_v2:
            md = processed_dir / name.replace(".txt", ".md")
            assert not md.exists(), (
                f"{md.name} devrait être supprimé car PARTIE 2 a été modifiée."
            )


# ---------------------------------------------------------------------------
# Tests CLI : python -m app.chunk_service <project>
# ---------------------------------------------------------------------------

class TestChunkServiceCLI:

    def _setup_project(self, tmp_path: Path) -> tuple[Path, str]:
        """Crée une arborescence de projet minimale et retourne (output_dir, project_name)."""
        project_name = "test_cli_project"
        output_dir = tmp_path / "sortie" / project_name
        merged_dir = output_dir / "merged"
        merged_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "chunks").mkdir(parents=True, exist_ok=True)
        (output_dir / "processed").mkdir(parents=True, exist_ok=True)

        transcript = merged_dir / "transcript_complet.txt"
        transcript.write_text(_make_long_transcript(), encoding="utf-8")

        return output_dir, project_name

    def test_cli_affiche_resume(self, tmp_path, monkeypatch):
        """
        python -m app.chunk_service <projet> doit terminer avec code 0
        et créer des fichiers chunk sur disque.
        """
        output_dir, project_name = self._setup_project(tmp_path)

        import app.paths as paths_module
        monkeypatch.setattr(paths_module, "SORTIE_DIR", tmp_path / "sortie")
        monkeypatch.setattr(sys, "argv", ["chunk_service", project_name])

        import runpy
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("app.chunk_service", run_name="__main__", alter_sys=True)

        assert exc_info.value.code == 0, (
            f"La CLI doit terminer avec code 0, reçu : {exc_info.value.code}"
        )

        chunks_dir = output_dir / "chunks"
        chunk_files = list(chunks_dir.glob("chunk_*.txt"))
        assert len(chunk_files) > 0, "La CLI doit créer des chunks."

    def test_cli_projet_inexistant_retourne_erreur(self, tmp_path, monkeypatch):
        """
        python -m app.chunk_service projet_inexistant doit terminer avec code 1.
        """
        import app.paths as paths_module
        monkeypatch.setattr(paths_module, "SORTIE_DIR", tmp_path / "sortie")
        monkeypatch.setattr(sys, "argv", ["chunk_service", "projet_qui_nexiste_pas"])

        import runpy
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("app.chunk_service", run_name="__main__", alter_sys=True)

        assert exc_info.value.code == 1
