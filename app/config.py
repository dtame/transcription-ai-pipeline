"""
Configuration globale de TranscriptionAI.

Modèles Ollama recommandés pour 16 Go de RAM :
    qwen3:8b      -> modèle principal (correction, restructuration, Markdown)
    llama3.1:8b   -> alternatif stable
    mistral:7b    -> secours léger
    gemma3:12b    -> possible mais lent avec 16 Go RAM

Commandes d'installation :
    ollama pull qwen3:8b
    ollama pull llama3.1:8b
    ollama pull mistral:7b
"""

# =========================
# Transcription audio
# =========================

SUPPORTED_EXTENSIONS = {".ogg", ".mp3", ".wav", ".m4a"}

ALLOWED_LANGUAGES = {"en", "fr"}
# Langues principales attendues des projets.
# N'est PLUS appliquée par la transcription depuis la Phase 1 : la langue
# réellement détectée par Whisper est conservée et le contenu n'est jamais
# retranscrit de force en anglais (voir contrat Transcript V2).
MODEL_NAME = "large-v3"
DEVICE = "cpu"
CHUNK_THRESHOLD_MINUTES = 60
CHUNK_DURATION_MINUTES = 10

# =========================
# Segmentation audio longue durée
# =========================

LONG_AUDIO_SEGMENTATION_ENABLED = True
# Si True, les fichiers dont la durée dépasse LONG_AUDIO_THRESHOLD_MINUTES
# sont découpés en segments avant transcription.
# Permet la reprise après interruption (veille, crash) au dernier segment non transcrit.

LONG_AUDIO_THRESHOLD_MINUTES = 30
# Durée minimale (en minutes) à partir de laquelle un fichier est traité en mode segmenté.

AUDIO_SEGMENT_MINUTES = 15
# Durée cible (en minutes) de chaque segment audio.

AUDIO_SEGMENT_OVERLAP_SECONDS = 10
# Chevauchement (en secondes) entre deux segments consécutifs.
# Évite les pertes de mots aux frontières de segment.
# Exemple : segment 2 commence 10 secondes avant la fin du segment 1.

SEGMENT_TRANSCRIPTS_ENABLED = True
# Si True, les transcripts individuels de chaque segment sont conservés
# dans sortie/<projet>/segment_transcripts/<stem>/ pour l'audit et la reprise.

# =========================
# Configuration IA
# =========================

AI_PROVIDER = "ollama"
# Valeurs possibles :
#   "ollama"    -> moteur principal recommandé (Ollama local)
#   "lmstudio"  -> LM Studio (API compatible OpenAI)
#   "openai"    -> API OpenAI cloud (nécessite clé API)
#   "anthropic" -> API Anthropic cloud (nécessite clé API)
#   "fake"      -> simulation locale pour les tests
# Ne concerne que les étapes SANS configuration dédiée : les quatre étapes
# éditoriales ont leur propre provider dans AI_STAGE_SETTINGS (voir plus bas).

AI_TASK = "clean_transcript"
# Tâches disponibles (voir app/prompt_manager.py) :
#   "clean_transcript" -> correction et structuration Markdown (défaut)
#   "summary"          -> résumé clair et structuré
#   "book_chapter"     -> transformation en chapitre de livre
#   "key_points"       -> extraction des idées principales
#   "classification"   -> classification documentaire

# =========================
# Ollama (moteur principal)
# =========================

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_TIMEOUT_SECONDS = 1200
OLLAMA_OPTIONS = {
    "temperature": 0.2,
    "num_ctx": 4096,
}

# =========================
# LM Studio
# =========================

LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
LMSTUDIO_MODEL = "local-model"
LMSTUDIO_TEMPERATURE = 0.2

# =========================
# OpenAI (cloud, optionnel)
# =========================

OPENAI_API_KEY = ""
# DÉPRÉCIÉ — doit rester vide. Ce fichier est versionné : aucune clé API ne
# doit y figurer. La clé est lue depuis la variable d'environnement
# OPENAI_API_KEY (ou un fichier .env local, ignoré par Git).
# Cette constante n'est consultée qu'en dernier recours, pour ne pas casser
# une installation V1 où elle aurait été renseignée localement.

OPENAI_MODEL = "gpt-4o-mini"
OPENAI_BASE_URL = None
OPENAI_TEMPERATURE = 0.2

# =========================
# Anthropic (cloud, optionnel)
# =========================

ANTHROPIC_MODEL = ""
# Volontairement vide : aucun nom de modèle cloud n'est supposé. Renseignez
# le modèle exact après avoir vérifié son nom et son tarif chez le
# fournisseur. La clé vient de la variable d'environnement ANTHROPIC_API_KEY.

