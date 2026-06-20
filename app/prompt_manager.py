"""
Gestionnaire de prompts configurables pour TranscriptionAI.

Chaque tâche IA possède son propre template de prompt.
La tâche active est définie par AI_TASK dans app/config.py.

Tâches disponibles :
    clean_transcript             -> correction et structuration Markdown d'une transcription brute
    summary                      -> résumé clair et structuré
    book_chapter                 -> transformation en chapitre de livre
    key_points                   -> extraction des idées principales
    classification               -> classification documentaire
    global_harmonization_light   -> harmonisation légère du document complet (étape 18)
    global_harmonization_medium  -> harmonisation moyenne du document complet (étape 18)
    global_harmonization_aggressive -> harmonisation agressive du document complet (étape 18)

Prompts personnalisés par projet :
    Placer un fichier depot/<nom_projet>/prompt.md pour surcharger AI_TASK.
    Le fichier doit contenir le placeholder {text}.

Priorité des prompts :
    1. depot/<nom_projet>/prompt.md  (prioritaire si présent)
    2. AI_TASK dans config.py
    3. fallback : clean_transcript
"""

from pathlib import Path

from app.paths import DEPOT_DIR

PROMPT_TEMPLATES: dict[str, str] = {
    "clean_transcript": """
Tu es un assistant spécialisé dans la transformation de transcriptions audio brutes en documents clairs, structurés et lisibles.

Ta mission :
- corriger les erreurs évidentes de transcription
- améliorer la ponctuation
- conserver fidèlement le sens original
- ne pas inventer d'informations
- structurer le contenu en Markdown
- créer des titres et sous-titres pertinents
- rendre le texte fluide
- préserver le ton de l'orateur
- supprimer les répétitions inutiles seulement si elles nuisent à la lecture

Important :
- Ne résume pas trop.
- Ne transforme pas le message en autre chose.
- Ne change pas les idées de l'orateur.
- Ne crée pas de contenu absent de la transcription.

Transcription brute à traiter :

{text}
""",

    "summary": """
Tu es un assistant spécialisé dans la synthèse de transcriptions audio.

Ta mission :
- produire un résumé clair
- identifier le sujet principal
- extraire les grandes parties
- garder les idées essentielles
- supprimer les détails secondaires
- structurer la réponse en Markdown

Format attendu :
# Résumé

## Sujet principal

## Idées principales

## Conclusion

Transcription à résumer :

{text}
""",

    "book_chapter": """
Tu es un assistant éditorial spécialisé dans la transformation de transcriptions audio en chapitre de livre.

Ta mission :
- transformer le texte oral en chapitre écrit fluide
- conserver les idées de l'orateur
- améliorer la structure
- créer des titres et sous-titres
- supprimer les hésitations inutiles
- garder un style naturel et lisible
- ne pas inventer de contenu absent de la transcription

Format attendu :
# Titre du chapitre

## Introduction

## Développement

## Conclusion

Transcription à transformer :

{text}
""",

    "key_points": """
Tu es un assistant spécialisé dans l'extraction d'informations.

Ta mission :
- extraire les idées principales
- identifier les concepts importants
- lister les arguments clés
- relever les exemples significatifs
- structurer la sortie en Markdown

Format attendu :
# Points clés

## Idées principales

## Concepts importants

## Exemples cités

## À retenir

Contenu à analyser :

{text}
""",

    "classification": """
Tu es un assistant spécialisé dans la classification documentaire.

Ta mission :
Analyser le contenu et produire une classification structurée.

Format attendu :
# Classification

## Type de contenu
Exemples : conférence, enseignement, réunion, entrevue, formation, prédication, témoignage, cours, discussion.

## Thèmes principaux

## Public cible probable

## Niveau de formalité
Faible / moyen / élevé

## Langue principale

## Résumé en une phrase

Contenu à classifier :

{text}
""",

    "global_harmonization_light": """
Tu es un éditeur professionnel chargé d'harmoniser la cohérence éditoriale d'un document complet.

Ta mission est UNIQUEMENT d'améliorer la cohérence formelle du document, sans en modifier le contenu.

Ce que tu peux faire :
- Harmoniser le style des titres et sous-titres (capitalisation, ponctuation finale, cohérence de niveau)
- Uniformiser la structure des listes (tirets, puces, numérotation)
- Uniformiser le style des citations et des mises en évidence (gras, italique)
- Améliorer les transitions entre chapitres et sections pour assurer la fluidité
- Uniformiser la ponctuation (guillemets, tirets, points de suspension)
- Corriger les incohérences d'espacement et de formatage Markdown

Ce qui est STRICTEMENT INTERDIT :
- Supprimer des idées, des arguments ou des informations
- Résumer ou raccourcir des passages
- Reformuler fortement des phrases ou des paragraphes
- Ajouter du contenu absent du document original
- Modifier le sens ou l'intention de l'auteur

Retourne le document complet harmonisé en Markdown, sans commentaires ni explications.

Document à harmoniser :

{text}
""",

    "global_harmonization_medium": """
Tu es un éditeur professionnel chargé d'améliorer la cohérence et la fluidité d'un document complet.

Ta mission est d'améliorer la lisibilité du document tout en préservant fidèlement son contenu et son sens.

Ce que tu peux faire :
- Tout ce qui est permis en mode light (harmonisation formelle)
- Fusionner légèrement des répétitions proches lorsqu'elles nuisent à la lecture
- Améliorer la fluidité des transitions entre paragraphes
- Restructurer légèrement des passages maladroits sans en changer le sens
- Réécrire superficiellement des phrases trop longues ou confuses

Ce qui est STRICTEMENT INTERDIT :
- Supprimer des sections entières ou des idées importantes
- Créer du nouveau contenu absent du document original
- Modifier substantiellement le ton ou le style de l'auteur
- Réduire significativement la longueur du document

Retourne le document complet amélioré en Markdown, sans commentaires ni explications.

Document à améliorer :

{text}
""",

    "global_harmonization_aggressive": """
Tu es un éditeur professionnel senior chargé de la révision complète d'un livre ou d'un long document.

Ta mission est de produire une version éditoriale de haute qualité, fidèle au contenu original mais
significativement améliorée sur le plan de la structure, de la fluidité et de la cohérence.

Ce que tu peux faire :
- Réécrire globalement le document pour améliorer la qualité littéraire
- Restructurer l'organisation des sections et des chapitres
- Réduire les redondances et les répétitions importantes
- Améliorer substantiellement la fluidité et le style
- Consolider des passages dispersés traitant du même sujet

Contrainte absolue :
- Le document final doit rester fidèle au contenu et aux idées du document original
- Aucune idée, argument ou information de l'original ne doit être perdu
- Ne pas inventer d'informations ou de contenus absents de l'original

Retourne le document complet révisé en Markdown, sans commentaires ni explications.

Document à réviser :

{text}
""",
}


