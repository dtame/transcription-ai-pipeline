"""
Fixtures partagées des tests de Phase 3 (Source Analyzer).

Deux principes :

1. le transcript de test est un VRAI contrat Transcript V2 — il est construit
   avec les modèles de la Phase 1 et passe son validateur. Un fixture bricolé à
   la main laisserait passer des tests qui échoueraient sur un vrai projet ;

2. aucun réseau, aucune clé d'API, aucun appel réel. Le moteur est toujours
   FakeAIEngine, et le répertoire `sortie/` est redirigé vers tmp_path.

Ces fixtures ne retranscrivent rien et ne touchent à aucun projet existant :
`depot/pastoral retreat/` et `sortie/pastoral_retreat/` ne sont jamais lus.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, replace as dataclass_replace
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
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

# Huit segments : cinq porteurs de contenu, trois hésitations. La couverture
# attendue est donc volontairement inférieure à 100 %, ce qui est le cas normal
# d'un discours oral.
DEFAULT_SEGMENT_TEXTS = (
    "La foi ne supprime pas l'épreuve, elle change la manière de la traverser.",
    "Quand tout s'effondre, ce qui reste debout est ce à quoi vous croyez vraiment.",
    "J'ai rencontré un homme qui avait tout perdu et qui priait encore chaque matin.",
    "L'épreuve révèle la solidité de la confiance plutôt qu'elle ne la fabrique.",
    "Traverser ne veut pas dire contourner, cela veut dire avancer malgré tout.",
    "Euh voilà.",
    "Bon.",
    "Hmm oui.",
)

SEGMENT_DURATION_SECONDS = 10.0


def build_transcript_document(
    *,
    project_name: str = "demo_analysis",
    texts: tuple[str, ...] = DEFAULT_SEGMENT_TEXTS,
    language: str = "fr",
    transcript_id: str | None = None,
) -> TranscriptDocument:
    """
    Construit un Transcript V2 valide à partir d'une liste de textes.

    Un seul fichier audio, segments contigus de dix secondes : la structure
    temporelle n'a aucune importance pour la Phase 3, qui ne doit surtout pas
    s'en servir pour organiser le sens.
    """
    segments: list[TranscriptSegment] = []
    start = 0.0

    for index, text in enumerate(texts, start=1):
        end = start + SEGMENT_DURATION_SECONDS

        segments.append(
            TranscriptSegment(
                id=format_src_id(index),
                source_id=format_audio_id(1),
                source_order=1,
                start=round_seconds(start),
                end=round_seconds(end),
                text=text,
            )
        )

        start = end

    source = TranscriptSource(
        source_id=format_audio_id(1),
        order=1,
        filename="01-enseignement.mp3",
        duration_seconds=round_seconds(start),
        detected_language=language,
    )

    stats = TranscriptStats(
        source_count=1,
        segment_count=len(segments),
        duration_seconds=round_seconds(start),
        word_count=sum(len(text.split()) for text in texts),
    )

    kwargs = {}

    if transcript_id is not None:
        kwargs["transcript_id"] = transcript_id

    document = TranscriptDocument(
        project_name=project_name,
        sources=[source],
        segments=segments,
        stats=stats,
        primary_language=language,
        detected_languages=[language],
        **kwargs,
    )

    ensure_valid_transcript_document(document)

    return document


def drop_segments(document: TranscriptDocument, removed_ids: set[str]) -> TranscriptDocument:
    """Vue dérivée : mêmes SRC survivants, stats recalculées, durée audio inchangée."""
    remaining = [segment for segment in document.segments if segment.id not in removed_ids]
    stats = TranscriptStats(
        source_count=document.stats.source_count,
        segment_count=len(remaining),
        duration_seconds=document.stats.duration_seconds,
        word_count=sum(len(segment.text.split()) for segment in remaining),
    )
    derived = dataclass_replace(document, segments=remaining, stats=stats)
    from app.transcript_validator import ensure_valid_transcript_document

    ensure_valid_transcript_document(derived, allow_source_id_gaps=True)
    return derived


def write_cleanup_provenance(
    path: Path,
    *,
    original_path: Path,
    clean_path: Path,
    original: TranscriptDocument,
    clean: TranscriptDocument,
    removed: list[TranscriptSegment],
    **overrides,
) -> Path:
    """cleanup_application.json minimal mais suffisant pour la provenance DERIVED."""
    from app.cleanup_application.constants import POLICY_B_PLUS
    from app.semantic_canary.integrity import sha256_of_file

    payload = {
        "schema_version": "1.0",
        "policy": {"policy_id": POLICY_B_PLUS},
        "derivation": {
            "type": "language_cleanup",
            "source_transcript_id": original.transcript_id,
            "policy": POLICY_B_PLUS,
            "removed_source_count": len(removed),
        },
        "source_hashes": {"transcript_data": sha256_of_file(original_path)},
        "clean_hashes": {"clean_transcript_data_sha256": sha256_of_file(clean_path)},
        "stats": {
            "original_segment_count": original.stats.segment_count,
            "clean_segment_count": clean.stats.segment_count,
            "original_word_count": original.stats.word_count,
            "clean_word_count": clean.stats.word_count,
            "removed_source_count": len(removed),
        },
        "removed": [
            {
                "source_ref": segment.id,
                "audio_id": segment.source_id,
                "source_order": segment.source_order,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
            }
            for segment in removed
        ],
    }
    payload.update(overrides)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_transcript(directory: Path, document: TranscriptDocument) -> Path:
    """Écrit transcript_data.json dans un répertoire transcripts/."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / TRANSCRIPT_JSON_NAME

    path.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return path


