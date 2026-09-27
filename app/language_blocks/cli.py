"""
Invocation manuelle de la Phase 3A.1.1 — analyse structurelle des blocs FR.

Usage : python -m app.language_blocks.cli <nom_du_projet>
Exemple : python -m app.language_blocks.cli pastoral_retreat_v2_validation

Comme app/language_cleanup/cli.py, ce module n'est branché nulle part
automatiquement. Il ne fait que lire transcripts/transcript_data.json et
audit/language_cleanup.json, et écrire audit/language_blocks.json.
"""

from __future__ import annotations

import sys

from app.language_blocks.builder import run_block_analysis
from app.language_blocks.errors import LanguageBlocksError


def _usage() -> None:
    print("Usage  : python -m app.language_blocks.cli <nom_du_projet>")
    print("Exemple: python -m app.language_blocks.cli pastoral_retreat_v2_validation")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]

    try:
        result = run_block_analysis(project_name)
    except LanguageBlocksError as exc:
        print(f"[ERREUR] {exc}")
        return 1

    stats = result.manifest.stats
    print(f"[language_blocks] manifeste publié : {result.output_path}")
    print(f"[language_blocks] FR segments = {stats.total_FR_segments}")
    print(f"[language_blocks] FR blocks   = {stats.total_FR_blocks}")
    print(
        "[language_blocks] semantic_review = "
        f"{stats.semantic_review_distribution}"
    )
    print(f"[language_blocks] analysis_duration_seconds = {result.analysis_duration_seconds}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