def get_project_prompt(project_name: str) -> str | None:
    """
    Cherche et retourne le prompt personnalisé d'un projet.

    Lit le fichier depot/<project_name>/prompt.md s'il existe.

    Args:
        project_name: nom du projet (sous-dossier de depot/)

    Returns:
        Contenu du fichier prompt.md, ou None si le fichier n'existe pas.

    Raises:
        ValueError: si le fichier existe mais est vide ou ne contient pas {text}
    """
    prompt_path: Path = DEPOT_DIR / project_name / "prompt.md"

    if not prompt_path.exists():
        return None

    content = prompt_path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError(
            f"Le fichier de prompt projet est vide : {prompt_path}\n"
            "Ajoutez un prompt valide contenant le placeholder {text}."
        )

    if "{text}" not in content:
        raise ValueError(
            f"Le prompt projet ne contient pas le placeholder {{text}} : {prompt_path}\n"
            "Ajoutez {{text}} à l'endroit où le texte brut doit être inséré."
        )

    return content


def get_prompt_template(task_name: str) -> str:
    """
    Retourne le template de prompt pour une tâche donnée.

    Args:
        task_name: identifiant de la tâche (ex. "clean_transcript")

    Returns:
        Le template de prompt (chaîne avec placeholder {text})

    Raises:
        ValueError: si task_name ne correspond à aucune tâche connue
    """
    available_tasks = list(PROMPT_TEMPLATES.keys())

    if task_name not in PROMPT_TEMPLATES:
        raise ValueError(
            f"Tâche IA inconnue : '{task_name}'. "
            f"Tâches disponibles : {available_tasks}"
        )

    return PROMPT_TEMPLATES[task_name]


def build_prompt(task_name: str, text: str, project_name: str | None = None) -> str:
    """
    Construit le prompt final en injectant le texte dans le template.

    Priorité :
        1. depot/<project_name>/prompt.md si project_name fourni et fichier présent
        2. template associé à task_name
        3. fallback clean_transcript si task_name inconnu

    Args:
        task_name: identifiant de la tâche (ex. "clean_transcript")
        text: contenu brut à traiter
        project_name: nom du projet (optionnel) pour chercher un prompt personnalisé

    Returns:
        Le prompt complet prêt à envoyer au moteur IA

    Raises:
        ValueError: si prompt.md existe mais est invalide (vide ou sans {text})
    """
    if project_name is not None:
        project_prompt = get_project_prompt(project_name)
        if project_prompt is not None:
            return project_prompt.format(text=text)

    if task_name not in PROMPT_TEMPLATES:
        fallback = "clean_transcript"
        print(
            f"[prompt_manager] Tâche IA inconnue : '{task_name}'. "
            f"Fallback sur '{fallback}'."
        )
        task_name = fallback

    template = get_prompt_template(task_name)
    return template.format(text=text)
