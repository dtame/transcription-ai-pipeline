"""
Construction du contrat Transcript V2 à partir des captures de transcription.

Flux réel :

    Whisper
      ↓  (capture au plus près de la sortie du modèle)
    transcript_capture/<stem>.json
      ↓  (ce module : ordre, ownership overlap, identifiants, langues, stats)
    TranscriptDocument
      ↓  (transcript_writer)
    transcripts/transcript.txt   +   transcripts/transcript_data.json

Responsabilités de ce module :

- ordre canonique des sources audio (tri naturel déterministe) ;
- attribution des identifiants AUDIOxxx et SRCxxxxxx ;
- conversion des timestamps de segment technique → timestamps relatifs au
  fichier audio source ;
- règle d'ownership des segments Whisper aux frontières d'overlap ;
- langue par source et langue primaire du projet ;
- statistiques.

Aucune interprétation éditoriale, aucun appel LLM, aucune traduction.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path

from app.file_utils import natural_sort_key
from app.transcript_capture import load_project_captures
from app.transcript_models import (
    UNDETERMINED_LANGUAGE,
    AudioCapture,
    CapturedPart,
    TranscriptDocument,
    TranscriptSegment,
    TranscriptSource,
    TranscriptStats,
    format_audio_id,
    format_src_id,
    round_seconds,
)


class OwnedSegment:
    """Segment Whisper retenu pour une source, en secondes relatives au fichier."""

    __slots__ = ("start", "end", "text", "language", "part_id")

    def __init__(self, start: float, end: float, text: str, language: str, part_id: str):
        self.start = start
        self.end = end
        self.text = text
        self.language = language
        self.part_id = part_id


# ---------------------------------------------------------------------------
# Ownership aux frontières de segments techniques
# ---------------------------------------------------------------------------
#
# Trois notions, désormais explicitement séparées (Phase 3B.1) :
#
# - CAPTURE WINDOW  : l'étendue audio réellement découpée pour un segment
#                      technique — `[part.start_seconds, part.end_seconds]`.
#                      C'est ce que ffmpeg a extrait ; Whisper transcrit CE
#                      fichier, et rien ne garantit que ses timestamps restent
#                      dans cette étendue (voir « queue hors capture » plus bas).
#
# - OVERLAP WINDOW  : la portion initiale de la capture window d'une partie
#                      (hors la première) que la partie PRÉCÉDENTE a également
#                      capturée — `[part.start_seconds, own_start)`, de durée
#                      `effective_start_local`. Observée par les deux parties ;
#                      son contenu peut donc apparaître deux fois dans les
#                      captures brutes.
#
# - OWNERSHIP WINDOW : la plage de temps dont une partie est l'autorité
#                       exclusive dans le contrat publié — `[own_start,
#                       own_end)`. Contrairement à la capture window, ses deux
#                       bornes sont fixées par la géométrie du découpage
#                       (Phase 1 : `AUDIO_SEGMENT_MINUTES` /
#                       `AUDIO_SEGMENT_OVERLAP_SECONDS`), jamais par la
#                       longueur que Whisper décide spontanément de produire :
#
#                           own_start(N) = N.start_seconds + effective_start_local(N)
#                                          (0.0 pour la toute première partie)
#                           own_end(N)   = own_start(N+1)
#                                          (+∞ pour la toute dernière partie)
#
#                       Ces fenêtres partitionnent la timeline en intervalles
#                       contigus et disjoints : chaque position temporelle a un
#                       propriétaire déterministe, indépendant du contenu.


def _ownership_windows(parts: list[CapturedPart]) -> list[tuple[float, float]]:
    """
    Calcule [own_start, own_end) pour chaque partie technique, uniquement à
    partir de la géométrie de découpage connue (jamais du contenu Whisper).
    """
    starts = [
        part.start_seconds + (part.effective_start_local if index > 0 else 0.0)
        for index, part in enumerate(parts)
    ]

    return [
        (start, starts[index + 1] if index + 1 < len(starts) else math.inf)
        for index, start in enumerate(starts)
    ]


_DEDUP_NORMALIZE_RE = re.compile(r"[^\w]+", re.UNICODE)


def _normalized_for_dedup(text: str) -> str:
    """
    Normalisation minimale et déterministe pour détecter un doublon textuel
    réel dans l'overlap : casse et ponctuation ignorées, espaces réduits.

    Volontairement pas de similarité floue (embeddings, Levenshtein,
    comparaison sémantique) : il ne s'agit que de distinguer une répétition
    mot pour mot d'un contenu réellement différent — cf. Phase 3B.1 §12/14.
    """
    collapsed = _DEDUP_NORMALIZE_RE.sub(" ", text.lower())
    return " ".join(collapsed.split())


def _find_overlapping_duplicate(
    owned: list[OwnedSegment], start: float, text: str
) -> OwnedSegment | None:
    """
    Cherche, parmi les segments déjà retenus dont l'intervalle chevauche
    `start`, un texte identique (normalisé) à `text`.

    Le parcours s'arrête dès qu'un segment déjà retenu se termine avant
    `start` : les segments retenus sont produits dans un ordre croissant de
    fin, rien de plus ancien ne peut donc chevaucher davantage.
    """
    normalized = _normalized_for_dedup(text)

    for candidate in reversed(owned):
        if candidate.end <= start:
            break
        if _normalized_for_dedup(candidate.text) == normalized:
            return candidate

    return None


def _discard_superseded_tail(owned: list[OwnedSegment], start: float) -> None:
    """
    Retire de `owned` les segments déjà retenus dont le début est >= `start`.

    Utilisé uniquement quand un nouveau segment prouve, par un texte
    différent, que ce que la partie précédente avait produit sur cette plage
    n'était pas fiable (queue dégradée, répétition hallucinée). Un même
    instant audio ne peut porter deux textes distincts : celui qui vient
    d'être authentifié comme faisant partie d'un contenu cohérent l'emporte.
    """
    while owned and owned[-1].start >= start:
        owned.pop()


def resolve_owned_segments(capture: AudioCapture) -> list[OwnedSegment]:
    """
    Sélectionne, pour un fichier audio, les segments Whisper qui lui appartiennent
    réellement — une fois et une seule.

    RÈGLE D'OWNERSHIP
    -----------------
    Chaque partie technique a une fenêtre d'ownership exclusive et déterministe
    `[own_start, own_end)`, fixée par la géométrie du découpage (voir
    `_ownership_windows` ci-dessus) — jamais par la longueur que Whisper décide
    spontanément de produire.

    Pour chaque segment Whisper, converti en secondes relatives au fichier :

        0. début >= own_end
           → hors fenêtre technique : cette position appartient déjà à la
             partie SUIVANTE. Une sortie Whisper qui déborde de sa capture
             window (queue répétitive, hallucination de fin de tampon long)
             n'étend jamais son ownership au-delà de la frontière qui lui est
             assignée : IGNORÉ, sans effet sur les segments déjà retenus.
             Cet évènement est aussi la PREUVE STRUCTURELLE, indépendante du
             contenu, que cette partie s'est dégradée près de sa fin — utilisée
             au point 3.b ci-dessous.

        1. own_start <= début < own_end
           → la zone lui appartient exclusivement : CONSERVÉ.

        2. début < own_start ET début >= fin du dernier segment conservé
           → dans l'overlap entrant, mais personne ne l'a encore produit :
             CONSERVÉ (aucune perte de contenu).

        3. début < own_start ET début < fin du dernier segment conservé
           → dans l'overlap entrant, et la position est déjà couverte par un
             segment retenu de la partie précédente.

             a. texte identique (normalisé)  → doublon confirmé : IGNORÉ.

             b. texte différent ET la partie précédente a produit AILLEURS
                une queue hors de sa propre fenêtre technique (règle 0
                déclenchée au moins une fois pour elle) → cette partie est
                structurellement connue comme dégradée près de sa fin ; un
                même instant ne pouvant porter deux textes distincts, les
                segments déjà retenus à partir de cette position sont
                RETIRÉS et ce nouveau segment est CONSERVÉ à leur place.

             c. texte différent, mais la partie précédente n'a AUCUNE preuve
                de dégradation → simple variation normale de transcription
                entre deux appels Whisper indépendants sur la même plage
                (nouveau découpage, légère différence de mot). Sans preuve
                structurelle, on ne peut pas décider laquelle des deux
                versions est la bonne : la politique par défaut de la
                Phase 1 s'applique (la partie précédente l'emporte) — IGNORÉ.

        Le point 3.b est ce qui corrige le bug Phase 3B sans en réintroduire
        un autre : seule une partie DONT ON A LA PREUVE qu'elle a débordé de
        sa fenêtre technique (point 0) peut voir son contenu d'overlap
        supplanté par du texte différent. Une différence de texte ordinaire,
        sans cette preuve, ne suffit jamais à elle seule (§14 : aucune
        heuristique de contenu au-delà d'une égalité textuelle normalisée,
        déclenchée seulement quand une preuve technique l'autorise).

    Priorités respectées, dans cet ordre : aucune perte, pas de duplication,
    chronologie monotone, comportement testable.
    """
    owned: list[OwnedSegment] = []
    last_kept_end = 0.0
    previous_part_overran_its_window = False

    windows = _ownership_windows(capture.parts)

    for part, (own_start, own_end) in zip(capture.parts, windows):
        this_part_overran_its_window = False

        for segment in part.segments:
            start = segment.start + part.start_seconds
            end = segment.end + part.start_seconds

            if start >= own_end:
                # Hors fenêtre technique de cette partie : n'étend jamais son
                # ownership, quelle que soit la longueur produite par Whisper.
                # Preuve structurelle de dégradation, indépendante du texte.
                this_part_overran_its_window = True
                continue

            text = segment.text.strip()

            if not text:
                continue

            if start >= own_start:
                # Zone exclusive de cette partie.
                owned.append(
                    OwnedSegment(
                        start=start,
                        end=end,
                        text=text,
                        language=part.detected_language,
                        part_id=part.id,
                    )
                )
                last_kept_end = max(last_kept_end, end)
                continue

            # Overlap entrant : start < own_start.
            if start >= last_kept_end:
                # Personne ne l'a produit sur cette plage : aucune perte.
                owned.append(
                    OwnedSegment(
                        start=start,
                        end=end,
                        text=text,
                        language=part.detected_language,
                        part_id=part.id,
                    )
                )
                last_kept_end = max(last_kept_end, end)
                continue

            if _find_overlapping_duplicate(owned, start, text) is not None:
                # Doublon confirmé (texte identique après normalisation).
                continue

            if not previous_part_overran_its_window:
                # Texte différent, mais rien ne prouve que la partie
                # précédente s'est dégradée ici : simple variation normale de
                # transcription. Politique par défaut de la Phase 1 : la
                # partie précédente l'emporte.
                continue

            # Contenu différent, ET preuve structurelle que la partie
            # précédente a débordé de sa fenêtre technique : ce qu'elle avait
            # produit sur cette plage n'était pas fiable.
            _discard_superseded_tail(owned, start)
            last_kept_end = owned[-1].end if owned else 0.0

            owned.append(
                OwnedSegment(
                    start=start,
                    end=end,
                    text=text,
                    language=part.detected_language,
                    part_id=part.id,
                )
            )
            last_kept_end = max(last_kept_end, end)

        previous_part_overran_its_window = this_part_overran_its_window

    return owned


# ---------------------------------------------------------------------------
# Langues
# ---------------------------------------------------------------------------

def _dominant_language(
    durations_by_language: dict[str, float],
    fallback: str = UNDETERMINED_LANGUAGE,
) -> str:
    """
    Langue représentant la plus grande durée transcrite.

    Égalité tranchée par ordre alphabétique : le résultat ne dépend jamais de
    l'ordre d'itération.
    """
    if not durations_by_language:
        return fallback

    return min(
        durations_by_language.items(),
        key=lambda item: (-item[1], item[0]),
    )[0]


def _source_language(
    capture: AudioCapture,
    durations_by_language: dict[str, float],
) -> str:
    """
    Langue d'un fichier audio source.

    Politique : langue de la plus grande durée transcrite parmi ses segments
    techniques. Si aucun segment n'a été retenu (audio muet), on retombe sur la
    langue détectée par la première partie technique — jamais sur une devinette.
    """
    if durations_by_language:
        return _dominant_language(durations_by_language)

    for part in capture.parts:
        if part.detected_language:
            return part.detected_language

    return UNDETERMINED_LANGUAGE


# ---------------------------------------------------------------------------
# Construction du document
# ---------------------------------------------------------------------------

def order_captures(captures: list[AudioCapture]) -> list[AudioCapture]:
    """
    Ordre canonique des sources audio : tri naturel sur le nom de fichier.

        audio 1, audio 2, audio 10
        01-introduction, 02-session, 03-conclusion

    Déterministe et indépendant de l'ordre retourné par le système de fichiers.
    """
    return sorted(captures, key=lambda capture: natural_sort_key(capture.filename))


def build_transcript_document(
    project_name: str,
    captures: list[AudioCapture],
) -> TranscriptDocument:
    """
    Construit le contrat V2 à partir des captures d'un projet.

    Les identifiants SRC sont attribués dans l'ordre canonique des sources puis
    dans l'ordre chronologique des segments : ils sont donc uniques, continus,
    ordonnés et déterministes, indépendamment des segments techniques.
    """
    sources: list[TranscriptSource] = []
    segments: list[TranscriptSegment] = []

    project_durations: dict[str, float] = defaultdict(float)
    src_index = 0

    for order, capture in enumerate(order_captures(captures), start=1):
        source_id = format_audio_id(order)
        source_durations: dict[str, float] = defaultdict(float)

        for owned in resolve_owned_segments(capture):
            src_index += 1
            start = round_seconds(owned.start)
            end = round_seconds(owned.end)

            segments.append(
                TranscriptSegment(
                    id=format_src_id(src_index),
                    source_id=source_id,
                    source_order=order,
                    start=start,
                    end=end,
                    text=owned.text,
                )
            )

            spoken = max(0.0, end - start)
            source_durations[owned.language] += spoken
            project_durations[owned.language] += spoken

        sources.append(
            TranscriptSource(
                source_id=source_id,
                order=order,
                filename=capture.filename,
                duration_seconds=round_seconds(capture.duration_seconds),
                detected_language=_source_language(capture, source_durations),
            )
        )

    detected_languages = sorted({source.detected_language for source in sources})

    primary_language = _dominant_language(
        project_durations,
        fallback=detected_languages[0] if detected_languages else UNDETERMINED_LANGUAGE,
    )

    stats = TranscriptStats(
        source_count=len(sources),
        segment_count=len(segments),
        duration_seconds=round_seconds(
            sum(source.duration_seconds for source in sources)
        ),
        word_count=sum(len(segment.text.split()) for segment in segments),
    )

    return TranscriptDocument(
        project_name=project_name,
        sources=sources,
        segments=segments,
        stats=stats,
        primary_language=primary_language,
        detected_languages=detected_languages,
    )


def build_project_transcript(project_name: str, output_dir: Path) -> TranscriptDocument:
    """Construit le contrat V2 depuis les captures présentes sur le disque."""
    return build_transcript_document(
        project_name,
        load_project_captures(output_dir),
    )
