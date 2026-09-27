"""
Invocation manuelle de la Phase 3A.1 — audit linguistique.

Usage : python -m app.language_cleanup.cli <nom_du_projet>
Exemple : python -m app.language_cleanup.cli pastoral_retreat_v2_validation

Comme app/source_analysis/analyzer.py, ce module n'est branché nulle part
automatiquement : ni main.py, ni pipeline_runner.py ne l'appellent. Il ne fait
que lire transcripts/transcript_data.json et écrire audit/language_cleanup.json.
"""

from __future__ import annotations

import sys

from app.language_cleanup.auditor import run_audit
from app.language_cleanup.errors import LanguageCleanupError


def _usage() -> None:
    print("Usage  : python -m app.language_cleanup.cli <nom_du_projet>")
    print("Exemple: python -m app.language_cleanup.cli pastoral_retreat_v2_validation")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]

    try:
        result = run_audit(project_name)
    except LanguageCleanupError as exc:
        print(f"[ERREUR] {exc}")
        return 1

    stats = result.manifest.stats
    print(f"[language_cleanup] manifeste publié : {result.output_path}")
    print(f"[language_cleanup] segments audités : {stats.total_segments}")
    print(
        f"[language_cleanup] KEEP={stats.KEEP_segments} "
        f"REMOVE_TRANSLATION={stats.REMOVE_TRANSLATION_segments} "
        f"REVIEW={stats.REVIEW_segments}"
    )
    print(f"[language_cleanup] audit_duration_seconds={result.audit_duration_seconds}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
