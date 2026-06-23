"""
Configuration centralisée du moteur de génération d'images (image_engine).

Ce fichier est indépendant de app/config.py (pipeline texte).
Modifier uniquement ce fichier pour ajuster les paramètres d'images.

Providers disponibles :
  "sdxl_local"  → Stable Diffusion XL 1.0 (local, Hugging Face Diffusers)
  "fake"        → simulation sans dépendance (tests, CI)
"""

# ──────────────────────────────────────────────────────────────────────────────
# Provider actif
# ──────────────────────────────────────────────────────────────────────────────

IMAGE_PROVIDER = "sdxl_local"
# Valeurs possibles :
#   "sdxl_local"  → moteur SDXL local (Hugging Face Diffusers)
#   "fake"        → simulation pour les tests

# ──────────────────────────────────────────────────────────────────────────────
# Modèle SDXL
# ──────────────────────────────────────────────────────────────────────────────

SDXL_MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
# Identifiant Hugging Face du modèle SDXL.
# Le modèle est téléchargé automatiquement lors du premier appel (~6 Go).
# Cache par défaut : ~/.cache/huggingface/

SDXL_VARIANT = "fp16"
# Variante du modèle :
#   "fp16"  → demi-précision, recommandé avec GPU CUDA (moins de VRAM)
#   None    → précision complète (CPU ou GPU avec beaucoup de VRAM)

# ──────────────────────────────────────────────────────────────────────────────
# Dimensions des images
# ──────────────────────────────────────────────────────────────────────────────

IMAGE_WIDTH = 1024
# Largeur en pixels (SDXL natif : 1024)

IMAGE_HEIGHT = 1536
# Hauteur en pixels pour couverture verticale (ratio 2:3 approximatif)
# Couverture standard livre numérique/imprimé : 1600×2400 réduit à 1024×1536

# ──────────────────────────────────────────────────────────────────────────────
# Paramètres de génération
# ──────────────────────────────────────────────────────────────────────────────

IMAGE_STEPS = 30
# Nombre d'étapes de diffusion.
# Plage recommandée : 20 (rapide) → 50 (qualité max).

IMAGE_GUIDANCE_SCALE = 7.0
# Coefficient d'adhérence au prompt (Classifier-Free Guidance).
# Plage recommandée : 5.0 (créatif) → 10.0 (strict).

# ──────────────────────────────────────────────────────────────────────────────
# Prompt négatif par défaut
# ──────────────────────────────────────────────────────────────────────────────

IMAGE_NEGATIVE_PROMPT_DEFAULT = (
    "text, letters, words, watermark, logo, signature, caption, "
    "distorted face, deformed hands, extra fingers, missing fingers, "
    "fantasy, cartoon, anime, illustration, painting, drawing, sketch, "
    "oversaturated colors, glowing effects, neon, plastic look, "
    "digital art, CGI rendering, 3D render, artificial perfection, "
    "low quality, blurry, pixelated, noise, grain, jpeg artifacts, "
    "AI-looking image, Midjourney style, generic stock photo"
)

# ──────────────────────────────────────────────────────────────────────────────
# Mode de calcul (CPU / CUDA)
# ──────────────────────────────────────────────────────────────────────────────

SDXL_FORCE_CPU = False
# Si True, force le mode CPU même si CUDA est disponible.
# Utile pour déboguer ou si le GPU manque de VRAM.
# Attention : la génération CPU est très lente (plusieurs minutes par image).

SDXL_CPU_OFFLOAD = False
# Si True, active le déchargement séquentiel CPU/GPU (model_cpu_offload).
# Réduit la consommation VRAM au prix d'une latence plus élevée.
# Utile pour les GPU avec peu de VRAM (< 8 Go).

# ──────────────────────────────────────────────────────────────────────────────
# Dossiers de sortie (relatifs à sortie/<project_name>/images/)
# ──────────────────────────────────────────────────────────────────────────────

IMAGE_OUTPUT_SUBDIRS = [
    "cover_front",
    "cover_back",
    "chapters",
    "sections",
    "training",
    "rejected",
]
