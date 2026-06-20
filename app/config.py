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

OLLAMA_OPTIONS = {
    "temperature": 0.2,
    "num_ctx": 8192,
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
