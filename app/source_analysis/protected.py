"""
Sources protégées de la Phase 3B — snapshot SHA-256 octet à octet.

Ces fichiers sont des artefacts déjà validés (transcript original, clean,
audits 3A). Le Source Analyzer les LIT ; il ne doit en changer aucun octet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.cleanup_application.writer import audit_path, clean_json_path, clean_txt_path
from app.cleanup_policy.writer import artifact_path as cleanup_policy_path
from app.language_blocks.writer import manifest_path as language_blocks_path
from app.language_cleanup.writer import manifest_path as language_cleanup_path
from app.semantic_batch.writer import classification_artifact_path
from app.semantic_canary.integrity import sha256_of_file
from app.semantic_canary.writer import artifact_path as semantic_canary_path
from app.source_analysis.preflight import PREFLIGHT_ARTIFACT_NAME
from app.source_analysis.writer import transcripts_dir
from app.language_cleanup.transcript_source import audit_dir

TRANSCRIPT_DATA = "transcripts/transcript_data.json"
TRANSCRIPT_TXT = "transcripts/transcript.txt"
CLEAN_DATA = "transcripts/clean/transcript_data.json"
CLEAN_TXT = "transcripts/clean/transcript.txt"
LANGUAGE_CLEANUP = "audit/language_cleanup.json"
LANGUAGE_BLOCKS = "audit/language_blocks.json"
SEMANTIC_CANARY = "audit/semantic_translation_canary.json"
SEMANTIC_CLASSIFICATION = "audit/semantic_translation_classification.json"
CLEANUP_POLICY = "audit/cleanup_policy_simulation.json"
CLEANUP_APPLICATION = "audit/cleanup_application.json"
PREFLIGHT = "audit/source_analyzer_clean_preflight.json"

PROTECTED_KEYS = (
    TRANSCRIPT_DATA,
    TRANSCRIPT_TXT,
    CLEAN_DATA,
    CLEAN_TXT,
    LANGUAGE_CLEANUP,
    LANGUAGE_BLOCKS,
    SEMANTIC_CANARY,
    SEMANTIC_CLASSIFICATION,
    CLEANUP_POLICY,
    CLEANUP_APPLICATION,
    PREFLIGHT,
)


def protected_paths(project_name: str, *, sortie_dir: Path | None = None) -> dict[str, Path]:
    """Chemins canoniques des sources protégées, par clé stable."""
    original_dir = transcripts_dir(project_name, sortie_dir=sortie_dir)

    return {
        TRANSCRIPT_DATA: original_dir / "transcript_data.json",
        TRANSCRIPT_TXT: original_dir / "transcript.txt",
        CLEAN_DATA: clean_json_path(project_name, sortie_dir=sortie_dir),
        CLEAN_TXT: clean_txt_path(project_name, sortie_dir=sortie_dir),
        LANGUAGE_CLEANUP: language_cleanup_path(project_name, sortie_dir=sortie_dir),
        LANGUAGE_BLOCKS: language_blocks_path(project_name, sortie_dir=sortie_dir),
        SEMANTIC_CANARY: semantic_canary_path(project_name, sortie_dir=sortie_dir),
        SEMANTIC_CLASSIFICATION: classification_artifact_path(
            project_name, sortie_dir=sortie_dir
        ),
        CLEANUP_POLICY: cleanup_policy_path(project_name, sortie_dir=sortie_dir),
        CLEANUP_APPLICATION: audit_path(project_name, sortie_dir=sortie_dir),
        PREFLIGHT: audit_dir(project_name, sortie_dir=sortie_dir)
        / PREFLIGHT_ARTIFACT_NAME,
    }


@dataclass(frozen=True)
class ProtectedSnapshot:
    hashes: dict[str, str]

    def to_dict(self) -> dict[str, str]:
        return dict(self.hashes)


def snapshot_protected(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    require_all: bool = True,
) -> ProtectedSnapshot:
    """
    SHA-256 des octets bruts de chaque source protégée.

    `require_all=True` (défaut de l'exécution réelle) : un fichier manquant
    est une erreur, pas un oubli silencieux.
    """
    paths = protected_paths(project_name, sortie_dir=sortie_dir)
    hashes: dict[str, str] = {}
    missing: list[str] = []

    for key, path in paths.items():
        if not Path(path).is_file():
            missing.append(key)
            continue
        hashes[key] = sha256_of_file(path)

    if require_all and missing:
        raise FileNotFoundError(
            "Source(s) protégée(s) absente(s) : " + ", ".join(missing)
        )

    return ProtectedSnapshot(hashes=hashes)


def compare_protected(
    before: ProtectedSnapshot,
    after: ProtectedSnapshot,
) -> list[str]:
    """Clés dont le SHA a changé, ou qui ont disparu / apparu."""
    violations: list[str] = []
    keys = set(before.hashes) | set(after.hashes)

    for key in sorted(keys):
        left = before.hashes.get(key)
        right = after.hashes.get(key)
        if left != right:
            violations.append(key)

    return violations
