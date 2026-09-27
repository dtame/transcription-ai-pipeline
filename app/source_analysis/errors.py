"""
Erreurs propres au Source Analyzer.

Séparées des erreurs de la couche IA (app/ai/errors.py) à dessein : un échec
métier de Phase 3 n'est pas un incident de transport et ne doit surtout pas
être rejoué comme tel. La politique de rejeu de la Phase 2 ne connaît que
AITransientError ; rien d'ici n'en hérite.

Hiérarchie :

    SourceAnalysisError                     racine Phase 3
        SourceTranscriptError               transcript V2 absent ou hors contrat
        SourceTranscriptNotSubstantial      rien d'analysable dans la source
        SourceAnalysisContextExceeded       transcript plus grand que le budget
        SourceMapValidationError            source_map hors contrat
            SourceMapEditorialLeakError     structure de livre dans le Source Map
        MaxRealCallsExceededError           second appel réel tenté
        ExistingSourceMapConflictError      source_map existant non réutilisable
        SourceMapTruncatedError             finish_reason de troncature
        SourceAnalysisWindowPlannerConfigError  config WindowPlannerV2 invalide
        SourceAnalysisEmptyTranscript       transcript sans SRC présent
        SourceAnalysisWindowTooLarge        un SRC unique dépasse le hard max
        SourceAnalysisWindowPlanError       plan de fenêtres invalide
        WindowAnalysisError                 racine analyse d'une fenêtre
            WindowTransportWriteError       persistance transport échouée
            WindowTransportValidationError  transport invalide après persistance
            WindowSourceRefError            SRC hors fenêtre / context-only
            WindowResultValidationError     résultat fenêtre invalide
            WindowSemanticCapacityExceeded  overflow sémantique signalé
            WindowGranularityLimitExceeded  plafonds durs de granularité
        WindowOrchestrationError            cache / resume / budget
            WindowsIncompleteError          ALL_WINDOWS_READY refusé
            WindowCacheAmbiguityError       plusieurs candidats pour une fenêtre
            WindowCacheCorruptError         JSON cache illisible
        ConsolidationError                  racine consolidation 3B.7.4
            ConsolidationContextExceeded    input trop grand, pas de troncature
            ConsolidationInputError         ConsolidationInput invalide
            ConsolidationTransportWriteError  persistance transport échouée
            ConsolidationTransportValidationError  transport invalide
            ConsolidationResultValidationError    résultat invalide
        HybridReconstructionError           reconstruction canonique 3B.7.5
            HybridPreconditionError         identités / hashes / ALL_WINDOWS_READY
        SmallWindowPlanningError            planner candidat v2.1-small
        ConsolidationCapacityExceeded       input consolidation hors garde (local)
        RegionalConsolidationValidationError  résultat régional invalide
        HierarchyDepthExceeded              profondeur de consolidation dépassée
        HierarchyCapacityExceeded           global après régional hors garde
"""

from __future__ import annotations


class SourceAnalysisError(RuntimeError):
    """Racine des échecs du Source Analyzer."""


class SourceTranscriptError(SourceAnalysisError):
    """transcripts/transcript_data.json est absent, illisible ou hors contrat."""


class SourceTranscriptProvenanceError(SourceTranscriptError):
    """
    Un transcript DERIVED a été présenté sans preuve de provenance, ou
    avec une preuve incohérente (hash, jeu retiré, survivant modifié).

    Fail-closed : aucun repli silencieux vers « trous autorisés ».
    """


class SourceTranscriptNotSubstantial(SourceAnalysisError):
    """
    Le transcript ne contient pas assez de discours pour être analysé.

    Refus explicite plutôt que publication d'un Source Map vide : un fichier
    avec main_theme="" et ideas=[] serait indistinguable d'une analyse ratée.
    """

    def __init__(self, message: str, *, word_count: int, segment_count: int):
        self.word_count = int(word_count)
        self.segment_count = int(segment_count)
        super().__init__(message)


class SourceAnalysisContextExceeded(SourceAnalysisError):
    """
    La représentation complète du transcript ne tient pas dans le budget
    d'entrée utilisable du modèle.

    Levée AVANT tout appel : aucune troncature, aucune analyse partielle
    présentée comme globale. Porte le budget calculé et le découpage technique
    qui serait nécessaire, pour que la décision suivante soit informée.
    """

    def __init__(self, message: str, *, plan):
        self.plan = plan
        super().__init__(message)