ANTHROPIC_BASE_URL = None
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_TEMPERATURE = None

# =====================================================
# COUCHE IA COMMUNE (Phase 2)
# =====================================================
# Réglages partagés par tous les providers. Voir app/ai/ pour l'architecture.

AI_DEFAULT_TIMEOUT_SECONDS = 300
# Read timeout par défaut d'un appel IA, en secondes. Ollama conserve le sien
# (OLLAMA_TIMEOUT_SECONDS), plus long car un modèle local est plus lent.
# Ce n'est PAS un timeout total wall-clock : requests n'en fournit pas sur
# le chemin HTTP actuel. Surchargeable par étape / env sans modifier le code
# (voir AI_DEFAULT_CONNECT_TIMEOUT_SECONDS et AI_<STAGE>_READ_TIMEOUT_SECONDS).

AI_DEFAULT_CONNECT_TIMEOUT_SECONDS = 30
# Connect timeout par défaut, en secondes. Budget d'établissement TCP/TLS
# uniquement — pas une durée maximale de génération. Une valeur de l'ordre
# de quelques dizaines de secondes est volontaire : un read timeout long
# ne doit plus allonger le connect (cause locale du 3B Final).

AI_MAX_ATTEMPTS = 3
AI_RETRY_BASE_DELAY_SECONDS = 0.5
AI_RETRY_MAX_DELAY_SECONDS = 8.0
# Rejeu des seuls incidents transitoires (timeout, 429, 5xx, service
# injoignable). Une clé invalide ou une requête malformée ne sont jamais
# rejouées. max_attempts = 1 désactive le rejeu.

AI_CONTEXT_SAFETY_RATIO = 0.70
# Fraction de la fenêtre de contexte qu'une étape peut viser sans frôler la
# limite. Surchargeable par étape via AI_STAGE_SETTINGS. Il n'existe AUCUNE
# valeur universellement correcte : 0.70 est un défaut prudent, pas une
# vérité. La Phase 3 décidera comment le Source Analyzer dépense ce budget.

AI_FALLBACK_CONTEXT_WINDOW = 4096
AI_FALLBACK_MAX_OUTPUT_TOKENS = 1024
# Repli employé UNIQUEMENT pour un couple (provider, modèle) dont les
# capacités sont inconnues. Les capacités produites dans ce cas portent
# known=False : ce sont des hypothèses, pas des faits.

_ANTHROPIC_DOC_SOURCE = (
    "Anthropic official model documentation — vérifié le 2026-09-18"
)
_OPENAI_DOC_SOURCE = "OpenAI official model documentation — vérifié le 2026-09-18"

AI_MODEL_CAPABILITIES = {
    # Modèles de production retenus (Phase 2B). Valeurs relevées dans les
    # documentations officielles des fournisseurs le 2026-09-18 : ce sont des
    # faits datés, donc known=True, et non des hypothèses de repli.
    #
    # Seules des clés de modèle EXACTES sont déclarées, jamais "provider:*" :
    # un modèle non listé doit continuer de ressortir en known=False plutôt
    # que d'hériter des capacités d'un voisin.
    "anthropic:claude-sonnet-5": {
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "supports_structured_output": True,
        "supports_system_prompt": True,
        "supports_temperature": True,
        "known": True,
        "source": _ANTHROPIC_DOC_SOURCE,
    },
    "anthropic:claude-opus-5": {
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "supports_structured_output": True,
        "supports_system_prompt": True,
        "supports_temperature": True,
        "known": True,
        "source": _ANTHROPIC_DOC_SOURCE,
    },
    "openai:gpt-5.6-terra": {
        "context_window": 1_050_000,
        "max_output_tokens": 128_000,
        "supports_structured_output": True,
        "supports_system_prompt": True,
        # supports_temperature=False : le relevé de capacités de ce modèle
        # mentionne la sortie structurée et le system prompt, pas le réglage
        # de température. Aucun code ne consulte encore ce drapeau ; il vaut
        # False pour qu'une étape future ne parte pas du principe qu'elle peut
        # envoyer `temperature` sans l'avoir confirmé chez le fournisseur.
        "supports_temperature": False,
        "known": True,
        "source": _OPENAI_DOC_SOURCE,
    },
}
# Capacités vérifiées d'un modèle, prioritaires sur tout le reste.
# Clé "provider:model", ou "provider:*" pour tous les modèles d'un provider.
# Exemple :
#   AI_MODEL_CAPABILITIES = {
#       "ollama:qwen3:8b": {
#           "context_window": 32768,
#           "max_output_tokens": 8192,
#           "supports_structured_output": False,
#       },
#   }

