"""
Contrat de sortie de l'analyse structurelle — language_blocks.json.

Même séparation que app/language_cleanup/models.py : ce module décrit
uniquement CE QUE LE MANIFESTE EST (dataclasses, to_dict). La fabrication vit
dans builder.py, le jugement dans validator.py.

Aucun champ non déterministe (horodatage, UUID) n'apparaît dans ce contrat,
à l'exception de `analysis_duration_seconds` — une mesure d'exécution,
explicitement exclue de `canonical_dict()` (§34 du cahier des charges : le
déterminisme ne porte jamais sur un temps mesuré), comme
`audit_duration_seconds` l'est déjà dans app/language_cleanup/models.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Vocabulaires fermés
# ---------------------------------------------------------------------------

STRUCTURE_EN_FR = "EN_FR"
STRUCTURE_FR_EN = "FR_EN"
STRUCTURE_EN_FR_EN = "EN_FR_EN"
STRUCTURE_FR_ISOLATED = "FR_ISOLATED"
STRUCTURE_NON_EN_CONTEXT = "NON_EN_CONTEXT"
STRUCTURE_OTHER = "OTHER"

STRUCTURES = (
    STRUCTURE_EN_FR,
    STRUCTURE_FR_EN,
    STRUCTURE_EN_FR_EN,
    STRUCTURE_FR_ISOLATED,
    STRUCTURE_NON_EN_CONTEXT,
    STRUCTURE_OTHER,
)

DIRECTION_BEFORE = "BEFORE"
DIRECTION_AFTER = "AFTER"
DIRECTION_BOTH = "BOTH"
DIRECTION_NONE = "NONE"

CANDIDATE_DIRECTIONS = (
    DIRECTION_BEFORE,
    DIRECTION_AFTER,
    DIRECTION_BOTH,
    DIRECTION_NONE,
)

STATUS_ALL_REMOVE = "ALL_REMOVE"
STATUS_HAS_REMOVE = "HAS_REMOVE"
STATUS_ALL_REVIEW = "ALL_REVIEW"
STATUS_HAS_REVIEW = "HAS_REVIEW"
STATUS_ALL_KEEP = "ALL_KEEP"
STATUS_MIXED_DECISIONS = "MIXED_DECISIONS"

PHASE_3A1_STATUSES = (
    STATUS_ALL_REMOVE,
    STATUS_HAS_REMOVE,
    STATUS_ALL_REVIEW,
    STATUS_HAS_REVIEW,
    STATUS_ALL_KEEP,
    STATUS_MIXED_DECISIONS,
)

SEMANTIC_STATUS_NEEDED = "NEEDED"
SEMANTIC_STATUS_ALREADY_RESOLVED = "ALREADY_RESOLVED"
SEMANTIC_STATUS_NO_ENGLISH_CONTEXT = "NO_ENGLISH_CONTEXT"

SEMANTIC_REVIEW_STATUSES = (
    SEMANTIC_STATUS_NEEDED,
    SEMANTIC_STATUS_ALREADY_RESOLVED,
    SEMANTIC_STATUS_NO_ENGLISH_CONTEXT,
)


# ---------------------------------------------------------------------------
# Contexte anglais local (avant ou après un bloc FR)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnglishContext:
    """
    Petit bloc anglais local, cohérent, adjacent à un bloc FR (§12-14).

    `truncated` vaut True lorsque le run anglais complet dépassait un des
    plafonds MAX_CONTEXT_* (app.language_blocks.constants) et a été réduit à
    la portion la plus proche du bloc FR — jamais l'inverse.
    """

    source_refs: tuple[str, ...]
    start_seconds: float
    end_seconds: float
    text: str
    word_count: int
    segment_count: int
    distance_segments: int
    distance_seconds: float
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "source_refs": list(self.source_refs),
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
            "word_count": self.word_count,
            "segment_count": self.segment_count,
            "distance_segments": self.distance_segments,
            "distance_seconds": self.distance_seconds,
            "truncated": self.truncated,
        }


# ---------------------------------------------------------------------------
# Un bloc FR
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LanguageBlock:
    """Une intervention française continue et son contexte structurel."""

    block_id: str
    audio_id: str

    start_seconds: float
    end_seconds: float

    all_source_refs: tuple[str, ...]
    fr_source_refs: tuple[str, ...]
    bridge_source_refs: tuple[str, ...]

    text: str
    word_count: int
    segment_count: int
    fr_segment_count: int

    structure: str
    candidate_direction: str

    english_before: EnglishContext | None
    english_after: EnglishContext | None

    phase_3a1_decisions: tuple[tuple[str, str], ...]
    phase_3a1_remove_refs: tuple[str, ...]
    phase_3a1_review_refs: tuple[str, ...]
    phase_3a1_keep_refs: tuple[str, ...]
    phase_3a1_status: str

    already_resolved: bool
    needs_semantic_review: bool
    semantic_review_status: str

    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "audio_id": self.audio_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "all_source_refs": list(self.all_source_refs),
            "fr_source_refs": list(self.fr_source_refs),
            "bridge_source_refs": list(self.bridge_source_refs),
            "text": self.text,
            "word_count": self.word_count,
            "segment_count": self.segment_count,
            "fr_segment_count": self.fr_segment_count,
            "structure": self.structure,
            "candidate_direction": self.candidate_direction,
            "english_before": (
                self.english_before.to_dict() if self.english_before else None
            ),
            "english_after": (
                self.english_after.to_dict() if self.english_after else None
            ),
            "phase_3a1_decisions": {
                ref: decision for ref, decision in self.phase_3a1_decisions
            },
            "phase_3a1_remove_refs": list(self.phase_3a1_remove_refs),
            "phase_3a1_review_refs": list(self.phase_3a1_review_refs),
            "phase_3a1_keep_refs": list(self.phase_3a1_keep_refs),
            "phase_3a1_status": self.phase_3a1_status,
            "already_resolved": self.already_resolved,
            "needs_semantic_review": self.needs_semantic_review,
            "semantic_review_status": self.semantic_review_status,
        }


# ---------------------------------------------------------------------------
# Statistiques (§22-28 du cahier des charges)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GapAudit:
    """Distribution mesurée des gaps FR->FR adjacents (§8)."""

    pair_count: int = 0
    median_gap: float = 0.0
    p90_gap: float = 0.0
    p95_gap: float = 0.0
    p99_gap: float = 0.0
    max_gap: float = 0.0
    threshold_retained: float = 0.0

    def to_dict(self) -> dict:
        return {
            "pair_count": self.pair_count,
            "median_gap": self.median_gap,
            "p90_gap": self.p90_gap,
            "p95_gap": self.p95_gap,
            "p99_gap": self.p99_gap,
            "max_gap": self.max_gap,
            "threshold_retained": self.threshold_retained,
        }


@dataclass(frozen=True)
class BlocksManifestStats:
    """
    Toutes les statistiques obligatoires (§22-28), portées à plat.

    `to_dict()` fixe l'ordre de sérialisation. `analysis_duration_seconds` est
    le seul champ exclu de la vue canonique (déterminisme, §34).
    """

    total_FR_segments: int = 0
    total_FR_blocks: int = 0
    single_segment_blocks: int = 0
    multi_segment_blocks: int = 0
    max_FR_segments_in_block: int = 0
    median_FR_segments_per_block: float = 0.0
    mean_FR_segments_per_block: float = 0.0
    total_FR_words: int = 0

    structure_distribution: dict = field(default_factory=dict)
    candidate_direction_distribution: dict = field(default_factory=dict)
    phase_3a1_status_distribution: dict = field(default_factory=dict)
    semantic_review_distribution: dict = field(default_factory=dict)

    by_audio: tuple[dict, ...] = field(default_factory=tuple)
    temporal_quartiles: tuple[dict, ...] = field(default_factory=tuple)

    block_size_segments_histogram: dict = field(default_factory=dict)
    block_size_words_histogram: dict = field(default_factory=dict)

    context_availability: dict = field(default_factory=dict)

    gap_audit: GapAudit = field(default_factory=GapAudit)

    ai_estimation: dict = field(default_factory=dict)

    analysis_duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_FR_segments": self.total_FR_segments,
            "total_FR_blocks": self.total_FR_blocks,
            "single_segment_blocks": self.single_segment_blocks,
            "multi_segment_blocks": self.multi_segment_blocks,
            "max_FR_segments_in_block": self.max_FR_segments_in_block,
            "median_FR_segments_per_block": self.median_FR_segments_per_block,
            "mean_FR_segments_per_block": self.mean_FR_segments_per_block,
            "total_FR_words": self.total_FR_words,
            "structure_distribution": dict(self.structure_distribution),
            "candidate_direction_distribution": dict(
                self.candidate_direction_distribution
            ),
            "phase_3a1_status_distribution": dict(self.phase_3a1_status_distribution),
            "semantic_review_distribution": dict(self.semantic_review_distribution),
            "by_audio": [dict(entry) for entry in self.by_audio],
            "temporal_quartiles": [dict(entry) for entry in self.temporal_quartiles],
            "block_size_segments_histogram": dict(self.block_size_segments_histogram),
            "block_size_words_histogram": dict(self.block_size_words_histogram),
            "context_availability": dict(self.context_availability),
            "gap_audit": self.gap_audit.to_dict(),
            "ai_estimation": dict(self.ai_estimation),
            "analysis_duration_seconds": self.analysis_duration_seconds,
        }


# ---------------------------------------------------------------------------
# Le manifeste complet
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlocksConfiguration:
    """Recopie des seuils appliqués (app.language_blocks.constants)."""

    fr_gap_split_threshold_seconds: float
    bridge_max_run_segments: int
    bridge_max_words_per_segment: int
    bridge_max_duration_seconds: float
    bridge_max_total_gap_seconds: float
    context_window_max_block_skip: int
    max_context_segments: int
    max_context_words: int
    max_context_seconds: float

    def to_dict(self) -> dict:
        return {
            "fr_gap_split_threshold_seconds": self.fr_gap_split_threshold_seconds,
            "bridge_max_run_segments": self.bridge_max_run_segments,
            "bridge_max_words_per_segment": self.bridge_max_words_per_segment,
            "bridge_max_duration_seconds": self.bridge_max_duration_seconds,
            "bridge_max_total_gap_seconds": self.bridge_max_total_gap_seconds,
            "context_window_max_block_skip": self.context_window_max_block_skip,
            "max_context_segments": self.max_context_segments,
            "max_context_words": self.max_context_words,
            "max_context_seconds": self.max_context_seconds,
        }


@dataclass(frozen=True)
class LanguageBlocksManifest:
    """language_blocks.json — manifeste complet de l'analyse structurelle."""

    transcript_id: str
    transcript_sha256: str
    language_cleanup_sha256: str
    configuration: BlocksConfiguration
    stats: BlocksManifestStats
    blocks: tuple[LanguageBlock, ...] = field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "transcript_id": self.transcript_id,
            "transcript_sha256": self.transcript_sha256,
            "language_cleanup_sha256": self.language_cleanup_sha256,
            "configuration": self.configuration.to_dict(),
            "stats": self.stats.to_dict(),
            "blocks": [block.to_dict() for block in self.blocks],
        }

    def canonical_dict(self) -> dict:
        """
        Vue utilisée pour comparer deux exécutions (déterminisme, §34).

        Exclut `stats.analysis_duration_seconds`, seul champ du manifeste qui
        dépend de la machine et de l'instant d'exécution plutôt que du
        contenu analysé.
        """
        payload = self.to_dict()
        stats = dict(payload["stats"])
        stats.pop("analysis_duration_seconds", None)
        payload["stats"] = stats
        return payload
