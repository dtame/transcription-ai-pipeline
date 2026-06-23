"""
Service de génération et gestion des couvertures — TranscriptionAI.

Responsabilités :
  - Analyser le contenu du projet pour extraire le contexte de couverture
  - Résoudre la stratégie (user / image générée / typographie)
  - Générer la couverture avec cache intelligent
  - Sauvegarder cover.jpg, cover.png et cover_metadata.json
  - Mettre à jour project_state.json

Structure de sortie :
  sortie/<projet>/cover/
    ├── cover.jpg
    ├── cover.png           (si Pillow disponible)
    └── cover_metadata.json
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from app.paths import DEPOT_DIR, SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.project_metadata import load_project_metadata


# ---------------------------------------------------------------------------
# Décision automatique : type de couverture par document_type
# ---------------------------------------------------------------------------

_IMAGE_DOC_TYPES = frozenset({
    "livret", "petit_livre", "livre",
    "enseignement", "formation", "conference",
})

_TYPOGRAPHY_DOC_TYPES = frozenset({
    "rapport", "reunion",
})


# ---------------------------------------------------------------------------
# Résolution de stratégie
# ---------------------------------------------------------------------------

def resolve_cover_strategy(
    metadata: dict,
    publication_settings: dict,
) -> dict:
    """
    Détermine la stratégie de couverture à utiliser.

    Ordre de priorité :
      1. Image fournie par l'utilisateur  → type="image", source="user"
      2. Génération automatique d'image   → type="image", source="generated"
      3. Couverture typographique         → type="typography", source="typography"

    Retourne un dict avec au minimum :
      type         : "image" | "typography" | "none"
      source       : "user" | "generated" | "typography"
      user_path    : chemin absolu de l'image utilisateur (si source="user")
    """
    include_cover = metadata.get("include_cover", True)
    if not include_cover:
        return {"type": "none", "source": "none"}

    # ── 1. Image utilisateur ──────────────────────────────────────────────
    cover_image = metadata.get("cover_image", "auto")
    cover_image_source = metadata.get("cover_image_source", "none")

    if cover_image and cover_image not in ("auto", "none"):
        # Chemin relatif au dossier depot/<projet>
        project_name = publication_settings.get("_project_name", "")
        candidate = DEPOT_DIR / project_name / cover_image
        if not candidate.exists():
            # Essai en absolu
            candidate = Path(cover_image)
        if candidate.exists():
            return {
                "type":      "image",
                "source":    "user",
                "user_path": str(candidate),
            }

    if cover_image_source == "user":
        # L'utilisateur a déclaré une image utilisateur mais sans chemin → fallback
        pass

    # ── 2. Mode de génération explicite ──────────────────────────────────
    cover_generation_mode = metadata.get("cover_generation_mode", "auto")

    if cover_generation_mode == "typography":
        return {"type": "typography", "source": "typography"}

    if cover_generation_mode == "image":
        return {"type": "image", "source": "generated"}

    # ── 3. Décision automatique basée sur le document_type ────────────────
    doc_type = publication_settings.get("document_type", "article")

    if doc_type in _IMAGE_DOC_TYPES:
        return {"type": "image", "source": "generated"}

    if doc_type in _TYPOGRAPHY_DOC_TYPES:
        return {"type": "typography", "source": "typography"}

    # Défaut : image générée
    return {"type": "image", "source": "generated"}


# ---------------------------------------------------------------------------
# Contexte du document
# ---------------------------------------------------------------------------

def build_cover_context(project_name: str) -> dict:
    """
    Extrait le contexte du projet pour la génération de prompt.

    Lit :
      - Métadonnées project.yaml (titre, auteur, organisation, audience…)
      - Début de document_final.md pour un résumé (≤ 500 caractères)
    """
    meta = load_project_metadata(project_name)
    final_md = SORTIE_DIR / project_name / "final" / "document_final.md"

    short_summary = ""
    if final_md.exists():
        raw = final_md.read_text(encoding="utf-8")
        short_summary = _extract_summary(raw)

    return {
        "title":        meta.get("title", ""),
        "subtitle":     meta.get("subtitle", ""),
        "author":       meta.get("author", ""),
        "organization": meta.get("organization", ""),
        "theme":        meta.get("theme", ""),
        "document_type": meta.get("document_type", "auto"),
        "description":  meta.get("description", ""),
        "keywords":     meta.get("keywords", ""),
        "audience":     meta.get("audience", ""),
        "cover_style":  meta.get("cover_style", "editorial_realistic"),
        "summary":      short_summary,
    }


def _extract_summary(markdown: str) -> str:
    """
    Extrait un résumé court à partir du début d'un Markdown.
    Retire les titres et lignes vides, limite à 500 caractères.
    """
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if re.match(r"^[-*_]{3,}$", stripped):
            continue
        lines.append(stripped)
        if sum(len(l) for l in lines) >= 500:
            break

    text = " ".join(lines)
    return text[:500].rsplit(" ", 1)[0] if len(text) > 500 else text


# ---------------------------------------------------------------------------
# Construction du prompt
# ---------------------------------------------------------------------------

def build_cover_prompt(context: dict) -> str:
    """
    Construit le prompt de génération à partir du contexte du projet.
    Combine : résumé, thème, style, public cible et prompt système.
    """
    from app.cover_engine import COVER_SYSTEM_PROMPT

    parts: list[str] = []

    title = context.get("title", "")
    subtitle = context.get("subtitle", "")
    audience = context.get("audience", "")
    keywords = context.get("keywords", "")
    summary = context.get("summary", "")
    cover_style = context.get("cover_style", "editorial_realistic")

    if title:
        parts.append(f"Book about: {title}.")
    if subtitle:
        parts.append(f"Subtitle: {subtitle}.")
    if audience:
        parts.append(f"Audience: {audience}.")
    if keywords:
        parts.append(f"Key topics: {keywords}.")
    if summary:
        parts.append(f"Content summary: {summary}.")

    # Directive de style
    style_directives = _STYLE_DIRECTIVES.get(cover_style, _STYLE_DIRECTIVES["editorial_realistic"])
    parts.append(style_directives)

    # Prompt système global
    parts.append(COVER_SYSTEM_PROMPT)

    return " ".join(p for p in parts if p)


_STYLE_DIRECTIVES: dict[str, str] = {
    "editorial_realistic": (
        "Style: editorial realistic photography. "
        "Natural daylight. Authentic textures. "
        "Minimalist professional composition."
    ),
    "spiritual": (
        "Style: peaceful spiritual atmosphere. "
        "Soft natural light. Serene landscape or abstract symbol. "
        "Warm contemplative tones."
    ),
    "professional": (
        "Style: clean corporate professional. "
        "Neutral background. Geometric or abstract composition. "
        "Confident and polished look."
    ),
    "modern": (
        "Style: contemporary modern design. "
        "Bold clean lines. High contrast. "
        "Sleek minimalist aesthetic."
    ),
    "natural": (
        "Style: nature photography. "
        "Outdoor setting. Golden hour or overcast natural light. "
        "Organic textures and calm colours."
    ),
}


# ---------------------------------------------------------------------------
# Couverture typographique (image)
# ---------------------------------------------------------------------------

def generate_typography_cover(output_path: Path, settings: dict) -> Path:
    """
    Génère une couverture typographique sous forme d'image JPEG 600×900 px.

    Utilise Pillow si disponible.
    Sinon, crée un placeholder JPEG minimal.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _generate_typography_pillow(output_path, settings)
    except ImportError:
        from app.cover_engine import _write_placeholder_jpeg
        _write_placeholder_jpeg(output_path)

    return output_path


