"""
TranscriptionAI — Vérification système.

Vérifie que l'environnement est correctement configuré avant le premier lancement.

Usage :
    python check_system.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers d'affichage
# ---------------------------------------------------------------------------

WIDTH = 60


def _header(title: str) -> None:
    print()
    print("=" * WIDTH)
    print(f"  {title}")
    print("=" * WIDTH)


def _ok(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  [OK]    {label}{suffix}")


def _warn(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  [WARN]  {label}{suffix}")


def _fail(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  [FAIL]  {label}{suffix}")


def _info(label: str, detail: str = "") -> None:
    suffix = f"  {detail}" if detail else ""
    print(f"  [INFO]  {label}{suffix}")


# ---------------------------------------------------------------------------
# Vérifications
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent

errors: list[str] = []
warnings: list[str] = []


def check_python() -> None:
    _header("Python")
    version = sys.version_info
    ver_str = f"{version.major}.{version.minor}.{version.micro}"
    if version.major == 3 and version.minor >= 10:
        _ok(f"Python {ver_str}", "version compatible")
    elif version.major == 3 and version.minor == 9:
        _warn(f"Python {ver_str}", "Python 3.10+ recommandé")
        warnings.append(f"Python {ver_str} — version minimale 3.10 recommandée")
    else:
        _fail(f"Python {ver_str}", "Python 3.10+ requis")
        errors.append(f"Python {ver_str} non supporté — installez Python 3.11")


def check_folders() -> None:
    _header("Dossiers du projet")
    required = ["depot", "sortie", "logs", "temp", "rejets", "archives"]
    for folder in required:
        path = ROOT / folder
        if path.exists() and path.is_dir():
            _ok(folder + "/")
        else:
            _warn(f"{folder}/", "absent — sera créé automatiquement")
            warnings.append(f"Dossier {folder}/ absent")


def check_files() -> None:
    _header("Fichiers principaux")
    files = {
        "requirements.txt": "liste des dépendances",
        "main.py": "point d'entrée console",
        "streamlit_app.py": "interface Streamlit",
        "app/config.py": "configuration principale",
    }
    for filepath, desc in files.items():
        path = ROOT / filepath
        if path.exists():
            _ok(filepath, desc)
        else:
            _fail(filepath, f"MANQUANT — {desc}")
            errors.append(f"{filepath} introuvable")


def check_write_permissions() -> None:
    _header("Droits d'écriture")
    test_dirs = ["sortie", "logs"]
    for dirname in test_dirs:
        path = ROOT / dirname
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            _ok(f"{dirname}/", "écriture autorisée")
        except OSError as e:
            _fail(f"{dirname}/", f"écriture refusée : {e}")
            errors.append(f"Pas de droits d'écriture dans {dirname}/")


def check_disk_space() -> None:
    _header("Espace disque")
    total, used, free = shutil.disk_usage(ROOT)
    free_gb = free / (1024 ** 3)
    total_gb = total / (1024 ** 3)
    detail = f"{free_gb:.1f} Go libres sur {total_gb:.1f} Go"
    if free_gb >= 5:
        _ok("Espace disque suffisant", detail)
    elif free_gb >= 2:
        _warn("Espace disque limité", detail + " — minimum recommandé : 5 Go")
        warnings.append(f"Espace disque limité : {free_gb:.1f} Go libres")
    else:
        _fail("Espace disque insuffisant", detail + " — minimum requis : 2 Go")
        errors.append(f"Espace disque insuffisant : {free_gb:.1f} Go libres")


def check_ollama() -> None:
    _header("Ollama (moteur IA local)")

    try:
        import requests  # type: ignore
    except ImportError:
        _warn("Module 'requests' absent", "impossible de tester Ollama")
        warnings.append("Module 'requests' non installé — Ollama non vérifié")
        return

    url = "http://localhost:11434/api/tags"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        _warn("Ollama non accessible", "lancez Ollama puis relancez check_system.bat")
        warnings.append("Ollama n'est pas démarré — démarrez-le avant d'utiliser TranscriptionAI")
        return
    except requests.exceptions.Timeout:
        _warn("Ollama : délai dépassé", "Ollama est peut-être en cours de démarrage")
        warnings.append("Ollama timeout — réessayez dans quelques secondes")
        return
    except Exception as e:
        _warn("Ollama : erreur inattendue", str(e))
        warnings.append(f"Ollama : erreur — {e}")
        return

    _ok("Ollama est en cours d'exécution")

    # Liste des modèles disponibles
    models: list[str] = []
    for m in data.get("models", []):
        name = m.get("name", "")
        if name:
            models.append(name)

    if models:
        _info("Modèles disponibles :")
        for m in models:
            print(f"            - {m}")
    else:
        _warn("Aucun modèle installé", "lancez : ollama pull qwen3:8b")
        warnings.append("Aucun modèle Ollama installé")

    # Vérification du modèle configuré
    try:
        sys.path.insert(0, str(ROOT))
        from app.config import OLLAMA_MODEL  # type: ignore
        configured = OLLAMA_MODEL
    except Exception:
        configured = "qwen3:8b"

    configured_base = configured.split(":")[0]
    found = any(configured_base in m for m in models)

    if found:
        _ok(f"Modèle configuré disponible", configured)
    else:
        _warn(
            f"Modèle configuré absent : {configured}",
            f"lancez : ollama pull {configured}",
        )
        warnings.append(
            f"Modèle Ollama '{configured}' non installé — "
            f"lancez : ollama pull {configured}"
        )


# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------

def print_summary() -> None:
    _header("Résumé")

    if not errors and not warnings:
        print("  Tout est en ordre. TranscriptionAI est prêt.")
        print()
        print("  Démarrez l'interface avec : start_ui.bat")
        print("  Ou la console avec        : start_console.bat")
    else:
        if errors:
            print(f"  {len(errors)} ERREUR(S) détectée(s) — à corriger avant utilisation :")
            for e in errors:
                print(f"    • {e}")
        if warnings:
            print()
            print(f"  {len(warnings)} AVERTISSEMENT(S) — non bloquants :")
            for w in warnings:
                print(f"    • {w}")

    print()
    print("=" * WIDTH)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("=" * WIDTH)
    print("  TranscriptionAI — Vérification système")
    print("=" * WIDTH)

    check_python()
    check_files()
    check_folders()
    check_write_permissions()
    check_disk_space()
    check_ollama()
    print_summary()

    if errors:
        sys.exit(1)
