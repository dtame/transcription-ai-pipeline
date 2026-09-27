"""
Vocabulaire fermé et seuils déterministes de la Phase 3A.2A (§2-§18).

Rien ici ne recalcule une classification sémantique : ce module décrit
uniquement la COUCHE DE DÉCISION (politiques A/B/C) posée par-dessus la
classification déjà produite par la Phase 3A.1.2B.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Classification sémantique (réexport — jamais redéfinie, §10 de 3A.1.2B et
# principe de non-duplication déjà appliqué par app.semantic_batch.models)
# ---------------------------------------------------------------------------

from app.semantic_canary.models import (  # noqa: F401
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_TRANSLATION_BEFORE,
    CLASSIFICATION_UNCERTAIN,
    CLASSIFICATIONS,
)

TRANSLATION_CLASSIFICATIONS = frozenset(
    {CLASSIFICATION_TRANSLATION_BEFORE, CLASSIFICATION_TRANSLATION_AFTER}
)

# ---------------------------------------------------------------------------
# Origine sémantique d'un bloc (§6-7) — jamais mélangée silencieusement
# ---------------------------------------------------------------------------

ORIGIN_SEMANTIC_BATCH = "SEMANTIC_BATCH"
ORIGIN_PHASE_3A1_RESOLVED = "PHASE_3A1_RESOLVED"
ORIGIN_NO_ENGLISH_CONTEXT = "NO_ENGLISH_CONTEXT"

SEMANTIC_ORIGINS = (
    ORIGIN_SEMANTIC_BATCH,
    ORIGIN_PHASE_3A1_RESOLVED,
    ORIGIN_NO_ENGLISH_CONTEXT,
)

# Statuts language_blocks.json (semantic_review_status) correspondants.
STATUS_NEEDED = "NEEDED"
STATUS_ALREADY_RESOLVED = "ALREADY_RESOLVED"
STATUS_NO_ENGLISH_CONTEXT = "NO_ENGLISH_CONTEXT"

ORIGIN_BY_REVIEW_STATUS = {
    STATUS_NEEDED: ORIGIN_SEMANTIC_BATCH,
    STATUS_ALREADY_RESOLVED: ORIGIN_PHASE_3A1_RESOLVED,
    STATUS_NO_ENGLISH_CONTEXT: ORIGIN_NO_ENGLISH_CONTEXT,
}

# ---------------------------------------------------------------------------
# Décision d'application (§2, §21) — vocabulaire fermé
# ---------------------------------------------------------------------------

DECISION_AUTO_REMOVE = "AUTO_REMOVE"
DECISION_HUMAN_REVIEW = "HUMAN_REVIEW"
DECISION_KEEP = "KEEP"

DECISIONS = (DECISION_AUTO_REMOVE, DECISION_HUMAN_REVIEW, DECISION_KEEP)

# ---------------------------------------------------------------------------
# Politiques simulées (§8) — hypothèses, jamais une politique choisie
# ---------------------------------------------------------------------------

POLICY_A = "POLICY_A"
POLICY_B = "POLICY_B"
POLICY_C = "POLICY_C"

POLICY_IDS = (POLICY_A, POLICY_B, POLICY_C)

POLICY_LABELS = {
    POLICY_A: "ULTRA_CONSERVATIVE",
    POLICY_B: "CONSERVATIVE",
    POLICY_C: "BROADER",
}

# §9 : POLICY_C ne doit jamais être présentée comme recommandée/choisie.
POLICY_C_DISCLAIMER = (
    "POLICY_C est une SIMULATION servant à mesurer l'effet d'une politique "
    "moins restrictive. Elle n'est ni recommandée, ni approuvée, ni "
    "sélectionnée (§9)."
)

# Seuils exacts de chaque politique (§8) — un seul endroit où les lire.
POLICY_A_MIN_CONFIDENCE = 0.95
POLICY_A_MAX_WORDS = 30

POLICY_B_MIN_CONFIDENCE = 0.90
POLICY_B_MAX_WORDS = 30

POLICY_C_MIN_CONFIDENCE = 0.85
POLICY_C_MAX_WORDS = 60

# §15 : raison fixe pour les 15 ALREADY_RESOLVED, dans les trois politiques.
LEGACY_REASON_CODE = "LEGACY_RESOLVED_REQUIRES_POLICY_CONFIRMATION"

# Comptes attendus du projet réel — utilisés par le CLI uniquement, jamais
# figés dans le runner (qui reste générique pour les fixtures de test).
REAL_PROJECT_NAME = "pastoral_retreat_v2_validation"
REAL_PROJECT_EXPECTED_TOTAL = 333
REAL_PROJECT_EXPECTED_SEMANTIC_BATCH = 314
REAL_PROJECT_EXPECTED_PHASE_3A1_RESOLVED = 15
REAL_PROJECT_EXPECTED_NO_ENGLISH_CONTEXT = 4

# §16 : raison fixe pour les 4 NO_ENGLISH_CONTEXT, dans les trois politiques.
NO_ENGLISH_CONTEXT_REASON_CODE = "NO_ENGLISH_CONTEXT"

# §17 : raison fixe NOT_TRANSLATION.
NOT_TRANSLATION_REASON_CODE = "NOT_TRANSLATION_ALWAYS_KEEP"

# §18 : raison fixe UNCERTAIN — absence de preuve suffisante = conservation.
UNCERTAIN_REASON_CODE = "UNCERTAIN_INSUFFICIENT_EVIDENCE_ALWAYS_KEEP"

# ---------------------------------------------------------------------------
# Risk flags (§11) — valeurs minimales imposées, vocabulaire fermé de ce
# paquet (des valeurs supplémentaires documentées peuvent s'ajouter, jamais
# remplacer celles-ci).
# ---------------------------------------------------------------------------

RISK_HIGH_RISK_EXISTING = "HIGH_RISK_EXISTING"
RISK_LOW_CONFIDENCE = "LOW_CONFIDENCE"
RISK_MULTI_SRC = "MULTI_SRC"
RISK_LONG_BLOCK = "LONG_BLOCK"
RISK_MEDIUM_BLOCK = "MEDIUM_BLOCK"
RISK_BRIDGE_PRESENT = "BRIDGE_PRESENT"
RISK_EXTRA_CONTENT_SIGNAL = "EXTRA_CONTENT_SIGNAL"
RISK_LEGACY_RESOLVED = "LEGACY_RESOLVED"
RISK_NO_ENGLISH_CONTEXT = "NO_ENGLISH_CONTEXT"
RISK_FORMER_ALL_KEEP = "FORMER_ALL_KEEP"
RISK_FORMER_REVIEW = "FORMER_REVIEW"
RISK_TRANSLATION_AFTER = "TRANSLATION_AFTER"
RISK_OTHER_STRUCTURE = "OTHER_STRUCTURE"

RISK_FLAGS = (
    RISK_HIGH_RISK_EXISTING,
    RISK_LOW_CONFIDENCE,
    RISK_MULTI_SRC,
    RISK_LONG_BLOCK,
    RISK_MEDIUM_BLOCK,
    RISK_BRIDGE_PRESENT,
    RISK_EXTRA_CONTENT_SIGNAL,
    RISK_LEGACY_RESOLVED,
    RISK_NO_ENGLISH_CONTEXT,
    RISK_FORMER_ALL_KEEP,
    RISK_FORMER_REVIEW,
    RISK_TRANSLATION_AFTER,
    RISK_OTHER_STRUCTURE,
)

# §32 : seuil LOW_CONFIDENCE — repris identique au seuil déjà publié par la
# Phase 3A.1.2B pour "TRANSLATION_* avec confidence < 0.90" (cohérence des
# nombres déjà communiqués dans le rapport précédent, §1 du présent cahier).
LOW_CONFIDENCE_THRESHOLD = 0.90

# §12 : bornes exactes LONG_BLOCK / MEDIUM_BLOCK.
LONG_BLOCK_WORD_THRESHOLD = 60
MEDIUM_BLOCK_MIN_WORDS = 31
MEDIUM_BLOCK_MAX_WORDS = 60

# Structures reconnues (§14 rapport 3A.1.2B) — tout le reste (ex. "OTHER",
# utilisé par les blocs NO_ENGLISH_CONTEXT) déclenche OTHER_STRUCTURE.
KNOWN_BILINGUAL_STRUCTURES = ("EN_FR_EN", "EN_FR", "FR_EN")

# Statuts Phase 3A.1 pertinents pour FORMER_ALL_KEEP / FORMER_REVIEW (§13-14).
PHASE_3A1_ALL_KEEP = "ALL_KEEP"
PHASE_3A1_ALL_REVIEW = "ALL_REVIEW"
PHASE_3A1_HAS_REVIEW = "HAS_REVIEW"
PHASE_3A1_ALL_REMOVE = "ALL_REMOVE"

FORMER_REVIEW_STATUSES = (PHASE_3A1_ALL_REVIEW, PHASE_3A1_HAS_REVIEW)

# ---------------------------------------------------------------------------
# EXTRA_CONTENT_SIGNAL (§10) — liste déterministe de termes/patterns
# ---------------------------------------------------------------------------
#
# Ce mécanisme n'invente aucune classification : il extrait un signal de
# PRUDENCE depuis la justification déjà écrite par le modèle en Phase
# 3A.1.2B (`reason`), recherché en sous-chaîne, insensible à la casse.
#
# Deux groupes, documentés séparément :
#
# 1. Termes anglais cités TEXTUELLEMENT par le cahier des charges (§10) —
#    conservés même si les justifications observées sont rédigées en
#    français (aucune n'a matché lors de l'exploration réelle de
#    semantic_translation_classification.json, mais un futur run pourrait
#    produire des justifications anglaises).
# 2. Équivalents français CONSTATÉS dans les justifications réelles du
#    projet pastoral_retreat_v2_validation lors de l'exploration
#    exploratoire de cette phase (recherche documentée, pas une supposition) :
#    "ajout"/"ajoute"/"ajoutent"/"ajouté"/"ajoutée" (added/adds/additional),
#    "commentaire" (commentary), "développe"/"developpe" (expands/expansion,
#    couvre aussi "développement"/"developpement" par sous-chaîne),
#    "non présent"/"non present" (contains material not present),
#    "partiellement" (partially translates), "traduction partielle"
#    (partial translation), "nouvelle idée"/"nouvelle idee" (new idea),
#    "plus que" (more than), "supplémentaire"/"supplementaire" (additional
#    content). "pas simplement"/"pas seulement" (not merely/not simply)
#    n'ont, eux, jamais matché sur ce jeu de données réel mais restent inclus
#    pour la fidélité au cahier des charges (§10) et la robustesse à de
#    futures données.

EXTRA_CONTENT_SIGNAL_TERMS = (
    # --- Termes anglais explicitement cités par le cahier des charges §10 ---
    "additional",
    "extra",
    "adds",
    "added",
    "commentary",
    "expands",
    "expansion",
    "new idea",
    "more than",
    "not merely",
    "not simply",
    "partial translation",
    "partially translates",
    "contains material not present",
    # --- Équivalents français constatés ou raisonnablement attendus -------
    "ajout",
    "commentaire",
    "développe",
    "developpe",
    "nouvelle idée",
    "nouvelle idee",
    "plus que",
    "pas simplement",
    "pas seulement",
    "traduction partielle",
    "partiellement",
    "contient du contenu",
    "non présent",
    "non present",
    "supplémentaire",
    "supplementaire",
)
