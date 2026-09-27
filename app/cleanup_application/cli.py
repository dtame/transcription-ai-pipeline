"""
Invocation manuelle de la Phase 3A.2B.

Usage :
    python -m app.cleanup_application.cli <projet> --dry-run
    python -m app.cleanup_application.cli <projet> --apply

Sans --apply, le comportement est TOUJOURS un dry-run : aucun fichier
final n'est écrit. Cette phase n'est branchée ni dans main.py, ni dans
le pipeline V1, ni dans Source Analyzer.
"""

from __future__ import annotations

import sys

from app.cleanup_application.constants import POLICY_B_PLUS, REAL_PROJECT_NAME
from app.cleanup_application.errors import CleanupApplicationError
from app.cleanup_application.runner import run_cleanup_application


def _usage() -> None:
    print("Usage  : python -m app.cleanup_application.cli <nom_du_projet> [--dry-run|--apply]")
    print("Exemple: python -m app.cleanup_application.cli pastoral_retreat_v2_validation --dry-run")
    print("         python -m app.cleanup_application.cli pastoral_retreat_v2_validation --apply")
    print("Défaut : DRY RUN (aucune écriture) si --apply n'est pas fourni.")


def _print_dry_run(result) -> None:
    audit = result.audit
    stats = audit["stats"]
    comparison = audit["policy_b_comparison"]
    print(f"[cleanup_application] policy = {POLICY_B_PLUS}")
    print(
        f"[cleanup_application] AUTO_REMOVE={stats['auto_remove_blocks']} "
        f"HUMAN_REVIEW={stats['human_review_blocks']} "
        f"KEEP={stats['keep_blocks']}"
    )
    print(
        f"[cleanup_application] removed SRC={stats['removed_source_count']} "
        f"words={stats['removed_word_count']} "
        f"duration={stats['removed_duration_seconds']}"
    )
    print(
        f"[cleanup_application] B -> B+ exclusions : "
        f"{comparison['excluded_block_count']} blocs, "
        f"{comparison['excluded_src_count']} SRC, "
        f"{comparison['excluded_word_count']} mots"
    )
    print(
        f"[cleanup_application] TRANSLATION_AFTER retained="
        f"{audit['translation_after']['all_retained']} "
        f"(n={audit['translation_after']['observed_count']})"
    )
    print(
        f"[cleanup_application] multi-SRC retained="
        f"{audit['multi_src_translation']['all_retained']} "
        f"(n={audit['multi_src_translation']['observed_count']})"
    )
    print(
        f"[cleanup_application] HIGH_RISK retained="
        f"{audit['high_risk']['all_retained']} "
        f"(n={audit['high_risk']['observed_count']})"
    )
    print(
        f"[cleanup_application] bridges retained="
        f"{audit['bridges']['all_retained']} "
        f"(n={audit['bridges']['observed_count']})"
    )
    print(
        f"[cleanup_application] EXTRA_CONTENT retained="
        f"{audit['extra_content']['all_retained']} "
        f"(n={audit['extra_content']['observed_count']})"
    )
    if result.dry_run:
        print("[cleanup_application] DRY RUN - aucun fichier final ecrit.")
    else:
        print(f"[cleanup_application] published clean json : {result.paths['clean_json']}")
        print(f"[cleanup_application] published clean txt  : {result.paths['clean_txt']}")
        print(f"[cleanup_application] published audit      : {result.paths['audit']}")
        print("[cleanup_application] STOP - en attente de revue humaine.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]
    flags = set(argv[1:])
    if "--apply" in flags and "--dry-run" in flags:
        print("[ERREUR] --apply et --dry-run sont mutuellement exclusifs.")
        return 2

    apply = "--apply" in flags
    unknown = flags - {"--apply", "--dry-run"}
    if unknown:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(unknown)}")
        _usage()
        return 2

    try:
        result = run_cleanup_application(project_name, apply=apply)
    except CleanupApplicationError as exc:
        print(f"[ERREUR] {type(exc).__name__} - STOP : {exc}")
        return 1

    _print_dry_run(result)

    if (
        not apply
        and project_name == REAL_PROJECT_NAME
        and result.audit["stats"]["auto_remove_blocks"] >= 123
    ):
        print(
            "[ATTENTION] AUTO_REMOVE >= 123 (simulation POLICY_B). "
            "Inspecter : B+ doit être plus strict que B."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
