"""
Cover Builder — Moteur de couverture textuelle local pour PublishForge.

Génère une couverture professionnelle sans IA, sans modèle image, sans API externe.
Fonctionne entièrement hors ligne.

Entrées  : métadonnées du projet + thème de publication
Sorties  : sortie/<project_name>/publication/cover/cover.pdf
           sortie/<project_name>/publication/cover/cover.png  (si Pillow disponible)

Styles supportés (via cover_style du thème) :
    classic, compact, sermon, training, professional, corporate, media
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.publication_metadata import get_publication_metadata
from app.publication_theme import get_publication_theme


# ─────────────────────────────────────────────────────────────────────────────
# Labels par langue
# ─────────────────────────────────────────────────────────────────────────────

_LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "author_label":   "Auteur",
        "org_label":      "Organisation",
        "mode_label":     "Mode",
        "date_label":     "Date",
        "mode_names": {
            "BOOK":             "Livre",
            "BOOKLET":          "Livret",
            "SERMON":           "Prédication",
            "TRAINING":         "Formation",
            "CONSULTING_REPORT": "Rapport conseil",
            "CORPORATE_REPORT": "Rapport d'entreprise",
            "PODCAST":          "Podcast",
        },
    },
    "en": {
        "author_label":   "Author",
        "org_label":      "Organization",
        "mode_label":     "Mode",
        "date_label":     "Date",
        "mode_names": {
            "BOOK":             "Book",
            "BOOKLET":          "Booklet",
            "SERMON":           "Sermon",
            "TRAINING":         "Training",
            "CONSULTING_REPORT": "Consulting Report",
            "CORPORATE_REPORT": "Corporate Report",
            "PODCAST":          "Podcast",
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Palettes de couleurs par style
# ─────────────────────────────────────────────────────────────────────────────

_STYLE_PALETTES: dict[str, dict] = {
    "classic": {
        "bg":          (0x1A, 0x1A, 0x2E),
        "accent":      (0x4A, 0x90, 0xD9),
        "title_fg":    (0xFF, 0xFF, 0xFF),
        "subtitle_fg": (0xCC, 0xDD, 0xEE),
        "meta_fg":     (0xAA, 0xBB, 0xCC),
        "rule_fg":     (0x4A, 0x90, 0xD9),
    },
    "compact": {
        "bg":          (0xF8, 0xF9, 0xFA),
        "accent":      (0x2C, 0x3E, 0x50),
        "title_fg":    (0x1A, 0x1A, 0x2E),
        "subtitle_fg": (0x44, 0x55, 0x66),
        "meta_fg":     (0x66, 0x77, 0x88),
        "rule_fg":     (0x2C, 0x3E, 0x50),
    },
    "sermon": {
        "bg":          (0xFD, 0xFB, 0xF7),
        "accent":      (0x8B, 0x45, 0x13),
        "title_fg":    (0x3E, 0x1F, 0x02),
        "subtitle_fg": (0x6B, 0x3A, 0x10),
        "meta_fg":     (0x88, 0x66, 0x44),
        "rule_fg":     (0x8B, 0x45, 0x13),
    },
    "training": {
        "bg":          (0xF0, 0xF4, 0xFF),
        "accent":      (0x1E, 0x40, 0xAF),
        "title_fg":    (0x0F, 0x27, 0x6D),
        "subtitle_fg": (0x1E, 0x40, 0xAF),
        "meta_fg":     (0x44, 0x55, 0x88),
        "rule_fg":     (0x1E, 0x40, 0xAF),
    },
    "professional": {
        "bg":          (0xFF, 0xFF, 0xFF),
        "accent":      (0x00, 0x4E, 0x89),
        "title_fg":    (0x00, 0x2A, 0x4A),
        "subtitle_fg": (0x00, 0x4E, 0x89),
        "meta_fg":     (0x55, 0x66, 0x77),
        "rule_fg":     (0x00, 0x4E, 0x89),
    },
    "corporate": {
        "bg":          (0x0D, 0x1B, 0x2A),
        "accent":      (0xE8, 0xA8, 0x20),
        "title_fg":    (0xFF, 0xFF, 0xFF),
        "subtitle_fg": (0xE8, 0xD8, 0xA0),
        "meta_fg":     (0xAA, 0xBB, 0xCC),
        "rule_fg":     (0xE8, 0xA8, 0x20),
    },
    "media": {
        "bg":          (0x12, 0x12, 0x12),
        "accent":      (0xFF, 0x44, 0x44),
        "title_fg":    (0xFF, 0xFF, 0xFF),
        "subtitle_fg": (0xFF, 0xBB, 0xBB),
        "meta_fg":     (0xAA, 0xAA, 0xAA),
        "rule_fg":     (0xFF, 0x44, 0x44),
    },
}

_DEFAULT_PALETTE = _STYLE_PALETTES["classic"]


# ─────────────────────────────────────────────────────────────────────────────
# Mise en page par style (positions relatives sur la page, 0.0–1.0)
# ─────────────────────────────────────────────────────────────────────────────

_STYLE_LAYOUT: dict[str, dict] = {
    "classic": {
        "title_y_ratio":    0.38,
        "rule_y_ratio":     0.52,
        "meta_y_ratio":     0.68,
        "title_size_pt":    36,
        "subtitle_size_pt": 18,
        "meta_size_pt":     13,
        "margin_ratio":     0.12,
    },
    "compact": {
        "title_y_ratio":    0.30,
        "rule_y_ratio":     0.42,
        "meta_y_ratio":     0.55,
        "title_size_pt":    28,
        "subtitle_size_pt": 15,
        "meta_size_pt":     11,
        "margin_ratio":     0.10,
    },
    "sermon": {
        "title_y_ratio":    0.35,
        "rule_y_ratio":     0.50,
        "meta_y_ratio":     0.65,
        "title_size_pt":    34,
        "subtitle_size_pt": 17,
        "meta_size_pt":     12,
        "margin_ratio":     0.14,
    },
    "training": {
        "title_y_ratio":    0.25,
        "rule_y_ratio":     0.40,
        "meta_y_ratio":     0.60,
        "title_size_pt":    30,
        "subtitle_size_pt": 16,
        "meta_size_pt":     12,
        "margin_ratio":     0.10,
    },
    "professional": {
        "title_y_ratio":    0.40,
        "rule_y_ratio":     0.54,
        "meta_y_ratio":     0.68,
        "title_size_pt":    32,
        "subtitle_size_pt": 16,
        "meta_size_pt":     12,
        "margin_ratio":     0.13,
    },
    "corporate": {
        "title_y_ratio":    0.35,
        "rule_y_ratio":     0.50,
        "meta_y_ratio":     0.65,
        "title_size_pt":    34,
        "subtitle_size_pt": 17,
        "meta_size_pt":     13,
        "margin_ratio":     0.12,
    },
    "media": {
        "title_y_ratio":    0.42,
        "rule_y_ratio":     0.56,
        "meta_y_ratio":     0.70,
        "title_size_pt":    38,
        "subtitle_size_pt": 18,
        "meta_size_pt":     12,
        "margin_ratio":     0.10,
    },
}

_DEFAULT_LAYOUT = _STYLE_LAYOUT["classic"]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers typographiques
# ─────────────────────────────────────────────────────────────────────────────

def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Découpe `text` en lignes de `max_chars` caractères maximum."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current:
            candidate = f"{current} {word}"
        else:
            candidate = word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word[:max_chars]
    if current:
        lines.append(current)
    return lines or [""]


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _reportlab_color(rgb: tuple[int, int, int]):
    from reportlab.lib import colors
    return colors.HexColor(_rgb_to_hex(*rgb))


# ─────────────────────────────────────────────────────────────────────────────
# Générateur PDF (ReportLab canvas direct)
# ─────────────────────────────────────────────────────────────────────────────

def _build_cover_pdf(
    pdf_path: Path,
    metadata: dict,
    theme: dict,
    labels: dict,
) -> None:
    """
    Génère cover.pdf via ReportLab canvas.

    Utilise le canvas bas niveau pour un contrôle total du placement,
    adapté au rendu d'une page de couverture unique.
    """
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4, LETTER
    from reportlab.lib.units import pt

    # Taille de page
    page_size_name = (theme.get("page_size") or "LETTER").upper()
    pagesize = LETTER if page_size_name == "LETTER" else A4
    page_w, page_h = pagesize

    # Style visuel
    cover_style = (theme.get("cover_style") or "classic").lower()
    palette = _STYLE_PALETTES.get(cover_style, _DEFAULT_PALETTE)
    layout  = _STYLE_LAYOUT.get(cover_style, _DEFAULT_LAYOUT)

    margin = page_w * layout["margin_ratio"]

    # Métadonnées
    title    = (metadata.get("title")    or "").strip()
    subtitle = (metadata.get("subtitle") or "").strip()
    author   = (metadata.get("author")   or "").strip()
    org      = (metadata.get("organization") or "").strip()
    pub_date = (metadata.get("publication_date") or "").strip()
    pub_mode = (metadata.get("publication_mode") or "BOOK").strip().upper()

    mode_name = labels.get("mode_names", {}).get(pub_mode, pub_mode)

    # Canvas
    c = rl_canvas.Canvas(str(pdf_path), pagesize=pagesize)
    c.setTitle(title or "Cover")
    c.setAuthor(author or "PublishForge")

    # Fond
    bg_r, bg_g, bg_b = palette["bg"]
    c.setFillColorRGB(bg_r / 255, bg_g / 255, bg_b / 255)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # ── Bande d'accent supérieure (sauf compact / professional) ──────────────
    if cover_style not in ("compact", "professional"):
        ac_r, ac_g, ac_b = palette["accent"]
        c.setFillColorRGB(ac_r / 255, ac_g / 255, ac_b / 255)
        c.rect(0, page_h - 8 * pt, page_w, 8 * pt, fill=1, stroke=0)

    # ── Titre ────────────────────────────────────────────────────────────────
    title_y  = page_h * layout["title_y_ratio"]
    title_pt = layout["title_size_pt"]
    tf_r, tf_g, tf_b = palette["title_fg"]
    c.setFillColorRGB(tf_r / 255, tf_g / 255, tf_b / 255)
    c.setFont("Helvetica-Bold", title_pt)

    max_chars_title = int((page_w - 2 * margin) / (title_pt * 0.55))
    title_lines = _wrap_text(title, max(max_chars_title, 12))

    # Position du titre (aligné centre, décalé vers le bas pour chaque ligne)
    line_h_title = title_pt * 1.3
    for i, line in enumerate(title_lines):
        y = title_y - i * line_h_title
        c.drawCentredString(page_w / 2, y, line)

    # ── Sous-titre ───────────────────────────────────────────────────────────
    if subtitle:
        sub_y  = title_y - len(title_lines) * line_h_title - 12
        sub_pt = layout["subtitle_size_pt"]
        sf_r, sf_g, sf_b = palette["subtitle_fg"]
        c.setFillColorRGB(sf_r / 255, sf_g / 255, sf_b / 255)
        c.setFont("Helvetica-Oblique", sub_pt)
        max_chars_sub = int((page_w - 2 * margin) / (sub_pt * 0.55))
        sub_lines = _wrap_text(subtitle, max(max_chars_sub, 14))
        line_h_sub = sub_pt * 1.3
        for i, line in enumerate(sub_lines):
            c.drawCentredString(page_w / 2, sub_y - i * line_h_sub, line)

    # ── Ligne de séparation ───────────────────────────────────────────────────
    rule_y  = page_h * layout["rule_y_ratio"]
    rule_r, rule_g, rule_b = palette["rule_fg"]
    c.setStrokeColorRGB(rule_r / 255, rule_g / 255, rule_b / 255)
    c.setLineWidth(1.5)
    rule_w = page_w * 0.45
    c.line(
        (page_w - rule_w) / 2, rule_y,
        (page_w + rule_w) / 2, rule_y,
    )

    # ── Bloc de métadonnées ───────────────────────────────────────────────────
    meta_y  = page_h * layout["meta_y_ratio"]
    meta_pt = layout["meta_size_pt"]
    mf_r, mf_g, mf_b = palette["meta_fg"]
    c.setFillColorRGB(mf_r / 255, mf_g / 255, mf_b / 255)
    c.setFont("Helvetica", meta_pt)

    meta_lines: list[str] = []
    if author:
        meta_lines.append(f"{labels['author_label']} : {author}")
    if org:
        meta_lines.append(f"{labels['org_label']} : {org}")
    if mode_name:
        meta_lines.append(f"{labels['mode_label']} : {mode_name}")
    if pub_date:
        meta_lines.append(f"{labels['date_label']} : {pub_date}")

    line_h_meta = meta_pt * 1.6
    for i, line in enumerate(meta_lines):
        c.drawCentredString(page_w / 2, meta_y - i * line_h_meta, line)

    # ── Bande d'accent inférieure ──────────────────────────────────────────
    if cover_style in ("corporate", "classic", "media"):
        ac_r, ac_g, ac_b = palette["accent"]
        c.setFillColorRGB(ac_r / 255, ac_g / 255, ac_b / 255)
        c.rect(0, 0, page_w, 5 * pt, fill=1, stroke=0)

    c.save()


# ─────────────────────────────────────────────────────────────────────────────
# Générateur PNG (Pillow)
# ─────────────────────────────────────────────────────────────────────────────

def _build_cover_png(
    png_path: Path,
    metadata: dict,
    theme: dict,
    labels: dict,
    width: int = 1240,
    height: int = 1754,
) -> bool:
    """
    Génère cover.png via Pillow.

    Retourne True si la génération a réussi, False si Pillow n'est pas disponible
    ou en cas d'erreur. Ne lève jamais d'exception.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[cover_builder] Pillow non disponible — cover.png ignoré.")
        return False

    cover_style = (theme.get("cover_style") or "classic").lower()
    palette = _STYLE_PALETTES.get(cover_style, _DEFAULT_PALETTE)
    layout  = _STYLE_LAYOUT.get(cover_style, _DEFAULT_LAYOUT)

    # Métadonnées
    title    = (metadata.get("title")    or "").strip()
    subtitle = (metadata.get("subtitle") or "").strip()
    author   = (metadata.get("author")   or "").strip()
    org      = (metadata.get("organization") or "").strip()
    pub_date = (metadata.get("publication_date") or "").strip()
    pub_mode = (metadata.get("publication_mode") or "BOOK").strip().upper()
    mode_name = labels.get("mode_names", {}).get(pub_mode, pub_mode)

    # Couleurs
    bg_color     = palette["bg"]
    accent_color = palette["accent"]
    title_fg     = palette["title_fg"]
    subtitle_fg  = palette["subtitle_fg"]
    meta_fg      = palette["meta_fg"]
    rule_fg      = palette["rule_fg"]

    margin = int(width * layout["margin_ratio"])

    # Tailles de police (adaptées à la résolution PNG 1240px ≈ A4 150dpi)
    scale = width / 612.0
    title_sz    = max(int(layout["title_size_pt"] * scale * 1.05), 24)
    subtitle_sz = max(int(layout["subtitle_size_pt"] * scale * 1.0), 16)
    meta_sz     = max(int(layout["meta_size_pt"] * scale * 1.0), 12)

    try:
        img  = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Tentative de chargement de polices système
        try:
            font_title    = ImageFont.truetype("arial.ttf",    title_sz)
            font_subtitle = ImageFont.truetype("ariali.ttf",   subtitle_sz)
            font_meta     = ImageFont.truetype("arial.ttf",    meta_sz)
        except (OSError, IOError):
            try:
                font_title    = ImageFont.truetype("DejaVuSans-Bold.ttf",    title_sz)
                font_subtitle = ImageFont.truetype("DejaVuSans-Oblique.ttf", subtitle_sz)
                font_meta     = ImageFont.truetype("DejaVuSans.ttf",         meta_sz)
            except (OSError, IOError):
                font_title    = ImageFont.load_default()
                font_subtitle = ImageFont.load_default()
                font_meta     = ImageFont.load_default()

        # Bande supérieure
        if cover_style not in ("compact", "professional"):
            draw.rectangle([(0, 0), (width, 16)], fill=accent_color)

        # ── Titre ────────────────────────────────────────────────────────────
        title_y = int(height * layout["title_y_ratio"])
        max_chars_title = max(int((width - 2 * margin) / (title_sz * 0.58)), 10)
        title_lines = _wrap_text(title, max_chars_title)

        line_h_title = int(title_sz * 1.35)
        for i, line in enumerate(title_lines):
            bbox = draw.textbbox((0, 0), line, font=font_title)
            tw = bbox[2] - bbox[0]
            x = (width - tw) // 2
            y = title_y + i * line_h_title
            draw.text((x, y), line, fill=title_fg, font=font_title)

        # ── Sous-titre ───────────────────────────────────────────────────────
        if subtitle:
            sub_y = title_y + len(title_lines) * line_h_title + 20
            max_chars_sub = max(int((width - 2 * margin) / (subtitle_sz * 0.60)), 14)
            sub_lines = _wrap_text(subtitle, max_chars_sub)
            line_h_sub = int(subtitle_sz * 1.35)
            for i, line in enumerate(sub_lines):
                bbox = draw.textbbox((0, 0), line, font=font_subtitle)
                tw = bbox[2] - bbox[0]
                x = (width - tw) // 2
                draw.text((x, sub_y + i * line_h_sub), line, fill=subtitle_fg, font=font_subtitle)

        # ── Règle ────────────────────────────────────────────────────────────
        rule_y = int(height * layout["rule_y_ratio"])
        rule_w = int(width * 0.45)
        rx0 = (width - rule_w) // 2
        rx1 = rx0 + rule_w
        draw.line([(rx0, rule_y), (rx1, rule_y)], fill=rule_fg, width=3)

        # ── Métadonnées ───────────────────────────────────────────────────────
        meta_y = int(height * layout["meta_y_ratio"])
        meta_lines: list[str] = []
        if author:
            meta_lines.append(f"{labels['author_label']} : {author}")
        if org:
            meta_lines.append(f"{labels['org_label']} : {org}")
        if mode_name:
            meta_lines.append(f"{labels['mode_label']} : {mode_name}")
        if pub_date:
            meta_lines.append(f"{labels['date_label']} : {pub_date}")

        line_h_meta = int(meta_sz * 1.7)
        for i, line in enumerate(meta_lines):
            bbox = draw.textbbox((0, 0), line, font=font_meta)
            tw = bbox[2] - bbox[0]
            x = (width - tw) // 2
            draw.text((x, meta_y + i * line_h_meta), line, fill=meta_fg, font=font_meta)

        # ── Bande inférieure ──────────────────────────────────────────────────
        if cover_style in ("corporate", "classic", "media"):
            draw.rectangle([(0, height - 12), (width, height)], fill=accent_color)

        img.save(str(png_path), "PNG", dpi=(150, 150))
        return True

    except Exception as exc:  # noqa: BLE001
        print(f"[cover_builder] Erreur génération PNG : {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Sauvegarde du project_state
# ─────────────────────────────────────────────────────────────────────────────

def _save_cover_state(
    project_name: str,
    *,
    generated: bool,
    now: str,
    pdf_path: str | None = None,
    png_path: str | None = None,
    error: str | None = None,
    cover_style: str | None = None,
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
    else:
        if error:
            entry["error"] = error

    state["cover"] = entry
    save_project_state(project_name, state)
    print("[cover_builder] project_state.json mis à jour.")


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée public
# ─────────────────────────────────────────────────────────────────────────────

def generate_cover(project_name: str) -> dict:
    """
    Génère une couverture textuelle professionnelle pour le projet.

    Ne nécessite aucune IA, aucun modèle image, aucune API externe.
    Fonctionne entièrement hors ligne.

    Entrées :
        - publication_metadata  (title, subtitle, author, organization,
                                 publication_date, publication_mode)
        - publication_theme     (cover_style, page_size)

    Sorties :
        sortie/<project_name>/publication/cover/cover.pdf  (toujours)
        sortie/<project_name>/publication/cover/cover.png  (si Pillow disponible)

    Retourne :
        {
            "pdf": Path(...),          # toujours présent si succès
            "png": Path(...) | None,   # None si Pillow absent
        }

    Lève RuntimeError en cas d'échec de génération PDF.
    """
    now = datetime.now().isoformat(timespec="seconds")

    print(f"[cover_builder] Génération couverture — projet : {project_name}")
    log_event({
        "step":    "cover_builder",
        "project": project_name,
        "action":  "start",
    })

    # ── Dossier de sortie ────────────────────────────────────────────────────
    cover_dir = SORTIE_DIR / project_name / "publication" / "cover"
    cover_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = cover_dir / "cover.pdf"
    png_path = cover_dir / "cover.png"

    # ── Chargement des métadonnées ────────────────────────────────────────────
    metadata = get_publication_metadata(project_name)
    print(
        f"[cover_builder] Métadonnées : "
        f"titre={metadata['title']!r} | "
        f"auteur={metadata['author']!r} | "
        f"mode={metadata['publication_mode']}"
    )
    log_event({
        "step":    "cover_builder",
        "project": project_name,
        "action":  "metadata_loaded",
        "title":   metadata["title"],
        "author":  metadata["author"],
        "mode":    metadata["publication_mode"],
    })

    # ── Chargement du thème ───────────────────────────────────────────────────
    pub_mode  = metadata.get("publication_mode") or "BOOK"
    doc_lang  = metadata.get("document_language") or "en"
    theme     = get_publication_theme(pub_mode, doc_lang)
    cover_style = theme.get("cover_style", "classic")

    print(f"[cover_builder] Thème utilisé : {theme['mode']} | cover_style={cover_style}")
    log_event({
        "step":        "cover_builder",
        "project":     project_name,
        "action":      "theme_loaded",
        "mode":        theme["mode"],
        "cover_style": cover_style,
    })

    # ── Labels selon la langue ────────────────────────────────────────────────
    lang   = doc_lang.strip().lower()
    labels = _LABELS.get(lang, _LABELS["en"])

    # ── Génération PDF ────────────────────────────────────────────────────────
    try:
        _build_cover_pdf(pdf_path, metadata, theme, labels)
        print(f"[cover_builder] Couverture PDF générée : {pdf_path}")
        log_event({
            "step":    "cover_builder",
            "project": project_name,
            "action":  "pdf_generated",
            "path":    str(pdf_path),
        })
    except Exception as exc:  # noqa: BLE001
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
    png_ok = _build_cover_png(png_path, metadata, theme, labels)
    if png_ok:
        print(f"[cover_builder] Couverture PNG générée : {png_path}")
        log_event({
            "step":    "cover_builder",
            "project": project_name,
            "action":  "png_generated",
            "path":    str(png_path),
        })
    else:
        png_path = None  # type: ignore[assignment]

    # ── Mise à jour du project_state ──────────────────────────────────────────
    _save_cover_state(
        project_name,
        generated=True,
        pdf_path=str(pdf_path),
        png_path=str(png_path) if png_path else None,
        now=now,
        cover_style=cover_style,
    )

    print(f"[cover_builder] Génération couverture terminée — projet : {project_name}")
    log_event({
        "step":    "cover_builder",
        "project": project_name,
        "action":  "done",
        "pdf":     str(pdf_path),
        "png":     str(png_path) if png_path else None,
    })

    return {
        "pdf": pdf_path,
        "png": png_path,
    }
