from app.project_manager import discover_projects
from app.transcript_merger import merge_project_transcripts


def main():
    projects = discover_projects()

    if not projects:
        print("Aucun projet détecté.")
        return

    for project in projects:
        print("=" * 70)
        print(f"Projet : {project.name}")
        merge_project_transcripts(project)


if __name__ == "__main__":
    main()