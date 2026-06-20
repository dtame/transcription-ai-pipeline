from app.project_manager import discover_projects


def main():
    projects = discover_projects()

    if not projects:
        print("Aucun projet détecté.")
        return

    for project in projects:
        print("=" * 70)
        print(f"Projet : {project.name}")
        print(f"Dossier source : {project.source_dir}")
        print(f"Nombre de fichiers audio : {len(project.audio_files)}")

        for audio_file in project.audio_files:
            print(f" - {audio_file.name}")

        print(f"Sortie : {project.output_dir}")


if __name__ == "__main__":
    main()