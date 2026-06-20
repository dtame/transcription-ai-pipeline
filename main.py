"""
TranscriptionAI — Point d'entrée principal.

Usage :
    python main.py                      → menu interactif
    python main.py --all                → traiter tous les projets
    python main.py --project <nom>      → traiter un projet spécifique
    python main.py --exports            → exports uniquement (publication/docx/pdf)
    python main.py --reports            → rapports uniquement
    python main.py --status             → afficher l'état des projets
"""

from __future__ import annotations

import argparse
import sys

# Force UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


# ---------------------------------------------------------------------------
# Menu interactif
# ---------------------------------------------------------------------------

MENU = """
=================================
  TranscriptionAI
=================================

  1 - Traiter tous les projets
  2 - Traiter un projet spécifique
  3 - Générer uniquement les exports
  4 - Générer uniquement les rapports
  5 - Afficher l'état des projets
  6 - Quitter

=================================
Choix : """


def _ask_choice(prompt: str, options: list[str]) -> str | None:
    """Affiche une liste numérotée et retourne la valeur choisie."""
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    raw = input("\nVotre choix (numéro) : ").strip()
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass
    return None


def menu_traiter_tous() -> None:
    from app.production_service import process_all_projects
    process_all_projects()


def menu_traiter_un_projet() -> None:
    from app.project_manager import discover_projects
    from app.production_service import process_project

    projects = discover_projects()
    if not projects:
        print("Aucun projet détecté dans depot/.")
        return

    names = [p.name for p in projects]
    print("\nProjets disponibles :")
    choice = _ask_choice("", names)

    if choice is None:
        print("Choix invalide.")
        return

    process_project(choice)


def menu_exports_seulement() -> None:
    from app.production_service import process_exports_only
    process_exports_only()


def menu_rapports_seulement() -> None:
    from app.production_service import process_reports_only
    process_reports_only()


def menu_etat_projets() -> None:
    from app.production_service import print_projects_status
    print_projects_status()


def run_menu() -> None:
    while True:
        try:
            choice = input(MENU).strip()
        except KeyboardInterrupt:
            print("\n\nInterrompu.")
            sys.exit(0)

        if choice == "1":
            menu_traiter_tous()
        elif choice == "2":
            menu_traiter_un_projet()
        elif choice == "3":
            menu_exports_seulement()
        elif choice == "4":
            menu_rapports_seulement()
        elif choice == "5":
            menu_etat_projets()
        elif choice == "6":
            print("\nAu revoir.")
            sys.exit(0)
        else:
            print("Choix invalide. Entrez un nombre entre 1 et 6.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TranscriptionAI — orchestrateur de pipeline audio → document.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        help="Traiter tous les projets détectés dans depot/ sans menu.",
    )
    group.add_argument(
        "--project",
        metavar="NOM",
        help="Traiter uniquement le projet spécifié.",
    )
    group.add_argument(
        "--exports",
        action="store_true",
        help="Générer uniquement publication + DOCX + PDF (sans IA/transcription).",
    )
    group.add_argument(
        "--reports",
        action="store_true",
        help="Régénérer uniquement les rapports JSON.",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Afficher l'état de tous les projets.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.all:
        from app.production_service import process_all_projects
        process_all_projects()

    elif args.project:
        from app.production_service import process_project
        process_project(args.project)

    elif args.exports:
        from app.production_service import process_exports_only
        process_exports_only()

    elif args.reports:
        from app.production_service import process_reports_only
        process_reports_only()

    elif args.status:
        from app.production_service import print_projects_status
        print_projects_status()

    else:
        run_menu()


if __name__ == "__main__":
    main()
