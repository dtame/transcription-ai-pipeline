"""
Cover Builder — Orchestrateur de couverture typographique pour PublishForge.

Génère une couverture professionnelle sans IA, sans modèle image, sans API externe.
Fonctionne entièrement hors ligne.

Nouvelle architecture (v2) :
    CoverTheme       → palettes, typographies, textures, ornements
    CoverLayout      → grille de 8 zones, marges, proportions
    CoverComposition → modèles de composition, équilibre visuel
    CoverRenderer    → rendu PDF (ReportLab) + PNG (Pillow)

Sorties :
    sortie/<project_name>/publication/cover/cover.pdf  (toujours)
    sortie/<project_name>/publication/cover/cover.png  (si Pillow disponible)

API publique conservée (rétrocompatibilité totale) :
    generate_cover(project_name) → {"pdf": Path, "png": Path | None}

Paramètres supplémentaires lus depuis les métadonnées du projet :
    cover_theme       → nom de thème explicite (priorité sur cover_style)
    cover_composition → modèle de composition explicite
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.publication_metadata import get_publication_metadata
from app.publication_theme import get_publication_theme

from app.cover_theme import get_theme, CoverTheme
from app.cover_layout import build_grid
from app.cover_composition import (
    resolve_composition_model,
    VisualBalance,
    CompositionContext,
)
from app.cover_renderer import (
    FontRegistry,
    render_pdf,
    render_png,
)


# ─────────────────────────────────────────────────────────────────────────────
# Dimensions de page
# ─────────────────────────────────────────────────────────────────────────────

def _page_size_pt(page_size_name: str) -> tuple[float, float]:
    """Retourne les dimensions de la page en points ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4, LETTER, B5
        sizes = {
            "A4":           A4,
            "LETTER":       LETTER,
            "B5":           B5,
            "DIGEST":       (396.0, 612.0),    # 5.5 × 8.5 po
            "SIX_BY_NINE":  (432.0, 648.0),    # 6 × 9 po
        }
        return sizes.get(page_size_name.upper(), LETTER)
    except ImportError:
        return (612.0, 792.0)  # LETTER en points


def _png_dimensions(page_size_name: str) -> tuple[int, int]:
    """Retourne les dimensions PNG à 150 DPI pour la prévisualisation."""
    sizes = {
        "A4":          (1240, 1754),
        "LETTER":      (1275, 1650),
        "B5":          (1039, 1469),
        "DIGEST":      (825,  1275),
        "SIX_BY_NINE": (900,  1350),
    }
    return sizes.get(page_size_name.upper(), (1240, 1754))


# ─────────────────────────────────────────────────────────────────────────────
# Sauvegarde du project_state
# ─────────────────────────────────────────────────────────────────────────────

def _save_cover_state(
    project_name: str,
    *,
    generated:    bool,
    now:          str,
    pdf_path:     str | None = None,
    png_path:     str | None = None,
    error:        str | None = None,
    cover_style:  str | None = None,
    composition:  str | None = None,
) -> None:
    state = load_project_state(project_name)
    state.setdefault("cover", {})

    entry: dict = {
        "generated":    generated,
        "generated_at": now,
    }
    if generated:
        if pdf_path:
            entry["pdf"] = pdf_path
        if png_path:
            entry["png"] = png_path
        if cover_style:
            entry["cover_style"] = cover_style
        if composition:
            entry["composition"] = composition
    elif error:
        entry["error"] = error

    state["cover"] = entry
    save_project_state(project_name, state)


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée public — API préservée
# ─────────────────────────────────────────────────────────────────────────────