AI_PRICING_ENTRIES = [
    # Tarifs des modèles de production retenus (Phase 2B), relevés dans les
    # documentations officielles des fournisseurs le 2026-09-18.
    {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "currency": "USD",
        "unit": "tokens",
        "input_cost_per_1m_tokens": 2.00,
        "output_cost_per_1m_tokens": 10.00,
        "is_local": False,
        "effective_date": "2026-09-18",
        "source": "Anthropic official pricing/model documentation",
        "verified": True,
    },
    {
        "provider": "anthropic",
        "model": "claude-opus-5",
        "currency": "USD",
        "unit": "tokens",
        "input_cost_per_1m_tokens": 5.00,
        "output_cost_per_1m_tokens": 25.00,
        "is_local": False,
        "effective_date": "2026-09-18",
        "source": "Anthropic official pricing/model documentation",
        "verified": True,
    },
    {
        "provider": "openai",
        "model": "gpt-5.6-terra",
        "currency": "USD",
        "unit": "tokens",
        "input_cost_per_1m_tokens": 2.00,
        "output_cost_per_1m_tokens": 12.00,
        "is_local": False,
        "effective_date": "2026-09-18",
        "source": "OpenAI official pricing/model documentation",
        "verified": True,
        # Ce modèle applique des règles tarifaires distinctes au-delà de
        # certains seuils de contexte. Le seuil exact n'est pas modélisé ici,
        # et inventer un palier serait pire que de ne pas en avoir : tout coût
        # calculé pour ce modèle ressort donc en cost_status="base_estimate"
        # et non "known". Voir app/ai/pricing.py (REGIME_LONG_CONTEXT).
        "unmodeled_regimes": "long_context_not_modeled",
        "notes": (
            "Base standard pricing. Long-context pricing rules may differ "
            "and are not modeled by Phase 2B."
        ),
    },
]
# Catalogue tarifaire. Un modèle sans tarif est rapporté avec
# cost_status="unknown" et un coût null — jamais 0.00, qui laisserait croire
# à la gratuité.
# Chaque entrée doit être vérifiée à sa source et datée :
#   AI_PRICING_ENTRIES = [
#       {
#           "provider": "openai",
#           "model": "<modèle exact>",
#           "input_cost_per_1m_tokens": 0.0,
#           "output_cost_per_1m_tokens": 0.0,
#           "currency": "USD",
#           "effective_date": "AAAA-MM-JJ",
#           "source": "https://…  (page de tarification consultée)",
#           "verified": True,
#       },
#   ]
# Les runtimes locaux (Ollama, LM Studio) sont déjà enregistrés par
# app/ai/pricing.py avec un coût API nul et un coût de calcul non valorisé.

AI_STAGE_SETTINGS = {
    # Configuration initiale de production des étapes éditoriales (Phase 2B).
    #
    #   source_analysis       Anthropic / Claude Sonnet 5
    #   editorial_planning    Anthropic / Claude Opus 5
    #   book_generation       Anthropic / Claude Sonnet 5
    #   book_validation       OpenAI    / GPT-5.6 Terra
    #
    # Seuls provider et modèle sont verrouillés. La température, le plafond de
    # sortie et le schéma de réponse restent le choix de l'étape appelante, qui
    # les fournit via AIRequest quand ses prompts existeront (Phases 3 à 5).
    "source_analysis": {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
    },
    "editorial_planning": {
        "provider": "anthropic",
        "model": "claude-opus-5",
    },
    "book_generation": {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
    },
    "book_validation": {
        "provider": "openai",
        "model": "gpt-5.6-terra",
    },
    # Étape fenêtre 3B.7.2 — isolée. Ne change pas source_analysis global
    # ni les trois autres étapes éditoriales. Timeouts 30/1800 issus du
    # design 3B.7 : ce n'est PAS le 7200 de l'essai global échoué.
    # max_output 32000 = borne opérationnelle de design, pas une prédiction
    # provider. Aucun appel réel n'est autorisé par cette entrée seule.
    "source_analysis_window": {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "max_output_tokens": 32000,
        "connect_timeout_seconds": 30,
        "read_timeout_seconds": 1800,
    },
    # Étape consolidation 3B.7.4 — isolée. Ne change pas source_analysis
    # global, source_analysis_window, ni les trois étapes éditoriales.
    # max_output 16000 = borne opérationnelle de design (transport compact
    # d'opérations), pas 128000 ni 32000. Timeouts 30/1800 : ce n'est PAS
    # le 7200 de l'essai global échoué. Aucun appel réel n'est autorisé
    # par cette entrée seule.
    "source_analysis_consolidation": {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "max_output_tokens": 16000,
        "connect_timeout_seconds": 30,
        "read_timeout_seconds": 1800,
    },
}
# Provider et modèle par étape éditoriale. Une étape absente de ce tableau
# (visual_design, image_generation, document_rendering) hérite de AI_PROVIDER :
# aucun choix automatique n'est fait par la couche IA.
# Champs facultatifs par étape : temperature, max_output_tokens,
# context_safety_ratio, connect_timeout_seconds, read_timeout_seconds.
# Les timeouts d'étape sont absents volontairement : aucun long read
# opérationnel n'est autorisé ici. Un read long source_analysis se
# configure via AI_SOURCE_ANALYSIS_READ_TIMEOUT_SECONDS après revue.

