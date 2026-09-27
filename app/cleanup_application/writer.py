"""
Publication atomique des trois sorties de la Phase 3A.2B.

    transcripts/clean/transcript_data.json
    transcripts/clean/transcript.txt
    audit/cleanup_application.json

Transaction logique :

1. sérialiser les trois contenus en mémoire ;
2. écrire trois fichiers .partial dans leurs répertoires finaux ;
3. valider les octets partiels ;
4. Path.replace() de chacun.

Si une écriture .partial échoue : tous les .partial sont supprimés, aucun
fichier final n'est créé/remplacé. Un run précédent valide survit.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.cleanup_application.errors import ApplicationValidationError
from app.file_utils import write_text_atomic
from app.paths import SORTIE_DIR
from app.semantic_batch.writer import audit_dir as _audit_dir
from app.source_analysis.writer import transcripts_dir as _transcripts_dir

CLEAN_DIR_NAME = "clean"
CLEAN_JSON_NAME = "transcript_data.json"
CLEAN_TXT_NAME = "transcript.txt"
AUDIT_NAME = "cleanup_application.json"


def dumps_canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def sha256_of_text(content: str) -> str:
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def clean_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return _transcripts_dir(project_name, sortie_dir=sortie_dir) / CLEAN_DIR_NAME


def clean_json_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return clean_dir(project_name, sortie_dir=sortie_dir) / CLEAN_JSON_NAME


def clean_txt_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return clean_dir(project_name, sortie_dir=sortie_dir) / CLEAN_TXT_NAME


def audit_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return _audit_dir(project_name, sortie_dir=sortie_dir) / AUDIT_NAME


def output_paths(project_name: str, *, sortie_dir: Path | None = None) -> dict[str, Path]:
    return {
        "clean_json": clean_json_path(project_name, sortie_dir=sortie_dir),
        "clean_txt": clean_txt_path(project_name, sortie_dir=sortie_dir),
        "audit": audit_path(project_name, sortie_dir=sortie_dir),
    }


def _partial(path: Path) -> Path:
    return path.with_name(path.name + ".partial")


def _cleanup_partials(paths: list[Path]) -> None:
    for path in paths:
        _partial(path).unlink(missing_ok=True)


def publish_outputs(
    *,
    project_name: str,
    clean_json_payload: dict,
    clean_txt: str,
    audit_payload: dict,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    """
    Écrit les trois artefacts via .partial puis replace. Lève
    ApplicationValidationError / OSError sans laisser de .partial.
    """
    paths = output_paths(project_name, sortie_dir=sortie_dir)
    ordered = [paths["clean_json"], paths["clean_txt"], paths["audit"]]
    contents = {
        paths["clean_json"]: dumps_canonical(clean_json_payload),
        paths["clean_txt"]: clean_txt,
        paths["audit"]: dumps_canonical(audit_payload),
    }

    for path in ordered:
        path.parent.mkdir(parents=True, exist_ok=True)

    written_partials: list[Path] = []
    try:
        for path in ordered:
            partial = _partial(path)
            # write_bytes : pas de traduction Windows \n -> \r\n, afin que le
            # SHA-256 en mémoire soit celui des octets publiés.
            partial.write_bytes(contents[path].encode("utf-8"))
            written_partials.append(partial)

        for path in ordered:
            on_disk = _partial(path).read_bytes().decode("utf-8")
            if on_disk != contents[path]:
                raise ApplicationValidationError(
                    f"Octets partiels ≠ contenu canonique pour {path.name}."
                )

        for path in ordered:
            _partial(path).replace(path)
            written_partials = [p for p in written_partials if p != _partial(path)]
    except BaseException:
        _cleanup_partials(ordered)
        raise

    leftover = [_partial(path) for path in ordered if _partial(path).exists()]
    if leftover:
        raise ApplicationValidationError(
            f"Fichier(s) .partial restant(s) après publication : {leftover}"
        )

    return paths


def write_text_atomic_if_needed(path: Path, content: str) -> Path:
    """Exposé pour les tests d'échec d'écriture atomique unitaire."""
    return write_text_atomic(path, content)


def default_sortie() -> Path:
    return SORTIE_DIR
