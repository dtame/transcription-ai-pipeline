"""
Fixture d'intégration bout-en-bout pour la Phase 3A.1.2A (canary sémantique).

Construit un VRAI petit projet (transcript_data.json -> language_cleanup.json
via le vrai auditeur Phase 3A.1 -> language_blocks.json via le vrai
analyseur Phase 3A.1.1), conçu pour que la sélection déterministe du canary
(app.semantic_canary.selection) trouve tous les bassins qu'elle exige :

    >= 6 blocs ALREADY_RESOLVED         (pool A)
    >= 6 blocs ALL_REVIEW & NEEDED      (pool B)
    >= 6 blocs ALL_KEEP & NEEDED        (pool C)
    1 bloc AUDIO003                     (D2)
    1 bloc BEFORE-only                  (D3)
    1 bloc AFTER-only                   (D4)
    1 bloc BOTH avec ratio de mots élevé (D5)
    1 bloc nettement plus long que les autres (D1)

Les décisions Phase 3A.1 (REMOVE_TRANSLATION / REVIEW / KEEP) sont obtenues
en exploitant les seuils DOCUMENTÉS et déterministes de
app.language_cleanup.translation_matcher / auditor — jamais en les
contournant : un jeu de phrases FR/EN construit pour franchir (ou non) ces
seuils précis, rien de plus.
"""

from __future__ import annotations

from pathlib import Path

from app.language_blocks.builder import run_block_analysis
from app.language_cleanup.auditor import run_audit
from app.transcript_models import (
    TranscriptDocument,
    TranscriptSegment,
    TranscriptSource,
    TranscriptStats,
    format_audio_id,
    format_src_id,
    round_seconds,
)
from app.transcript_validator import ensure_valid_transcript_document
from app.transcript_writer import TRANSCRIPT_JSON_NAME

PROJECT = "semantic_canary_fixture_project"

SEGMENT_DURATION_SECONDS = 5.0

# ---------------------------------------------------------------------------
# Phrases — chaque tuple (langue, texte). Une frontière d'audio est marquée
# par une nouvelle sous-liste dans AUDIO_SCRIPTS.
# ---------------------------------------------------------------------------

# AUDIO001 : 6 paires EN/FR à recouvrement lexical FORT -> REMOVE_TRANSLATION
# (pool A — contrôle positif ALREADY_RESOLVED).
_AUDIO001 = [
    ("EN", "God wants to give you power for your life."),
    ("FR", "Dieu veut vous donner la puissance."),
    ("EN", "The Lord wants to bless your heart today."),
    ("FR", "Le Seigneur veut benir votre coeur."),
    ("EN", "Jesus wants to save your soul from sin."),
    ("FR", "Jesus veut sauver votre ame."),
    ("EN", "The king wants to give his kingdom away."),
    ("FR", "Le roi veut donner son royaume."),
    ("EN", "God wants to forgive your sin completely."),
    ("FR", "Dieu veut pardonner votre peche."),
    ("EN", "The Father wants to give you light always."),
    ("FR", "Le Pere veut vous donner la lumiere."),
]

# AUDIO002 : 6 paires EN/FR à recouvrement lexical FAIBLE (un seul jeton
# partagé) -> REVIEW (pool B). Puis 6 paires EN/FR SANS aucun recouvrement
# -> KEEP (pool C).
_AUDIO002 = [
    ("EN", "We will read about the king today in our study."),
    ("FR", "Le roi n'est pas vraiment le sujet de mon histoire preferee."),
    ("EN", "God is the center of our discussion this morning."),
    ("FR", "Dieu occupe une place que je ne saurais decrire facilement."),
    ("EN", "Love changes everything we do in our daily life."),
    ("FR", "L'amour transforme des choses que je vis chaque jour ici."),
    ("EN", "We should forgive people who hurt us deeply."),
    ("FR", "Pardonner reste une chose difficile pour beaucoup de gens."),
    ("EN", "The heart of the matter is simple to explain."),
    ("FR", "Mon coeur ressent des choses que je narrive pas a nommer."),
    ("EN", "Time changes the way we understand our own story."),
    ("FR", "Le temps efface des souvenirs que je gardais precieusement."),
    # KEEP — aucun recouvrement lexical avec les EN adjacents.
    ("EN", "The weather today is quite pleasant for our gathering."),
    ("FR", "J'ai visite un marche coloré avec des fruits exotiques rares."),
    ("EN", "This building has excellent acoustics for our music."),
    ("FR", "Les enfants jouaient dehors avec un ballon rouge et bleu."),
    ("EN", "Our schedule for tomorrow includes a long walk outside."),
    ("FR", "La cuisine locale propose des plats vraiment tres varies."),
    ("EN", "The garden behind this house has many colorful flowers."),
    ("FR", "Mon voisin repare sa voiture depuis plusieurs jours deja."),
    ("EN", "Traffic was unusually light on our drive this morning."),
    ("FR", "Cette region produit un fromage local assez reputee."),
    ("EN", "The library downtown just received many new books."),
    ("FR", "Nous avons visite un vieux village de pecheurs hier."),
]

