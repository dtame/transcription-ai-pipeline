"""
Publication PDF Engine — Génère publication.pdf depuis publication.md.

Entrée  : sortie/<project_name>/publication/publication.md
Sortie  : sortie/<project_name>/publication/publication.pdf

Moteur modulaire conçu pour supporter à terme :
  - couverture graphique IA
  - livre / livret
  - guide du participant / formateur
  - rapport entreprise
  - thèmes graphiques
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import cm
from reportlab.lib import colors

from app.document_language import get_document_language
from app.logger import log_event
from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state
from app.publication_metadata import get_publication_metadata
from app.publication_theme import get_publication_theme


# Mapping nom de page → tuple ReportLab
_PAGESIZES: dict[str, tuple] = {
    "LETTER": LETTER,
    "A4":     A4,
}


# ─────────────────────────────────────────────────────────────────────────────
# Labels par langue
# ─────────────────────────────────────────────────────────────────────────────

_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "toc":            "Table of Contents",
        "project_label":  "Project",
        "date_label":     "Date",
    },
    "fr": {
        "toc":            "Table des matières",
        "project_label":  "Projet",
        "date_label":     "Date",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Couleurs
# ─────────────────────────────────────────────────────────────────────────────

_COLOR_PRIMARY   = colors.HexColor("#1A1A2E")
_COLOR_SECONDARY = colors.HexColor("#2C3E50")
_COLOR_TEXT      = colors.HexColor("#2D2D2D")
_COLOR_ACCENT    = colors.HexColor("#4A4A6A")
_COLOR_SUBTLE    = colors.HexColor("#888888")


# ─────────────────────────────────────────────────────────────────────────────
# Styles typographiques
# ─────────────────────────────────────────────────────────────────────────────

def _build_styles(theme: dict | None = None) -> dict[str, ParagraphStyle]:
    """Crée l'ensemble des styles ReportLab selon le thème fourni."""
    t = theme or {}
    base = getSampleStyleSheet()

    title_fs   = t.get("title_font_size",    28)
    h1_fs      = t.get("heading1_font_size", 18)
    h2_fs      = t.get("heading2_font_size", 14)
    body_fs    = t.get("body_font_size",     11)
    line_mul   = t.get("body_line_spacing",  1.15)
    body_lead  = round(body_fs * line_mul * 1.15, 1)

    TitleStyle = ParagraphStyle(
        "PubPDFTitle",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=title_fs,
        leading=round(title_fs * 1.3, 1),
        alignment=TA_CENTER,
        textColor=_COLOR_PRIMARY,
        spaceAfter=16,
    )

    SubtitleStyle = ParagraphStyle(
        "PubPDFSubtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=max(body_fs, 12),
        leading=round(max(body_fs, 12) * 1.4, 1),
        alignment=TA_CENTER,
        textColor=_COLOR_ACCENT,
        spaceAfter=8,
    )

    MetaStyle = ParagraphStyle(
        "PubPDFMeta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=body_fs,
        leading=round(body_fs * 1.35, 1),
        alignment=TA_CENTER,
        textColor=_COLOR_SECONDARY,
        spaceAfter=4,
    )

    TocTitleStyle = ParagraphStyle(
        "PubPDFTocTitle",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=h1_fs,
        leading=round(h1_fs * 1.3, 1),
        textColor=_COLOR_PRIMARY,
        spaceAfter=12,
    )

    TocEntryStyle = ParagraphStyle(
        "PubPDFTocEntry",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=body_fs,
        leading=round(body_fs * 1.5, 1),
        textColor=_COLOR_TEXT,
        leftIndent=12,
        spaceAfter=4,
    )

    Heading1Style = ParagraphStyle(
        "PubPDFH1",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=h1_fs,
        leading=round(h1_fs * 1.3, 1),
        textColor=_COLOR_PRIMARY,
        spaceAfter=10,
        spaceBefore=18,
    )

    Heading2Style = ParagraphStyle(
        "PubPDFH2",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=h2_fs,
        leading=round(h2_fs * 1.4, 1),
        textColor=_COLOR_SECONDARY,
        spaceAfter=8,
        spaceBefore=12,
    )

    Heading3Style = ParagraphStyle(
        "PubPDFH3",
        parent=base["Normal"],
        fontName="Helvetica-BoldOblique",
        fontSize=max(body_fs, 11),
        leading=round(max(body_fs, 11) * 1.3, 1),
        textColor=_COLOR_ACCENT,
        spaceAfter=6,
        spaceBefore=10,
    )

    BodyStyle = ParagraphStyle(
        "PubPDFBody",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=body_fs,
        leading=body_lead,
        textColor=_COLOR_TEXT,
        spaceAfter=6,
        spaceBefore=2,
    )

    BulletStyle = ParagraphStyle(
        "PubPDFBullet",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=body_fs,
        leading=body_lead,
        textColor=_COLOR_TEXT,
        leftIndent=18,
        spaceAfter=4,
    )

    return {
        "title":     TitleStyle,
        "subtitle":  SubtitleStyle,
        "meta":      MetaStyle,
        "toc_title": TocTitleStyle,
        "toc_entry": TocEntryStyle,
        "h1":        Heading1Style,
        "h2":        Heading2Style,
        "h3":        Heading3Style,
        "body":      BodyStyle,
        "bullet":    BulletStyle,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers texte
# ─────────────────────────────────────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    """Échappe les caractères XML pour ReportLab."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _inline_md(text: str) -> str:
    """Convertit les marqueurs Markdown inline en balises ReportLab."""
    text = _escape_xml(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"_(.+?)_",       r"<i>\1</i>", text)
    text = re.sub(r"\*(.+?)\*",     r"<i>\1</i>", text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Callbacks de pagination
# ─────────────────────────────────────────────────────────────────────────────

def _on_cover_page(canvas, doc) -> None:
    """Page de couverture : aucun numéro."""


def _on_content_page(canvas, doc) -> None:
    """Pages de contenu : numéro centré en bas."""
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(_COLOR_SUBTLE)
    canvas.drawCentredString(doc.pagesize[0] / 2, 0.9 * cm, str(doc.page))
    canvas.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# Expressions régulières pour le parseur Markdown
# ─────────────────────────────────────────────────────────────────────────────

_HEADING_RE  = re.compile(r"^(#{1,3})\s+(.+)$")
_HR_RE       = re.compile(r"^---+$")
_BULLET_RE   = re.compile(r"^\s*[*\-+]\s+(.+)$")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(.+)$")

# Supprime les commentaires HTML Markdown (<!-- ... -->) avant le rendu PDF.
# Ces commentaires sont utilisés par publication_builder comme marqueurs de
# sections vides et ne doivent jamais apparaître dans les livrables clients.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

_STRUCTURAL_KEYS: frozenset[str] = frozenset({
    "cover",
    "couverture",
    "title page",
    "page de titre",
    "table of contents",
    "table des matières",
})


# ─────────────────────────────────────────────────────────────────────────────
# Extraction depuis publication.md
# ─────────────────────────────────────────────────────────────────────────────

def _extract_title(lines: list[str]) -> str:
    """
    Extrait le titre depuis la section Cover/Couverture de publication.md.

    Ordre de priorité :
      1. Premier texte **gras** dans la section Cover/Couverture
      2. Premier H1 non structurel
      3. Fallback : "Publication"
    """
    in_cover = False
    for line in lines:
        stripped = line.strip()
        m = _HEADING_RE.match(stripped)
        if m:
            key = m.group(2).strip().lower()
            if key in ("cover", "couverture"):
                in_cover = True
                continue
            if key in _STRUCTURAL_KEYS:
                in_cover = False
                continue
        if in_cover and stripped.startswith("**") and stripped.endswith("**"):
            return stripped[2:-2].strip()

    for line in lines:
        m = _HEADING_RE.match(line.strip())
        if m and len(m.group(1)) == 1:
            key = m.group(2).strip().lower()
            if key not in _STRUCTURAL_KEYS:
                return m.group(2).strip()

    return "Publication"


def _extract_toc_entries(lines: list[str]) -> list[str]:
    """
    Extrait les titres H1 du corps du document (hors sections structurelles)
    pour construire la table des matières.
    """
    entries: list[str] = []
    structural_seen = 0

    for line in lines:
        m = _HEADING_RE.match(line.strip())
        if not m:
            continue
        key = m.group(2).strip().lower()
        if key in _STRUCTURAL_KEYS:
            structural_seen += 1
            continue
        if len(m.group(1)) == 1 and structural_seen >= 1:
            entries.append(m.group(2).strip())

    return entries


# ─────────────────────────────────────────────────────────────────────────────
# Pages structurelles (couverture, page de titre, TOC)
# ─────────────────────────────────────────────────────────────────────────────

def _cover_story(
    styles: dict,
    title: str,
    project_name: str,
    labels: dict[str, str],
    page_h: float,
    metadata: dict | None = None,
) -> list:
    """Construit la story de la page de couverture (page 1)."""
    meta     = metadata or {}
    pub_date = meta.get("publication_date") or date.today().isoformat()
    subtitle = meta.get("subtitle", "")
    author   = meta.get("author", "")
    org      = meta.get("organization", "")

    story: list = [
        Spacer(1, page_h * 0.28),
        Paragraph(_escape_xml(title), styles["title"]),
    ]

    if subtitle:
        story += [
            Spacer(1, 0.2 * cm),
            Paragraph(_escape_xml(subtitle), styles["subtitle"]),
        ]

    story += [
        Spacer(1, 0.4 * cm),
        HRFlowable(
            width="50%",
            thickness=1.5,
            color=_COLOR_ACCENT,
            hAlign="CENTER",
        ),
        Spacer(1, 0.5 * cm),
    ]

    if author:
        story.append(Paragraph(_escape_xml(author), styles["meta"]))
    if org:
        story.append(Paragraph(_escape_xml(org), styles["meta"]))

    story += [
        Paragraph(
            f"{_escape_xml(labels['date_label'])} : {_escape_xml(pub_date)}",
            styles["meta"],
        ),
        PageBreak(),
    ]
    return story


def _title_page_story(
    styles: dict,
    title: str,
    project_name: str,
    labels: dict[str, str],
    page_h: float,
    metadata: dict | None = None,
) -> list:
    """Construit la story de la page de titre (page 2)."""
    meta     = metadata or {}
    pub_date = meta.get("publication_date") or date.today().isoformat()
    subtitle = meta.get("subtitle", "")
    author   = meta.get("author", "")
    org      = meta.get("organization", "")

    story: list = [
        Spacer(1, page_h * 0.30),
        Paragraph(_escape_xml(title), styles["title"]),
        Spacer(1, 0.3 * cm),
    ]

    if subtitle:
        story += [
            Paragraph(_escape_xml(subtitle), styles["subtitle"]),
            Spacer(1, 0.15 * cm),
        ]

    if author:
        story.append(Paragraph(_escape_xml(author), styles["meta"]))
    if org:
        story.append(Paragraph(_escape_xml(org), styles["meta"]))

    story += [
        Spacer(1, 0.15 * cm),
        Paragraph(_escape_xml(pub_date), styles["meta"]),
        PageBreak(),
    ]
    return story


def _toc_story(
    styles: dict,
    toc_entries: list[str],
    labels: dict[str, str],
) -> list:
    """Construit la story de la table des matières."""
    story: list = [
        Paragraph(_escape_xml(labels["toc"]), styles["toc_title"]),
        Spacer(1, 0.3 * cm),
    ]
    for entry in toc_entries:
        story.append(Paragraph(f"• {_escape_xml(entry)}", styles["toc_entry"]))
    story.append(PageBreak())
    return story


# ─────────────────────────────────────────────────────────────────────────────
# Corps du document
# ─────────────────────────────────────────────────────────────────────────────

def _body_story(lines: list[str], styles: dict) -> list:
    """
    Convertit le corps de publication.md en story ReportLab.

    Ignore les sections structurelles (Cover, Title Page, TOC).
    Prend en charge :
      - Titres H1 / H2 / H3
      - Listes à puces et listes numérotées
      - Paragraphes normaux avec formatage inline **bold** et _italic_
      - Séparateurs horizontaux (---) → ignorés
    """
    story: list = []
    structural_count = 0

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if _HR_RE.match(stripped):
            i += 1
            continue

        m = _HEADING_RE.match(stripped)
        if m:
            level = len(m.group(1))
            text  = m.group(2).strip()
            key   = text.lower()

            if key in _STRUCTURAL_KEYS:
                structural_count += 1
                i += 1
                continue

            if level == 1:
                story.append(Paragraph(_inline_md(text), styles["h1"]))
            elif level == 2:
                story.append(Paragraph(_inline_md(text), styles["h2"]))
            else:
                story.append(Paragraph(_inline_md(text), styles["h3"]))
            i += 1
            continue

        if not stripped:
            story.append(Spacer(1, 4))
            i += 1
            continue

        bm = _BULLET_RE.match(lines[i])
        if bm:
            story.append(
                Paragraph(f"• {_inline_md(bm.group(1).strip())}", styles["bullet"])
            )
            i += 1
            continue

        nm = _NUMBERED_RE.match(lines[i])
        if nm:
            story.append(
                Paragraph(f"• {_inline_md(nm.group(1).strip())}", styles["bullet"])
            )
            i += 1
            continue

        story.append(Paragraph(_inline_md(stripped), styles["body"]))
        i += 1

    return story


# ─────────────────────────────────────────────────────────────────────────────
# Mise à jour du project_state
# ─────────────────────────────────────────────────────────────────────────────

def _save_pdf_state(
    project_name: str,
    *,
    generated: bool,
    now: str,
    path: str | None = None,
    error: str | None = None,
    theme: str | None = None,
) -> None:
    state = load_project_state(project_name)
    state.setdefault("publication", {})

    entry: dict = {"generated": generated, "generated_at": now}
    if generated and path:
        entry["path"] = path
    if not generated and error:
        entry["error"] = error
    if theme:
        entry["theme"] = theme

    state["publication"]["pdf_engine"] = entry
    save_project_state(project_name, state)
    print("[publication_pdf_engine] project_state.json mis à jour.")


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée public
# ─────────────────────────────────────────────────────────────────────────────

def _cover_pdf_story(cover_pdf_path: Path, page_w: float, page_h: float) -> list:
    """
    Insère une image de couverture comme première page du PDF final.

    Priorité :
        1. cover_image.png  (moteur image externe : LOCAL_FILE / SD / ComfyUI)
        2. cover.png        (cover_builder textuel rasterisé)

    Si aucune image n'est disponible, retourne [] (fallback couverture textuelle).
    """
    cover_dir = cover_pdf_path.parent

    # Priorité à cover_image.png (moteur image externe)
    for candidate_name in ("cover_image.png", "cover.png"):
        candidate = cover_dir / candidate_name
        if candidate.exists() and candidate.stat().st_size > 0:
            try:
                img = RLImage(str(candidate), width=page_w, height=page_h)
                return [img, PageBreak()]
            except Exception:
                continue

    # Fallback silencieux : la couverture textuelle intégrée sera utilisée
    return []


def generate_publication_pdf(
    project_name: str,
    include_generated_cover: bool = True,
) -> Path | None:
    """
    Génère publication.pdf depuis publication.md.

    Entrée  : sortie/<project_name>/publication/publication.md
    Sortie  : sortie/<project_name>/publication/publication.pdf

    Args:
        project_name:            Nom du projet.
        include_generated_cover: Si True et que cover.pdf existe dans
                                 publication/cover/, l'utilise comme première
                                 page (via cover.png si disponible).
                                 Sinon utilise la couverture textuelle intégrée.

    Retourne le chemin du PDF généré, ou None en cas d'erreur.
    """
    pub_dir  = SORTIE_DIR / project_name / "publication"
    md_path  = pub_dir / "publication.md"
    pdf_path = pub_dir / "publication.pdf"
    now      = datetime.now().isoformat(timespec="seconds")

    print(f"[publication_pdf_engine] Génération PDF — projet : {project_name}")
    log_event({
        "step":    "publication_pdf_engine",
        "project": project_name,
        "action":  "start",
    })

    # ── Sélection de la source : préférer la version sanitized ───────────────
    sanitized_path = pub_dir / "publication_sanitized.md"
    effective_path = sanitized_path if sanitized_path.exists() else md_path

    if not effective_path.exists():
        msg = f"publication.md introuvable : {md_path}"
        print(f"[publication_pdf_engine] ERREUR : {msg}")
        log_event({
            "step":    "publication_pdf_engine",
            "project": project_name,
            "action":  "error",
            "error":   msg,
        })
        _save_pdf_state(project_name, generated=False, error=msg, now=now)
        return None

    _source_label = "publication_sanitized.md" if sanitized_path.exists() else "publication.md"
    print(f"[publication_pdf_engine] Publication utilisée : {effective_path}  [{_source_label}]")
    log_event({
        "step":    "publication_pdf_engine",
        "project": project_name,
        "action":  "source",
        "path":    str(effective_path),
        "source":  _source_label,
    })

    # ── Lecture ───────────────────────────────────────────────────────────
    md_text = effective_path.read_text(encoding="utf-8")
    # Supprimer les éventuels commentaires HTML résiduels avant tout traitement
    md_text = _HTML_COMMENT_RE.sub("", md_text)
    lines   = md_text.splitlines()

    # ── Langue documentaire ───────────────────────────────────────────────
    lang   = get_document_language(project_name, fallback_text=md_text)
    labels = _LABELS.get(lang, _LABELS["en"])
    print(f"[publication_pdf_engine] Langue documentaire : {lang}")

    # ── Mode de publication ───────────────────────────────────────────────
    state            = load_project_state(project_name)
    publication_mode = state.get("publication_mode") or "BOOK"
    print(f"[publication_pdf_engine] Mode de publication : {publication_mode}")

    # ── Chargement du thème ───────────────────────────────────────────────
    theme = get_publication_theme(publication_mode, lang)
    print(
        f"[publication_pdf_engine] Thème chargé : {theme['mode']} | "
        f"cover_style={theme['cover_style']} | "
        f"body={theme['body_font_size']}pt | "
        f"h1={theme['heading1_font_size']}pt"
    )
    log_event({
        "step":           "publication_pdf_engine",
        "project":        project_name,
        "action":         "theme_loaded",
        "mode":           theme["mode"],
        "cover_style":    theme["cover_style"],
        "body_font_size": theme["body_font_size"],
    })

    # Surcharger le label TOC avec le libellé du thème (respecte la langue)
    labels = dict(labels)
    labels["toc"] = theme.get("toc_title", labels["toc"])

    # ── Métadonnées de publication ────────────────────────────────────────
    pub_meta = get_publication_metadata(project_name)
    print(
        f"[publication_pdf_engine] Métadonnées appliquées au PDF — "
        f"titre={pub_meta['title']!r} | auteur={pub_meta['author']!r}"
    )
    log_event({
        "step":    "publication_pdf_engine",
        "project": project_name,
        "action":  "metadata_applied",
        "title":   pub_meta["title"],
        "author":  pub_meta["author"],
    })

    # ── Extraction titre + TOC ────────────────────────────────────────────
    # Le titre des métadonnées prend la priorité sur celui extrait du MD
    title_from_meta = pub_meta.get("title", "").strip()
    title_from_md   = _extract_title(lines)
    title           = title_from_meta if title_from_meta else title_from_md
    toc_entries     = _extract_toc_entries(lines)

    print(f"[publication_pdf_engine] Titre : « {title} »")
    print(f"[publication_pdf_engine] TOC : {len(toc_entries)} entrée(s)")

    # ── Construction du PDF ───────────────────────────────────────────────
    try:
        pub_dir.mkdir(parents=True, exist_ok=True)

        styles   = _build_styles(theme)
        pagesize = _PAGESIZES.get(theme.get("page_size", "LETTER"), LETTER)
        page_w, page_h = pagesize

        # Marges en points depuis le thème (1 inch = 72 pt)
        m_top    = theme.get("top_margin",    72)
        m_bottom = theme.get("bottom_margin", 72)
        m_left   = theme.get("left_margin",   72)
        m_right  = theme.get("right_margin",  72)

        def _make_frame(frame_id: str) -> Frame:
            return Frame(
                m_left,
                m_bottom,
                page_w - m_left - m_right,
                page_h - m_top  - m_bottom,
                id=frame_id,
            )

        cover_tpl = PageTemplate(
            id="cover",
            frames=[_make_frame("cover")],
            onPage=_on_cover_page,
        )
        content_tpl = PageTemplate(
            id="content",
            frames=[_make_frame("content")],
            onPage=_on_content_page,
        )

        # Propriétés internes du PDF (métadonnées de publication)
        pdf_author  = pub_meta.get("author") or "PublishForge"
        pdf_subject = pub_meta.get("subtitle") or f"Publication — {project_name}"
        pdf_creator = "TranscriptionAI / PublishForge"
        if pub_meta.get("organization"):
            pdf_creator = f"{pub_meta['organization']} / PublishForge"

        doc = BaseDocTemplate(
            str(pdf_path),
            pagesize=pagesize,
            pageTemplates=[cover_tpl, content_tpl],
            title=title,
            author=pdf_author,
            subject=pdf_subject,
            creator=pdf_creator,
        )

        # ── Story ─────────────────────────────────────────────────────────
        story: list = []

        # Chemins des couvertures disponibles
        _cover_pub_dir    = SORTIE_DIR / project_name / "publication" / "cover"
        generated_cover_pdf = _cover_pub_dir / "cover.pdf"
        cover_image_png     = _cover_pub_dir / "cover_image.png"
        cover_png           = _cover_pub_dir / "cover.png"

        # Une image de couverture est disponible si cover_image.png ou cover.png existe,
        # ou si cover.pdf existe (lequel peut fournir cover.png via _cover_pdf_story)
        _has_cover_image = (
            cover_image_png.exists() or cover_png.exists() or generated_cover_pdf.exists()
        )
        _use_generated_cover = (
            include_generated_cover
            and _has_cover_image
            and theme.get("include_cover", True)
        )

        # 1. Couverture (template "cover" → pas de numéro)
        if _use_generated_cover:
            _cover_pages = _cover_pdf_story(generated_cover_pdf, page_w, page_h)
            if _cover_pages:
                _used_img = (
                    cover_image_png if cover_image_png.exists() else cover_png
                )
                print(
                    f"[publication_pdf_engine] Couverture image utilisée : {_used_img}"
                )
                story.extend(_cover_pages)
            else:
                # Fallback : couverture textuelle intégrée
                if theme.get("include_cover", True):
                    story.extend(
                        _cover_story(styles, title, project_name, labels, page_h, pub_meta)
                    )
        elif theme.get("include_cover", True):
            story.extend(_cover_story(styles, title, project_name, labels, page_h, pub_meta))

        # Basculer sur le template "content" pour les pages suivantes
        story.append(NextPageTemplate("content"))

        # 2. Page de titre
        if theme.get("include_title_page", True):
            story.extend(_title_page_story(styles, title, project_name, labels, page_h, pub_meta))

        # 3. Table des matières (si des entrées existent et si le thème l'active)
        if theme.get("include_toc", True) and toc_entries:
            story.extend(_toc_story(styles, toc_entries, labels))

        # 4. Corps du document
        story.extend(_body_story(lines, styles))

        doc.build(story)

    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        print(f"[publication_pdf_engine] ERREUR génération : {msg}")
        log_event({
            "step":    "publication_pdf_engine",
            "project": project_name,
            "action":  "error",
            "error":   msg,
        })
        _save_pdf_state(project_name, generated=False, error=msg, now=now)
        return None

    print(f"[publication_pdf_engine] PDF généré : {pdf_path}")
    log_event({
        "step":    "publication_pdf_engine",
        "project": project_name,
        "action":  "generated",
        "path":    str(pdf_path),
        "mode":    publication_mode,
        "lang":    lang,
    })

    _save_pdf_state(
        project_name,
        generated=True,
        path=str(pdf_path),
        now=now,
        theme=publication_mode,
    )
    return pdf_path