# =========================
# Harmonisation éditoriale globale (étape 18)
# =========================

GLOBAL_EDITOR_ENABLED = True
# Activer pour harmoniser document_final.md après la fusion des chunks.
# Génère sortie/<projet>/harmonized/document_harmonized.md.
# Ne modifie jamais document_final.md.

GLOBAL_EDITOR_MODE = "light"
# Valeurs possibles :
#   "off"        -> désactivé explicitement (même si GLOBAL_EDITOR_ENABLED = True)
#   "light"      -> harmonisation légère : titres, structure, ponctuation, transitions
#   "medium"     -> fusion légère de répétitions, amélioration de la fluidité
#   "aggressive" -> réécriture globale, réservé aux livres longs

# =====================================================
# COVER GENERATION — Génération automatique des couvertures
# =====================================================

COVER_PROVIDER = "sdxl_local"
# Moteur de génération d'images :
#   "sdxl_local" -> Stable Diffusion XL via API WebUI locale (défaut)
#                   Nécessite AUTOMATIC1111 / Forge lancé sur COVER_SD_WEBUI_URL
#   "openai"     -> DALL-E 3 via API OpenAI (nécessite OPENAI_API_KEY)
#   "fake"       -> fallback de dernier recours — couverture typographique
#                   Utilisé uniquement si aucun provider réel n'est disponible

# ── Paramètres Stable Diffusion WebUI (sdxl_local) ────────────────────────
COVER_SD_WEBUI_URL = "http://127.0.0.1:7860"
# URL de base de l'API WebUI (AUTOMATIC1111, Forge, Fooocus…)

COVER_WIDTH  = 768
COVER_HEIGHT = 1152
# Dimensions de la couverture générée (pixels).
# 768×1152 ≈ ratio livre 2:3.

COVER_STEPS     = 25
COVER_CFG_SCALE = 7
COVER_SAMPLER   = "DPM++ 2M Karras"
# Paramètres de sampling SDXL.

COVER_STYLE = "editorial_realistic"
# Style par défaut des couvertures générées.
# Valeurs supportées (voir SUPPORTED_COVER_STYLES) :
#   "editorial_realistic" -> photographie réaliste et professionnelle (défaut)
#   "spiritual"           -> atmosphère paisible, lumière douce
#   "professional"        -> épuré corporate, fond neutre
#   "modern"              -> contemporain, lignes nettes, minimaliste
#   "natural"             -> photographie nature, lumière naturelle

COVER_REALISM_PRIORITY = True
# Si True, les prompts insistent sur le réalisme photographique
# et évitent les rendus numériques ou la fantasy.

COVER_AVOID_AI_LOOK = True
# Si True, ajoute au prompt des instructions pour éviter l'aspect "image IA".

COVER_EDITORIAL_MODE = True
# Si True, les prompts privilégient l'esthétique éditoriale de livre publié.

REGENERATE_IF_TOO_ARTIFICIAL = True
# Réservé à une implémentation future : détecter et régénérer
# les couvertures à l'aspect trop artificiel.

SUPPORTED_COVER_STYLES = [
    "editorial_realistic",
    "spiritual",
    "professional",
    "modern",
    "natural",
]

# =====================================================
# COVER LAYOUT — Dimensions standards pour l'impression
# =====================================================

DEFAULT_COVER_DPI = 300
# Résolution cible pour les couvertures générées (points par pouce).
# Utilisée pour calculer les dimensions en pixels.


def get_standard_cover_pixels(page_size_name: str) -> tuple[int, int]:
    """
    Retourne les dimensions standard de la couverture en pixels à DEFAULT_COVER_DPI.

    Exemples :
        letter      → (2550, 3300)   — 8.5 × 11 po à 300 DPI
        a4          → (2480, 3508)   — 210 × 297 mm à 300 DPI
        digest      → (1650, 2550)   — 5.5 × 8.5 po à 300 DPI
        six_by_nine → (1800, 2700)   — 6 × 9 po à 300 DPI
    """
    from app.cover_layout_service import get_standard_cover_pixels as _gsp
    return _gsp(page_size_name)