def generate_cover(project_name: str) -> dict:
    """
    Génère une couverture typographique professionnelle pour le projet.

    Ne nécessite aucune IA, aucun modèle image, aucune API externe.
    Fonctionne entièrement hors ligne.

    Entrées (lues automatiquement) :
        publication_metadata  → title, subtitle, author, organization,
                                 publication_date, publication_mode,
                                 document_language
        publication_theme     → cover_style, page_size

    Sorties :
        sortie/<project_name>/publication/cover/cover.pdf  (toujours)
        sortie/<project_name>/publication/cover/cover.png  (si Pillow disponible)

    Retourne :
        {
            "pdf": Path,          # toujours présent si succès
            "png": Path | None,   # None si Pillow absent ou erreur
        }

    Lève RuntimeError en cas d'échec de génération PDF.
    """
    now = datetime.now().isoformat(timespec="seconds")

    print(f"[cover_builder] Génération couverture — projet : {project_name}")
    log_event({"step": "cover_builder", "project": project_name, "action": "start"})

    # ── Dossier de sortie ────────────────────────────────────────────────────
    cover_dir = SORTIE_DIR / project_name / "publication" / "cover"
    cover_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = cover_dir / "cover.pdf"
    png_path = cover_dir / "cover.png"

    # ── Chargement des métadonnées ───────────────────────────────────────────
    metadata = get_publication_metadata(project_name)
    print(
        f"[cover_builder] Métadonnées : "
        f"titre={metadata.get('title', '')!r} | "
        f"auteur={metadata.get('author', '')!r} | "
        f"mode={metadata.get('publication_mode', 'BOOK')}"
    )
    log_event({
        "step":    "cover_builder",
        "project": project_name,
        "action":  "metadata_loaded",
        "title":   metadata.get("title", ""),
        "author":  metadata.get("author", ""),
        "mode":    metadata.get("publication_mode", "BOOK"),
    })

    # ── Chargement du thème de publication ──────────────────────────────────
    pub_mode    = (metadata.get("publication_mode") or "BOOK").strip().upper()
    doc_lang    = (metadata.get("document_language") or "fr").strip().lower()
    pub_theme   = get_publication_theme(pub_mode, doc_lang)
    cover_style = pub_theme.get("cover_style", "classic")
    page_size_n = (pub_theme.get("page_size") or "LETTER").upper()

    print(f"[cover_builder] Thème : {pub_theme.get('mode', pub_mode)} | "
          f"cover_style={cover_style} | page_size={page_size_n}")

    # ── Résolution du thème et de la composition ─────────────────────────────
    # Priorité : cover_theme explicite dans metadata > cover_style > pub_mode
    explicit_theme = metadata.get("cover_theme") or metadata.get("cover_composition")
    theme: CoverTheme = get_theme(
        cover_style    = explicit_theme or cover_style,
        publication_mode = pub_mode,
    )
    composition = resolve_composition_model(pub_mode, explicit_theme or cover_style)

    print(f"[cover_builder] Thème visuel : {theme.name} | "
          f"Composition : {composition.value}")
    log_event({
        "step":        "cover_builder",
        "project":     project_name,
        "action":      "theme_resolved",
        "theme":       theme.name,
        "composition": composition.value,
    })

    # ── Construction de la grille ────────────────────────────────────────────
    page_size = _page_size_pt(page_size_n)
    grid      = build_grid(
        page_w       = page_size[0],
        page_h       = page_size[1],
        margin_ratio = theme.margin_ratio,
        composition  = composition,
    )

    # ── Équilibre visuel et contexte de composition ──────────────────────────
    # Calcul de la largeur disponible pour le texte
    available_w = page_size[0] * (1.0 - 2.0 * theme.margin_ratio)

    # Polices pour la mesure
    fn_title = FontRegistry.get_rl_font(theme.font_family, "bold")
    fn_sub   = FontRegistry.get_rl_font(theme.font_family, "regular", italic=True)

    ctx: CompositionContext = VisualBalance.build_context(
        metadata         = metadata,
        composition      = composition,
        title_size_pt    = theme.main_title.size_pt,
        subtitle_size_pt = theme.subtitle.size_pt,
        available_width  = available_w,
        font_name_title  = fn_title,
        font_name_sub    = fn_sub,
    )

    print(
        f"[cover_builder] Titre {len(ctx.title_lines)} ligne(s) "
        f"(scale={ctx.title_scale:.2f}) | "
        f"Sous-titre {len(ctx.subtitle_lines)} ligne(s) "
        f"(scale={ctx.subtitle_scale:.2f})"
    )

    # ── Génération PDF ────────────────────────────────────────────────────────
    try:
        render_pdf(pdf_path, ctx, theme, grid, page_size)
        print(f"[cover_builder] PDF généré : {pdf_path}")
        log_event({
            "step":    "cover_builder",
            "project": project_name,
            "action":  "pdf_generated",
            "path":    str(pdf_path),
        })
    except Exception as exc:
        msg = f"Échec génération PDF : {exc}"
        print(f"[cover_builder] ERREUR : {msg}")
        log_event({
            "step":    "cover_builder",
            "project": project_name,
            "action":  "error",
            "error":   msg,
        })
        _save_cover_state(project_name, generated=False, error=msg, now=now)
        raise RuntimeError(msg) from exc

    # ── Génération PNG (optionnelle) ──────────────────────────────────────────
    png_w, png_h = _png_dimensions(page_size_n)

    # Reconstruction de la grille à l'échelle PNG
    grid_png = build_grid(
        page_w       = float(png_w),
        page_h       = float(png_h),
        margin_ratio = theme.margin_ratio,
        composition  = composition,
    )

    png_ok = render_png(png_path, ctx, theme, grid_png, width=png_w, height=png_h)

    if png_ok:
        print(f"[cover_builder] PNG généré : {png_path}")
        log_event({
            "step":    "cover_builder",
            "project": project_name,
            "action":  "png_generated",
            "path":    str(png_path),
        })
    else:
        png_path = None  # type: ignore[assignment]
        print("[cover_builder] PNG non généré (Pillow absent ou erreur).")

    # ── Mise à jour du project_state ──────────────────────────────────────────
    _save_cover_state(
        project_name,
        generated    = True,
        pdf_path     = str(cover_dir / "cover.pdf"),
        png_path     = str(cover_dir / "cover.png") if png_ok else None,
        now          = now,
        cover_style  = cover_style,
        composition  = composition.value,
    )

    print(f"[cover_builder] Génération terminée — projet : {project_name}")
    log_event({
        "step":    "cover_builder",
        "project": project_name,
        "action":  "done",
        "theme":   theme.name,
        "pdf":     str(cover_dir / "cover.pdf"),
        "png":     str(cover_dir / "cover.png") if png_ok else None,
    })

    return {
        "pdf": cover_dir / "cover.pdf",
        "png": cover_dir / "cover.png" if png_ok else None,
    }
