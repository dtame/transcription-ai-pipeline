"""
Fixtures partagées des tests de transcription (Phase 0A) et de la couche IA
(Phase 2).

Objectifs :
- aucun accès aux projets réels (depot/, sortie/, temp/, archives/, logs/) ;
- aucun chargement de modèle Whisper ;
- aucun appel ffmpeg/ffprobe dans les tests unitaires ;
- aucun appel IA réel, aucune clé API lue depuis la machine ;
- tout est confiné dans tmp_path.

Les imports des modules de production sont faits à l'intérieur des fixtures afin
de ne pas alourdir la collecte des tests préexistants.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Isolation des écritures sur disque
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_logs(tmp_path, monkeypatch) -> None:
    """
    Redirige LOGS_DIR vers tmp_path pour TOUS les tests.

    log_event() résout LOGS_DIR dans les globales de app.logger au moment de
    l'appel : un seul patch suffit, quel que soit le module appelant. Garantit
    qu'aucun test n'appende dans logs/transcription_log.jsonl.
    """
    import app.logger as logger

    monkeypatch.setattr(logger, "LOGS_DIR", tmp_path / "logs")


# ---------------------------------------------------------------------------
# Isolation des identifiants IA
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_ai_credentials(monkeypatch) -> None:
    """
    Aucun test ne voit les clés API de la machine, ni le .env du dépôt.

    Si un développeur a réellement OPENAI_API_KEY dans son shell, la suite
    doit se comporter exactement comme sur une machine sans credentials :
    c'est la garantie qu'aucun test ne peut déclencher un appel facturé.
    """
    import app.ai.settings as ai_settings

    for variable in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(variable, raising=False)

    for variable in (
        "AI_DEFAULT_CONNECT_TIMEOUT_SECONDS",
        "AI_DEFAULT_READ_TIMEOUT_SECONDS",
        "AI_SOURCE_ANALYSIS_CONNECT_TIMEOUT_SECONDS",
        "AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS",
        "AI_EDITORIAL_PLANNING_CONNECT_TIMEOUT_SECONDS",
        "AI_EDITORIAL_PLANNING_READ_TIMEOUT_SECONDS",
        "AI_BOOK_GENERATION_CONNECT_TIMEOUT_SECONDS",
        "AI_BOOK_GENERATION_READ_TIMEOUT_SECONDS",
        "AI_BOOK_VALIDATION_CONNECT_TIMEOUT_SECONDS",
        "AI_BOOK_VALIDATION_READ_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(variable, raising=False)

    # Marque le .env comme « déjà chargé » : load_env_file() ne lira rien.
    monkeypatch.setattr(ai_settings, "_env_file_loaded", True)


@pytest.fixture
def no_ai_network(monkeypatch):
    """
    Interdit tout POST HTTP sortant de la couche IA.

    Les tests de provider qui simulent un échange réseau réinstallent leur
    propre double par-dessus ; ceux qui n'en installent pas échouent bruyamment
    plutôt que de contacter un service réel.
    """
    import app.ai.providers._http as http_module

    def _forbidden(*args, **kwargs):
        raise AssertionError(
            "Appel réseau interdit pendant les tests : "
            f"{args[0] if args else kwargs.get('url')}"
        )

    monkeypatch.setattr(http_module.requests, "post", _forbidden)


# ---------------------------------------------------------------------------
# Isolation du répertoire de sortie
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_sortie(tmp_path, monkeypatch) -> Path:
    """
    Redirige SORTIE_DIR vers tmp_path pour project_state et la segmentation.

    Garantit qu'aucun test n'écrit dans sortie/<projet réel>/.
    """
    import app.project_state as project_state
    import app.segmented_transcription_service as sts

    sortie = tmp_path / "sortie"
    sortie.mkdir(exist_ok=True)

    monkeypatch.setattr(project_state, "SORTIE_DIR", sortie)
    monkeypatch.setattr(sts, "SORTIE_DIR", sortie)

    return sortie


@pytest.fixture
def silence_logs(monkeypatch) -> None:
    """Neutralise log_event pour ne pas écrire dans logs/transcription_log.jsonl."""
    import app.pipeline_runner as pipeline_runner
    import app.segmented_transcription_service as sts
    import app.transcript_merger as transcript_merger

    for module in (sts, pipeline_runner, transcript_merger):
        monkeypatch.setattr(module, "log_event", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# Projet audio factice
# ---------------------------------------------------------------------------

@pytest.fixture
def make_audio_project(tmp_path, isolated_sortie):
    """
    Construit un AudioProject dont tous les répertoires vivent dans tmp_path.

    Le dataclass est instancié directement (sans create_project) pour éviter
    la création de répertoires sous depot/, temp/, archives/ et rejets/.
    """
    from app.project_manager import AudioProject

    def _make(name: str = "demo_project", audio_files: dict | None = None):
        audio_files = audio_files if audio_files is not None else {"lesson_01.mp3": b"aaa"}

        source_dir = tmp_path / "depot" / name
        source_dir.mkdir(parents=True, exist_ok=True)

        paths = []
        for filename, content in audio_files.items():
            audio_path = source_dir / filename
            audio_path.write_bytes(content)
            paths.append(audio_path)

        output_dir = isolated_sortie / name
        project = AudioProject(
            name=name,
            source_dir=source_dir,
            audio_files=sorted(paths),
            output_dir=output_dir,
            transcripts_dir=output_dir / "transcripts",
            merged_dir=output_dir / "merged",
            book_dir=output_dir / "book",
            pdf_dir=output_dir / "pdf",
            temp_dir=tmp_path / "temp" / name,
            archives_dir=tmp_path / "archives" / name,
            rejects_dir=tmp_path / "rejets" / name,
        )

        for directory in (
            project.output_dir,
            project.transcripts_dir,
            project.merged_dir,
            project.temp_dir,
            project.archives_dir,
            project.rejects_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        return project

    return _make


# ---------------------------------------------------------------------------
# Environnement de la transcription segmentée
# ---------------------------------------------------------------------------

class SegmentedEnv:
    """Handles d'instrumentation pour les tests de transcription segmentée."""

    def __init__(self, sortie: Path):
        self.sortie = sortie
        self.duration = 0.0
        self.saves: list[dict] = []          # snapshots de chaque save_project_state
        self.created_segments: list[tuple] = []  # (nom_fichier, start, end)

    @property
    def save_count(self) -> int:
        return len(self.saves)

    def transcribed_ids_at_save(self, index: int, audio_path: Path) -> list[str]:
        """Ids des segments marqués 'transcribed' dans le snapshot n° index."""
        key = str(audio_path.resolve())
        segments = self.saves[index].get("files", {}).get(key, {}).get("segments", {})
        return sorted(
            seg_id
            for seg_id, seg in segments.items()
            if seg.get("status") == "transcribed"
        )


@pytest.fixture
def segmented_env(monkeypatch, isolated_sortie, silence_logs) -> SegmentedEnv:
    """
    Prépare transcribe_long_audio_with_segments pour une exécution hermétique :

    - durée audio simulée (pas de ffprobe) ;
    - segments audio créés comme simples fichiers stub (pas de ffmpeg) ;
    - barre de progression neutralisée ;
    - chaque appel à save_project_state est enregistré (snapshot profond).
    """
    import app.segmented_transcription_service as sts

    env = SegmentedEnv(isolated_sortie)

    monkeypatch.setattr(sts, "get_audio_duration_seconds", lambda path: env.duration)
    monkeypatch.setattr(sts, "print_progress", lambda **kwargs: None)

    def _fake_create_audio_segment(audio_path, output_path, start, end):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-audio-segment")
        env.created_segments.append((output_path.name, start, end))

    monkeypatch.setattr(sts, "_create_audio_segment", _fake_create_audio_segment)

    real_save = sts.save_project_state

    def _spy_save(project_name, state):
        real_save(project_name, state)
        env.saves.append(copy.deepcopy(state))

    monkeypatch.setattr(sts, "save_project_state", _spy_save)

    return env