class SourceMapValidationError(SourceAnalysisError):
    """
    Le Source Map ne satisfait pas son contrat : rien ne doit être publié.

    Collecte toutes les violations plutôt que de s'arrêter à la première, comme
    le fait déjà TranscriptValidationError en Phase 1.
    """

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__(
            f"{len(self.errors)} violation(s) du contrat source_map 1.0 : "
            + " | ".join(self.errors)
        )


class MaxRealCallsExceededError(SourceAnalysisError):
    """
    Un second appel réel a été tenté depuis le même garde-fou.

    Cette exécution n'autorise qu'un seul engine.generate() vers un
    fournisseur réel. Le compteur est incrémenté AVANT l'appel : un échec
    ne rend jamais le droit d'en faire un deuxième.
    """


class ExistingSourceMapConflictError(SourceAnalysisError):
    """
    Un source_map.json existe déjà et n'est pas un cache valide de cette
    signature clean. L'écraser silencieusement ferait perdre un artefact.
    """


class SourceMapTruncatedError(SourceAnalysisError):
    """
    Le fournisseur a arrêté la génération pour cause de plafond de tokens.

    Même si le JSON est partiellement parseable, rien n'est publié.
    """


class SourceMapEditorialLeakError(SourceMapValidationError):
    """
    Une structure de livre s'est glissée dans le Source Map.

    Cas distinct parce que le diagnostic est différent : ce n'est pas un champ
    mal rempli, c'est la frontière Phase 3 / Phase 4 qui a été franchie.
    """

    def __init__(self, fields, *, location: str = "source_map"):
        self.fields = tuple(fields)
        self.location = location
        super().__init__(
            [
                f"champ éditorial interdit dans {location} : « {name} » — "
                "chapitres, sections, titres et table des matières appartiennent "
                "à la Phase 4 (Editorial Planner)"
                for name in self.fields
            ]
        )


class SourceAnalysisWindowPlannerConfigError(SourceAnalysisError):
    """Configuration de WindowPlannerV2 invalide (budget, version, politique)."""


class SourceAnalysisEmptyTranscript(SourceAnalysisError):
    """
    Aucun SRC présent : un plan de fenêtres vide n'est pas un résultat valide.

    Fail-closed : pas de WIN001 vide.
    """


class SourceAnalysisWindowTooLarge(SourceAnalysisError):
    """
    Un seul SRC, prompt inclus, dépasse hard_max_input_tokens.

    Jamais scindé, jamais tronqué. L'échec est explicite.
    """

    def __init__(
        self,
        message: str,
        *,
        src_id: str,
        estimated_tokens: int,
        hard_max_input_tokens: int,
    ):
        self.src_id = src_id
        self.estimated_tokens = int(estimated_tokens)
        self.hard_max_input_tokens = int(hard_max_input_tokens)
        super().__init__(message)


class SourceAnalysisWindowPlanError(SourceAnalysisError):
    """Le plan de fenêtres viole son contrat structurel."""


class WindowAnalysisError(SourceAnalysisError):
    """Échec de l'analyse sémantique d'une fenêtre (pipeline 3B.7.2)."""


class WindowTransportWriteError(WindowAnalysisError):
    """
    La persistance du transport exact a échoué.

    Fail-closed : aucun décodage, aucune validation de résultat, aucun
    result.json. Le pipeline s'arrête avant le decoder.
    """


class WindowTransportValidationError(WindowAnalysisError):
    """
    Le transport persisté viole semantic-transport-v1 ou le decoder
    fail-closed.

    transport.json peut exister. result.json ne doit pas être publié.
    """


class WindowSourceRefError(WindowAnalysisError):
    """
    Une source_ref est hors fenêtre, absente (SRC supprimé / gap), ou
    uniquement CONTEXT-ONLY pour un record substantif.
    """


class WindowResultValidationError(WindowAnalysisError):
    """Le WindowSemanticResult viole son contrat local."""


class WindowSemanticCapacityExceeded(WindowAnalysisError):
    """
    Le modèle a signalé analysis_capacity_exceeded.

    transport.json peut exister. result.json ne doit pas être publié.
    Le résultat n'est pas READY. Aucun retry.
    """