# AUDIO003 : un seul bloc FR (D2 — bloc AUDIO003), recouvrement faible
# (REVIEW), pour rester dans le bassin NEEDED.
_AUDIO003 = [
    ("EN", "We continue our teaching about faith and endurance."),
    ("FR", "Le roi de cette histoire n'apparait presque jamais ici."),
    ("EN", "This part of the story matters for later chapters."),
]

# AUDIO004 : bloc AFTER-only (FR en tout premier, rien avant), bloc
# BEFORE-only (FR en tout dernier, rien apres), et un bloc BOTH long et
# "riche" (D1 + D5 : mots FR >> mots EN adjacents combinés).
_AUDIO004 = [
    # AFTER-only : premier segment du fichier -> aucun contexte avant.
    ("FR", "Mon enfance dans un petit village reste un souvenir tres marquant pour moi."),
    ("EN", "We now begin our reflection on family and memory together."),
    # Bloc long et riche (BOTH) : mots FR largement supérieurs aux mots EN
    # adjacents combinés -> heuristique "contenu excedentaire" (D5), et aussi
    # le bloc le plus long du corpus (D1).
    ("EN", "Let us think about grace for a moment."),
    (
        "FR",
        "La grace de Dieu agit dans nos vies de manieres que nous ne "
        "comprenons pas toujours immediatement, et je voudrais partager "
        "avec vous une histoire personnelle qui illustre cela avec des "
        "details que je n'ai jamais racontes publiquement avant aujourd'hui, "
        "une histoire qui a change ma maniere de voir la patience, le doute, "
        "et la confiance que l'on place dans des choses invisibles mais "
        "reelles pour celui qui les vit chaque jour avec serieux.",
    ),
    ("EN", "Grace remains central to everything we teach here."),
    # BEFORE-only : dernier segment du fichier -> aucun contexte après.
    ("EN", "This concludes our main teaching point for today."),
    ("FR", "Je vous remercie tous pour votre attention et votre patience."),
]

AUDIO_SCRIPTS = (_AUDIO001, _AUDIO002, _AUDIO003, _AUDIO004)


def build_fixture_transcript() -> TranscriptDocument:
    """Construit un Transcript V2 valide, multi-audio, pour ce fixture."""
    segments: list[TranscriptSegment] = []
    sources: list[TranscriptSource] = []
    src_index = 1

    for audio_index, script in enumerate(AUDIO_SCRIPTS, start=1):
        source_id = format_audio_id(audio_index)
        cursor = 0.0

        for language, text in script:
            end = cursor + SEGMENT_DURATION_SECONDS
            segments.append(
                TranscriptSegment(
                    id=format_src_id(src_index),
                    source_id=source_id,
                    source_order=audio_index,
                    start=round_seconds(cursor),
                    end=round_seconds(end),
                    text=text,
                )
            )
            cursor = end
            src_index += 1

        sources.append(
            TranscriptSource(
                source_id=source_id,
                order=audio_index,
                filename=f"{audio_index:02d}-audio.mp3",
                duration_seconds=round_seconds(cursor),
                detected_language="fr",
            )
        )

    stats = TranscriptStats(
        source_count=len(sources),
        segment_count=len(segments),
        duration_seconds=sum(source.duration_seconds for source in sources),
        word_count=sum(len(segment.text.split()) for segment in segments),
    )

    document = TranscriptDocument(
        project_name=PROJECT,
        sources=sources,
        segments=segments,
        stats=stats,
        primary_language="fr",
        detected_languages=["fr"],
    )

    ensure_valid_transcript_document(document)

    return document


def write_fixture_transcript(sortie_dir: Path) -> Path:
    """Écrit transcript_data.json du fixture sous sortie_dir/<projet>/transcripts/."""
    import json

    document = build_fixture_transcript()
    directory = Path(sortie_dir) / PROJECT / "transcripts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / TRANSCRIPT_JSON_NAME

    path.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return path


def build_fixture_project(sortie_dir: Path):
    """
    Construit le projet fixture complet sur disque : transcript_data.json,
    puis language_cleanup.json (vrai auditeur), puis language_blocks.json
    (vrai analyseur). Retourne le résultat de `run_block_analysis`.
    """
    write_fixture_transcript(sortie_dir)
    run_audit(PROJECT, sortie_dir=sortie_dir, write=True)
    return run_block_analysis(PROJECT, sortie_dir=sortie_dir, write=True)
