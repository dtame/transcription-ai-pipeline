"""
Emplacement et publication atomique de source_map.json.

EMPLACEMENT

    sortie/<projet>/analysis/source_map.json

Un répertoire neuf, `analysis/`, plutôt qu'un répertoire existant. Les
répertoires V1 portent chacun une étape de la chaîne de réécriture — chunks/ le
découpage, processed/ le passage IA par chunk, reviewed/ les corrections,
final/ le document assemblé, publication/ les exports. Y ranger le Source Map
le ferait passer pour une étape de cette chaîne, alors qu'il est la première
étape d'une chaîne DIFFÉRENTE : comprendre la source avant d'en faire quoi que
ce soit. `analysis/` accueillera les artefacts d'analyse et de planification des
phases suivantes, à côté de transcripts/ qui porte déjà le contrat V2.

PUBLICATION ATOMIQUE

Même schéma que la Phase 1, via app.file_utils.write_text_atomic :

    écriture dans source_map.json.partial
        ↓  validation déjà réussie en amont
    Path.replace() — atomique, y compris sur Windows

Garanties : un source_map.json invalide n'est jamais publié, un fichier valide
déjà présent survit à un échec d'écriture, et aucun `.partial` ne subsiste —
y compris sur KeyboardInterrupt, puisque write_text_atomic intercepte
BaseException pour nettoyer avant de propager.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.file_utils import write_text_atomic
from app.paths import SORTIE_DIR

ANALYSIS_DIR_NAME = "analysis"
TRANSCRIPTS_DIR_NAME = "transcripts"
SOURCE_MAP_NAME = "source_map.json"

# Indentation du fichier publié. Le Source Map est relu par des humains avant
# d'autoriser la phase suivante : il doit être diffable et lisible, pas compact.
_JSON_INDENT = 2


def analysis_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    """Répertoire des artefacts d'analyse V2 d'un projet."""
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR

    return root / project_name / ANALYSIS_DIR_NAME


def source_map_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    """Chemin canonique de source_map.json."""
    return analysis_dir(project_name, sortie_dir=sortie_dir) / SOURCE_MAP_NAME


def transcripts_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    """
    Répertoire du contrat Transcript V2, seule ENTRÉE métier de la Phase 3.

    Déclaré ici avec la sortie pour que tout l'emplacement des fichiers V2 tienne
    dans un seul module : un test qui redirige SORTIE_DIR n'a qu'un point à
    détourner, et l'entrée ne peut pas dériver vers merged/ ou final/ par
    inadvertance.
    """
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR

    return root / project_name / TRANSCRIPTS_DIR_NAME


def partial_path(path: Path) -> Path:
    """Fichier temporaire employé par l'écriture atomique."""
    path = Path(path)

    return path.with_name(path.name + ".partial")


def render_source_map(payload: dict) -> str:
    """
    Sérialisation canonique du Source Map.

    `ensure_ascii=False` : « fidélité » reste lisible plutôt que
    « fid\\u00e9lit\\u00e9 ». Pas de `sort_keys` : l'ordre des clés est celui
    décidé par SourceMap.to_dict(), qui suit la logique de lecture (en-tête,
    analyse globale, collections, stats) et non l'alphabet.

    Aucun horodatage n'apparaît dans ce fichier : deux analyses identiques
    produisent deux fichiers identiques octet pour octet.
    """
    return json.dumps(payload, ensure_ascii=False, indent=_JSON_INDENT) + "\n"


def write_source_map(path: Path, payload: dict) -> Path:
    """Écrit le Source Map atomiquement. Appelé APRÈS validation, jamais avant."""
    return write_text_atomic(Path(path), render_source_map(payload))


def read_source_map_payload(path: Path) -> dict | None:
    """
    Relit un source_map.json publié, ou None s'il est absent ou illisible.

    Un fichier corrompu vaut « pas de cache » plutôt qu'une exception : le
    résultat correct est alors de relancer l'analyse, pas de faire échouer le
    projet sur un artefact qu'on s'apprêtait de toute façon à remplacer.
    """
    path = Path(path)

    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None