class WindowGranularityLimitExceeded(WindowAnalysisError):
    """
    Le transport dépasse un plafond dur de granularité (counts / texte).

    Distinct d'une erreur de parse ou de schéma. transport.json peut
    exister. result.json ne doit pas être publié. Aucun retry.
    Aucune troncature locale des chaînes.
    """


class WindowOrchestrationError(SourceAnalysisError):
    """Échec d'orchestration multi-fenêtres (cache / resume / budget)."""


class WindowsIncompleteError(WindowOrchestrationError):
    """
    Le jeu de fenêtres n'est pas ALL_WINDOWS_READY.

    La consolidation future ne peut pas commencer. Aucun merge sémantique
    n'est tenté. Les fenêtres déjà valides restent réutilisables.
    """


class WindowCacheAmbiguityError(WindowOrchestrationError):
    """
    Plusieurs artefacts candidats pour la même fenêtre / signature.

    Fail-closed : on ne choisit pas le fichier le plus récent.
    """


class WindowCacheCorruptError(WindowOrchestrationError):
    """transport.json / result.json / metadata.json illisible ou non objet."""


class ConsolidationError(SourceAnalysisError):
    """Échec de la consolidation sémantique globale (pipeline 3B.7.4)."""


class ConsolidationContextExceeded(ConsolidationError):
    """
    Le ConsolidationInput dépasse le budget d'entrée sûr.

    Fail-closed : aucune troncature, aucun drop de record, aucune
    hiérarchie map-reduce automatique.
    """

    def __init__(
        self,
        message: str,
        *,
        estimated_tokens: int,
        safe_input_budget: int,
    ):
        self.estimated_tokens = int(estimated_tokens)
        self.safe_input_budget = int(safe_input_budget)
        super().__init__(message)


class ConsolidationInputError(ConsolidationError):
    """Le ConsolidationInput viole son contrat (ordre, IDs, SRC, fuite)."""


class ConsolidationTransportWriteError(ConsolidationError):
    """
    La persistance du transport de consolidation a échoué.

    Fail-closed : aucun décodage, aucun ConsolidationSemanticResult.
    """


class ConsolidationTransportValidationError(ConsolidationError):
    """
    Le transport persisté viole consolidation-transport-v1 ou le decoder
    fail-closed.

    transport.json peut exister. result.json ne doit pas être publié.
    """


class ConsolidationResultValidationError(ConsolidationError):
    """Le ConsolidationSemanticResult viole son contrat local."""


class HybridReconstructionError(SourceAnalysisError):
    """
    Échec de reconstruction canonique hybride (3B.7.5).

    Purement structurel : aucune décision d'équivalence sémantique.
    Aucun appel IA.
    """


class HybridPreconditionError(HybridReconstructionError):
    """
    Préconditions de reconstruction non satisfaites — fail-closed.

    ALL_WINDOWS_READY, identités transcript/plan, hashes fenêtre,
    identité ConsolidationInput, ou ConsolidationSemanticResult périmé.
    """


class SmallWindowPlanningError(SourceAnalysisWindowPlanError):
    """
    Échec du planner candidat window-planner-v2.1-small.

    Distinct d'une erreur de parse provider. Aucune troncature SRC.
    Un SRC unique trop grand, un hard max irrespecté après remesure,
    ou un équilibrage impossible lèvent cette erreur.
    """


class ConsolidationCapacityExceeded(ConsolidationContextExceeded):
    """
    L'input de consolidation dépasse la garde.

    Échec de capacité locale — pas un échec provider. Aucune troncature.
    """


class RegionalConsolidationValidationError(ConsolidationResultValidationError):
    """Le résultat de consolidation régionale viole son contrat."""


class HierarchyDepthExceeded(ConsolidationError):
    """
    La profondeur de consolidation dépasse le plafond borné.

    WINDOW → optional REGIONAL → GLOBAL (2 niveaux). Pas de récursion.
    """


class HierarchyCapacityExceeded(ConsolidationCapacityExceeded):
    """
    Le ConsolidationInput global après un niveau régional dépasse encore
    la garde. Fail-closed. Pas de troisième niveau dans cette phase.
    """