# ---------------------------------------------------------------------------
# Réponse simulée du Source Analyzer
# ---------------------------------------------------------------------------
#
# Contenu du scénario de référence (§62 du cahier des charges) :
#   main_theme, 1 topic, 2 ideas, 1 example, 0 reference, 0 uncertainty,
#   1 repetition, author_voice_profile.
#
# Les identifiants locaux sont volontairement quelconques : le programme ne doit
# jamais les reprendre tels quels.

_BASE_PAYLOAD = {
    "source_analysis": {
        "main_theme": (
            "Le rôle de la foi dans la manière de traverser les épreuves"
        ),
        "author_intent": {
            "summary": "Enseigner ce que la foi change dans l'épreuve, et encourager.",
            "confidence": "high",
            "kinds": ["enseigner", "encourager"],
        },
        "target_audience": {
            "summary": (
                "Audience croyante intéressée par un enseignement sur la foi "
                "dans les difficultés."
            ),
            "confidence": "medium",
            "kinds": [],
        },
    },
    "topics": [
        {
            "topic_id": "t_foi",
            "label": "Foi dans l'épreuve",
            "summary": "Ce que la foi modifie dans la traversée d'une épreuve.",
            "source_refs": ["SRC000001", "SRC000002", "SRC000004"],
        }
    ],
    "ideas": [
        {
            "idea_id": "idea_7",
            "summary": (
                "La foi ne fait pas disparaître l'épreuve : elle change la "
                "manière de la traverser."
            ),
            "kind": "claim",
            "importance": "central",
            "topic_refs": ["t_foi"],
            "relations": [],
            "source_refs": ["SRC000001", "SRC000002"],
        },
        {
            "idea_id": "banana",
            "summary": (
                "L'épreuve révèle la solidité d'une confiance déjà présente "
                "plutôt qu'elle ne la crée."
            ),
            "kind": "explanation",
            "importance": "supporting",
            "topic_refs": ["t_foi"],
            "relations": [{"relation": "supports", "to_idea": "idea_7"}],
            "source_refs": ["SRC000004", "SRC000005"],
        },
    ],
    "examples": [
        {
            "example_id": "42",
            "kind": "anecdote",
            "summary": (
                "Un homme qui avait tout perdu et continuait de prier chaque matin."
            ),
            "supports_idea_refs": ["idea_7"],
            "source_refs": ["SRC000003"],
        }
    ],
    "references": [],
    "uncertainties": [],
    "repetitions": [
        {
            "repetition_id": "rep_a",
            "character": "development",
            "description": (
                "L'affirmation initiale est reprise puis développée, ce n'est "
                "pas un doublon."
            ),
            "idea_refs": ["idea_7", "banana"],
            "source_refs": ["SRC000002", "SRC000005"],
        }
    ],
    "author_voice_profile": {
        "tone": ["didactique", "encourageant"],
        "register": "langue parlée accessible",
        "sentence_style": "phrases courtes, rythme oral",
        "rhetorical_patterns": [
            "reprise d'une formule pour insister",
            "opposition entre supprimer et traverser",
        ],
        "use_of_questions": "peu de questions, surtout des affirmations",
        "use_of_repetition": "reprise volontaire des formules centrales",
        "use_of_examples": "une anecdote vécue par idée principale",
        "direct_address": "s'adresse directement à l'auditoire au vous",
        "teaching_style": "affirmation puis illustration",
        "distinctive_traits": ["images concrètes du quotidien"],
    },
}