def _generate_typography_pillow(output_path: Path, settings: dict) -> None:
    """Génère la couverture typographique avec Pillow."""
    from PIL import Image, ImageDraw

    W, H = 600, 900

    theme_colors = settings.get("theme_colors", {})
    primary   = _hex_to_rgb(theme_colors.get("primary",   "#1a1a1a"))
    secondary = _hex_to_rgb(theme_colors.get("secondary", "#f5f0e8"))
    accent    = _hex_to_rgb(theme_colors.get("accent",    "#666666"))

    img  = Image.new("RGB", (W, H), color=secondary)
    draw = ImageDraw.Draw(img)

    # Bande de couleur primaire en haut (15% de la page)
    band_h = int(H * 0.15)
    draw.rectangle([0, 0, W, band_h], fill=primary)

    # Bande de couleur accent en bas (8% de la page)
    foot_h = int(H * 0.08)
    draw.rectangle([0, H - foot_h, W, H], fill=accent)

    # Ligne décorative sous la bande haute
    draw.rectangle([0, band_h, W, band_h + 3], fill=accent)

    # Titre (zone centrale)
    title    = settings.get("title", "")
    subtitle = settings.get("subtitle", "")
    author   = settings.get("author", "")
    org      = settings.get("organization", "")
    date_s   = settings.get("date", "")
    version  = settings.get("version", "")

    title_y = int(H * 0.35)
    _draw_wrapped(draw, title,    W, title_y,    primary, max_chars=28, size_hint="large")
    if subtitle:
        _draw_wrapped(draw, subtitle, W, title_y + 70, accent, max_chars=38, size_hint="medium")

    # Séparateur
    sep_y = int(H * 0.62)
    draw.line([(W // 2 - 60, sep_y), (W // 2 + 60, sep_y)], fill=accent, width=1)

    # Auteur
    author_y = sep_y + 25
    if author:
        _draw_centered(draw, author, W, author_y, primary)

    # Organisation
    if org:
        _draw_centered(draw, org, W, author_y + 28, accent)

    # Date + version au bas de la page (zone pied)
    meta_parts = []
    if date_s:
        meta_parts.append(date_s)
    if version:
        meta_parts.append(f"v{version}")
    if meta_parts:
        meta_str = "  —  ".join(meta_parts)
        _draw_centered(draw, meta_str, W, H - foot_h // 2, secondary)

    img.save(str(output_path), "JPEG", quality=92)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _draw_centered(
    draw, text: str, page_w: int, y: int, fill: tuple
) -> None:
    """Texte centré horizontalement (compatibilité Pillow ancienne et récente)."""
    try:
        draw.text((page_w // 2, y), text, fill=fill, anchor="mm")
    except TypeError:
        approx_w = len(text) * 7
        draw.text((page_w // 2 - approx_w // 2, y - 8), text, fill=fill)


def _draw_wrapped(
    draw, text: str, page_w: int, y: int, fill: tuple,
    max_chars: int = 28, size_hint: str = "large",
) -> None:
    """Découpe le texte sur plusieurs lignes si nécessaire."""
    if not text:
        return
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)

    line_h = 38 if size_hint == "large" else 26
    for i, line in enumerate(lines[:3]):
        _draw_centered(draw, line, page_w, y + i * line_h, fill)


# ---------------------------------------------------------------------------
# Signature de cache
# ---------------------------------------------------------------------------

def _compute_cover_signature(
    project_name: str, settings: dict, strategy: dict
) -> str:
    """Calcule une signature MD5 pour la couverture (invalidation de cache)."""
    fields = {
        "title":              settings.get("title", ""),
        "theme":              settings.get("theme", ""),
        "cover_style":        settings.get("cover_style", "editorial_realistic"),
        "document_type":      settings.get("document_type", ""),
        "include_cover":      settings.get("include_cover", True),
        "strategy_type":      strategy.get("type", ""),
        "strategy_source":    strategy.get("source", ""),
    }
    if strategy.get("source") == "user" and strategy.get("user_path"):
        user_p = Path(strategy["user_path"])
        if user_p.exists():
            fields["user_image_hash"] = _file_hash(user_p)

    return hashlib.md5(
        json.dumps(fields, sort_keys=True, default=str).encode()
    ).hexdigest()


def _file_hash(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Métadonnées de couverture
# ---------------------------------------------------------------------------

def _save_cover_metadata(cover_dir: Path, meta: dict) -> None:
    meta_path = cover_dir / "cover_metadata.json"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_cover_metadata(project_name: str) -> dict:
    """Charge cover_metadata.json du projet, ou retourne un dict vide."""
    meta_path = SORTIE_DIR / project_name / "cover" / "cover_metadata.json"
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Génération principale
# ---------------------------------------------------------------------------

def generate_cover(project_name: str, force: bool = False) -> dict:
    """
    Génère la couverture du projet avec cache intelligent.

    Cache invalidé si :
      - couverture absente
      - titre modifié
      - thème modifié
      - style modifié
      - image utilisateur modifiée
      - stratégie changée

    Args:
        project_name: Nom du projet.
        force:        Si True, régénère même si le cache est valide.

    Returns:
        dict avec les informations de la couverture (section "cover" du state).
    """
    state = load_project_state(project_name)

    final_md_path = SORTIE_DIR / project_name / "final" / "document_final.md"
    if not final_md_path.exists():
        print(f"[cover] document_final.md introuvable pour : {project_name}")
        _update_cover_state(state, {"generated": False})
        save_project_state(project_name, state)
        return {"generated": False}

    # ── Résolution des paramètres ─────────────────────────────────────────
    from app.publication_template_service import resolve_publication_settings
    from app import config as cfg

    final_content = final_md_path.read_text(encoding="utf-8")
    settings = resolve_publication_settings(project_name, final_content)
    settings["_project_name"] = project_name

    strategy = resolve_cover_strategy(metadata=settings, publication_settings=settings)

    if strategy["type"] == "none":
        print(f"[cover] Couverture désactivée pour : {project_name}")
        result = {"generated": False}
        _update_cover_state(state, result)
        save_project_state(project_name, state)
        return result

    # ── Cache ─────────────────────────────────────────────────────────────
    cover_dir = SORTIE_DIR / project_name / "cover"
    cover_jpg = cover_dir / "cover.jpg"
    current_sig = _compute_cover_signature(project_name, settings, strategy)

    if not force:
        cover_state = state.get("cover", {})
        if (
            cover_jpg.exists()
            and cover_state.get("generated")
            and cover_state.get("source_signature") == current_sig
        ):
            print(f"[cover] Couverture déjà à jour : {cover_jpg}")
            return cover_state

    cover_dir.mkdir(parents=True, exist_ok=True)

    cover_type   = strategy["type"]
    cover_source = strategy["source"]
    provider     = "unknown"

    # ── Génération ────────────────────────────────────────────────────────
    try:
        if cover_source == "user":
            user_path = Path(strategy["user_path"])
            shutil.copy2(str(user_path), str(cover_jpg))
            provider = "user"
            print(f"[cover] Image utilisateur copiée : {cover_jpg}")

        elif cover_type == "typography":
            generate_typography_cover(cover_jpg, settings)
            provider = "typography"
            print(f"[cover] Couverture typographique générée : {cover_jpg}")

        else:
            # Génération par IA (ou fallback typographie si provider=fake)
            from app.cover_engine import get_cover_engine
            from app import config as _cfg

            _provider = getattr(_cfg, "COVER_PROVIDER", "fake").lower()

            if _provider == "fake":
                # Pas de vrai moteur d'image → couverture typographique propre
                generate_typography_cover(cover_jpg, settings)
                provider = "typography"
                print(f"[cover] Couverture typographique (fake provider) : {cover_jpg}")
            else:
                context = build_cover_context(project_name)
                prompt  = build_cover_prompt(context)
                engine  = get_cover_engine()
                engine.generate(prompt, cover_jpg)
                provider = engine.provider_name
                print(f"[cover] Couverture générée ({provider}) : {cover_jpg}")

    except Exception as exc:
        print(f"[cover] ERREUR génération : {exc}")
        raise

    # ── PNG optionnel ─────────────────────────────────────────────────────
    cover_png = cover_dir / "cover.png"
    try:
        from PIL import Image as PilImage
        with PilImage.open(str(cover_jpg)) as img:
            img.save(str(cover_png), "PNG")
    except ImportError:
        pass  # Pillow non disponible
    except Exception:
        pass  # Conversion PNG non critique

    # ── Métadonnées ───────────────────────────────────────────────────────
    cover_style = settings.get("cover_style", getattr(cfg, "COVER_STYLE", "editorial_realistic"))
    generated_at = datetime.now().isoformat(timespec="seconds")

    _save_cover_metadata(cover_dir, {
        "project":       project_name,
        "provider":      provider,
        "type":          cover_type,
        "style":         cover_style,
        "source":        cover_source,
        "generated_at":  generated_at,
        "signature":     current_sig,
        "jpg_path":      str(cover_jpg),
        "png_path":      str(cover_png) if cover_png.exists() else None,
    })

    result = {
        "generated":        True,
        "provider":         provider,
        "style":            cover_style,
        "type":             cover_type,
        "source":           cover_source,
        "path":             str(cover_jpg),
        "updated_at":       generated_at,
        "source_signature": current_sig,
    }

    _update_cover_state(state, result)
    save_project_state(project_name, state)

    return result


def _update_cover_state(state: dict, cover_info: dict) -> None:
    state["cover"] = cover_info


# ---------------------------------------------------------------------------
# Accès rapide au chemin de couverture
# ---------------------------------------------------------------------------

def get_cover_path(project_name: str) -> Path | None:
    """
    Retourne le chemin cover.jpg si la couverture existe et est substantielle.

    Retourne None si :
    - le fichier n'existe pas
    - le fichier est vide ou trop petit (< 2 Ko → probablement un JPEG 1×1 px)
    """
    cover_jpg = SORTIE_DIR / project_name / "cover" / "cover.jpg"
    if cover_jpg.exists() and cover_jpg.stat().st_size > 2_000:
        return cover_jpg
    return None


def delete_cover(project_name: str) -> None:
    """Supprime la couverture générée et réinitialise l'état."""
    cover_dir = SORTIE_DIR / project_name / "cover"
    if cover_dir.exists():
        shutil.rmtree(str(cover_dir))

    state = load_project_state(project_name)
    state.pop("cover", None)
    save_project_state(project_name, state)
    print(f"[cover] Couverture supprimée pour : {project_name}")


def import_user_cover(project_name: str, source_path: Path) -> Path:
    """
    Copie une image fournie par l'utilisateur dans depot/<projet>/assets/.

    Formats acceptés : .jpg, .jpeg, .png
    Met à jour cover.jpg dans sortie/<projet>/cover/.

    Returns:
        Chemin de destination dans assets/.
    """
    suffix = source_path.suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png"):
        raise ValueError(
            f"Format non supporté : {suffix!r}. Formats acceptés : .jpg, .jpeg, .png"
        )

    assets_dir = DEPOT_DIR / project_name / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    dest = assets_dir / ("cover" + suffix)
    shutil.copy2(str(source_path), str(dest))

    cover_dir = SORTIE_DIR / project_name / "cover"
    cover_dir.mkdir(parents=True, exist_ok=True)

    cover_jpg = cover_dir / "cover.jpg"

    if suffix == ".png":
        try:
            from PIL import Image as PilImage
            with PilImage.open(str(dest)) as img:
                img.convert("RGB").save(str(cover_jpg), "JPEG", quality=92)
        except ImportError:
            shutil.copy2(str(dest), str(cover_jpg))
    else:
        shutil.copy2(str(dest), str(cover_jpg))

    # Invalider le cache pour forcer la re-détection
    state = load_project_state(project_name)
    state.pop("cover", None)
    save_project_state(project_name, state)

    print(f"[cover] Image utilisateur importée : {dest}")
    return dest
