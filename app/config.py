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
#   "ollama"   -> moteur principal recommandé (Ollama local)
#   "lmstudio" -> LM Studio (API compatible OpenAI)
#   "openai"   -> API OpenAI cloud (nécessite clé API)
#   "fake"     -> simulation locale pour les tests

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

# =========================
# OpenAI (cloud, optionnel)
# =========================

OPENAI_API_KEY = ""
OPENAI_MODEL = "gpt-4o-mini"

# =========================
# Harmonisation éditoriale globale (étape 18)
# =========================

GLOBAL_EDITOR_ENABLED = False
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

COVER_PROVIDER = "fake"
# Moteur de génération d'images :
#   "fake"   -> simulation locale pour les tests (aucune dépendance)
#   "openai" -> DALL-E 3 via API OpenAI (nécessite OPENAI_API_KEY)

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