def fake_analysis_payload(**overrides) -> dict:
    """
    Copie de la réponse simulée de référence, éventuellement surchargée.

    La copie est profonde : un test qui modifie une collection ne doit pas
    contaminer les suivants.
    """
    payload = copy.deepcopy(_BASE_PAYLOAD)
    payload.update(copy.deepcopy(overrides))

    return payload


def fake_compact_analysis_payload(**overrides) -> dict:
    """Réponse provider compacte correspondant au scénario de référence."""
    from app.source_analysis.compact_reconstructor import to_compact_provider_payload

    return to_compact_provider_payload(fake_analysis_payload(**overrides))


def fake_ultra_analysis_payload(**overrides) -> dict:
    """Réponse provider ultra-compact correspondant au scénario de référence."""
    from app.source_analysis.ultra_compact_schema import to_ultra_transport_payload

    return to_ultra_transport_payload(fake_compact_analysis_payload(**overrides))


def fake_analysis_text(**overrides) -> str:
    """Réponse simulée sérialisée au contrat provider ultra-compact."""
    return json.dumps(fake_ultra_analysis_payload(**overrides), ensure_ascii=False)


def fake_engine(
    payload: dict | str | None = None,
    *,
    input_tokens: int | None = 12_000,
    output_tokens: int | None = 2_400,
    script=None,
    **kwargs,
) -> FakeAIEngine:
    """
    Moteur simulé renvoyant une analyse programmée.

    Les compteurs de tokens par défaut sont non nuls : c'est ce qui permet de
    vérifier que le coût enregistré vient bien de l'usage RAPPORTÉ et non d'un
    recalcul local.
    """
    if script is not None:
        return FakeAIEngine(script=script, **kwargs)

    if payload is None:
        text = fake_analysis_text()
    elif isinstance(payload, str):
        text = payload
    else:
        from app.source_analysis.compact_reconstructor import looks_like_canonical_raw
        from app.source_analysis.ultra_compact_schema import (
            looks_like_compact_dto,
            looks_like_ultra_transport,
            to_ultra_transport_payload,
        )

        if looks_like_ultra_transport(payload) and not looks_like_compact_dto(payload):
            text = json.dumps(payload, ensure_ascii=False)
        elif looks_like_canonical_raw(payload):
            text = json.dumps(to_ultra_transport_payload(payload), ensure_ascii=False)
        else:
            text = json.dumps(payload, ensure_ascii=False)

    return FakeAIEngine(
        script=[
            FakeReply(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason="stop",
                request_id="req_fake_001",
            )
        ],
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Environnement de projet isolé
# ---------------------------------------------------------------------------

@dataclass
class AnalysisEnv:
    """Projet V2 complet dans tmp_path : transcript publié, sortie vide."""

    project_name: str
    sortie: Path
    transcripts_dir: Path
    transcript_path: Path
    document: TranscriptDocument

    @property
    def source_map_path(self) -> Path:
        from app.source_analysis.writer import source_map_path

        return source_map_path(self.project_name)

    @property
    def partial_path(self) -> Path:
        from app.source_analysis.writer import partial_path

        return partial_path(self.source_map_path)

    def state(self) -> dict:
        from app.project_state import load_project_state

        return load_project_state(self.project_name)

    def source_map(self) -> dict:
        return json.loads(self.source_map_path.read_text(encoding="utf-8"))

    def rewrite_transcript(self, document: TranscriptDocument) -> Path:
        """Remplace le transcript publié — sert aux tests d'invalidation."""
        self.document = document

        return write_transcript(self.transcripts_dir, document)


@pytest.fixture
def analysis_env(tmp_path, monkeypatch) -> AnalysisEnv:
    """
    Projet isolé pour la Phase 3.

    `sortie/` est redirigé dans tmp_path pour les trois modules qui le
    connaissent : l'état projet, l'emplacement V2 du Source Map et le rapport.
    Aucun test ne peut donc écrire dans le vrai répertoire de sortie, ni lire un
    projet réel comme pastoral_retreat.
    """
    import app.project_state as project_state
    import app.report_service as report_service
    import app.source_analysis.writer as writer

    sortie = tmp_path / "sortie"
    sortie.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(project_state, "SORTIE_DIR", sortie)
    monkeypatch.setattr(report_service, "SORTIE_DIR", sortie)
    monkeypatch.setattr(writer, "SORTIE_DIR", sortie)

    project_name = "demo_analysis"
    document = build_transcript_document(project_name=project_name)
    transcripts_dir = sortie / project_name / "transcripts"
    transcript_path = write_transcript(transcripts_dir, document)

    return AnalysisEnv(
        project_name=project_name,
        sortie=sortie,
        transcripts_dir=transcripts_dir,
        transcript_path=transcript_path,
        document=document,
    )
