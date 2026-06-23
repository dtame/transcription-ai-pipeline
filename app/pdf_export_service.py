from pathlib import Path
from datetime import datetime
import hashlib
import json
import re

from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, NextPageTemplate,
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable, Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import cm, inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors

from app.paths import SORTIE_DIR
from app.project_state import load_project_state, save_project_state


def _file_hash(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _get_final_dir(project_name: str) -> Path:
    return SORTIE_DIR / project_name / "final"


def _get_md_path(project_name: str) -> Path:
    """
    Returns the best available Markdown source for the basic PDF export.

    Priority:
      1. document_clean.md  (clean version without technical metadata)
      2. document_final.md  (fallback — internal debug version)
    """
    final_dir = _get_final_dir(project_name)
    clean_md = final_dir / "document_clean.md"
    if clean_md.exists() and clean_md.stat().st_size > 100:
        return clean_md
    return final_dir / "document_final.md"


def _get_pdf_path(project_name: str) -> Path:
    return _get_final_dir(project_name) / "document_final.pdf"


def _get_clean_pdf_path(project_name: str) -> Path:
    return _get_final_dir(project_name) / "document_clean.pdf"


def _should_regenerate(
    state: dict,
    pdf_path: Path,
    current_signature: str,
) -> bool:
    if not pdf_path.exists():
        return True

    exports = state.get("exports", {})
    pdf_state = exports.get("pdf", {})

    if not pdf_state.get("generated"):
        return True

    if pdf_state.get("source_signature") != current_signature:
        return True

    return False


def _build_styles() -> dict:
    base = getSampleStyleSheet()

    styles = {
        "h1": ParagraphStyle(
            "H1PDF",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=26,
            spaceAfter=14,
            spaceBefore=20,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "h2": ParagraphStyle(
            "H2PDF",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=22,
            spaceAfter=10,
            spaceBefore=16,
            textColor=colors.HexColor("#2a2a2a"),
        ),
        "h3": ParagraphStyle(
            "H3PDF",
            parent=base["Heading3"],
            fontName="Helvetica-BoldOblique",
            fontSize=13,
            leading=18,
            spaceAfter=8,
            spaceBefore=12,
            textColor=colors.HexColor("#3a3a3a"),
        ),
        "body": ParagraphStyle(
            "BodyPDF",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            spaceAfter=6,
            spaceBefore=2,
        ),
        "bullet": ParagraphStyle(
            "BulletPDF",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            spaceAfter=4,
            spaceBefore=2,
            leftIndent=18,
            bulletIndent=0,
        ),
        "quote": ParagraphStyle(
            "QuotePDF",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=11,
            leading=16,
            spaceAfter=8,
            spaceBefore=8,
            leftIndent=24,
            rightIndent=24,
            textColor=colors.HexColor("#555555"),
        ),
        "code": ParagraphStyle(
            "CodePDF",
            parent=base["Code"],
            fontName="Courier",
            fontSize=9,
            leading=13,
            spaceAfter=8,
            spaceBefore=8,
            leftIndent=12,
            backColor=colors.HexColor("#f5f5f5"),
        ),
        "hr": ParagraphStyle(
            "HRPDF",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=6,
            leading=8,
            spaceAfter=8,
            spaceBefore=8,
            textColor=colors.HexColor("#cccccc"),
        ),
    }
    return styles


def _add_page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#888888"))
    page_text = f"Page {doc.page}"
    canvas.drawCentredString(
        doc.pagesize[0] / 2,
        1.2 * cm,
        page_text,
    )
    canvas.restoreState()


def _escape_xml(text: str) -> str:
    """Escape characters that would break ReportLab's XML parser."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _convert_markdown_to_story(md_text: str, styles: dict) -> list:
    """
    Parse Markdown line by line and build a ReportLab story (list of Flowables).

    Supported elements:
      - H1 / H2 / H3 headings
      - Bullet lists (* or -)
      - Block quotes (>)
      - Code fences (``` ... ```)
      - Horizontal rules (--- or ***)
      - Normal paragraphs
      - Blank lines (vertical space)
    """
    story = []
    lines = md_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Code fence (``` ... ```)
        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if code_lines:
                code_text = _escape_xml("\n".join(code_lines))
                code_text = code_text.replace("\n", "<br/>")
                story.append(Paragraph(code_text, styles["code"]))
            i += 1
            continue

        # Horizontal rule → ligne fine centrée
        if re.match(r"^-{3,}$", stripped) or re.match(r"^\*{3,}$", stripped):
            story.append(
                HRFlowable(
                    width="60%",
                    thickness=0.5,
                    color=colors.HexColor("#cccccc"),
                    hAlign="CENTER",
                    spaceAfter=8,
                    spaceBefore=8,
                )
            )
            i += 1
            continue

        # H3
        if stripped.startswith("### "):
            text = _escape_xml(stripped[4:].strip())
            story.append(Paragraph(text, styles["h3"]))
            i += 1
            continue

        # H2
        if stripped.startswith("## "):
            text = _escape_xml(stripped[3:].strip())
            story.append(Paragraph(text, styles["h2"]))
            i += 1
            continue

        # H1
        if stripped.startswith("# "):
            text = _escape_xml(stripped[2:].strip())
            story.append(Paragraph(text, styles["h1"]))
            i += 1
            continue

        # Bullet list (* or -)
        if re.match(r"^[*\-] ", stripped):
            text = _escape_xml(re.sub(r"^[*\-] ", "", stripped))
            story.append(Paragraph(f"• {text}", styles["bullet"]))
            i += 1
            continue

        # Block quote (>)
        if stripped.startswith("> "):
            text = _escape_xml(stripped[2:].strip())
            story.append(Paragraph(text, styles["quote"]))
            i += 1
            continue

        # Blank line → small vertical space
        if stripped == "":
            story.append(Spacer(1, 6))
            i += 1
            continue

        # Normal paragraph
        text = _escape_xml(stripped)
        story.append(Paragraph(text, styles["body"]))
        i += 1

    return story


def export_pdf(project_name: str) -> Path | None:
    """
    Génère document_final.pdf à partir de document_final.md.

    Régénère uniquement si :
      - le PDF n'existe pas
      - le MD source a changé (signature différente)
      - la signature enregistrée ne correspond plus

    Raises:
        RuntimeError: si le fichier source Markdown est absent.
    """
    md_path = _get_md_path(project_name)
    pdf_path = _get_pdf_path(project_name)

    if not md_path.exists():
        raise RuntimeError(
            f"[pdf_export] Fichier source absent pour le projet '{project_name}' : "
            f"{md_path.name}. "
            "Assurez-vous que l'étape final_document a réussi."
        )

    current_signature = _file_hash(md_path)
    state = load_project_state(project_name)

    if not _should_regenerate(state, pdf_path, current_signature):
        print(f"[pdf_export] PDF déjà à jour : {pdf_path}")
        return pdf_path

    md_text = md_path.read_text(encoding="utf-8")
    styles = _build_styles()

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"TranscriptionAI - {project_name}",
        author="TranscriptionAI",
        subject="Document généré automatiquement",
    )

    story = _convert_markdown_to_story(md_text, styles)

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)

    updated_at = datetime.now().isoformat(timespec="seconds")

    if "exports" not in state:
        state["exports"] = {}

    state["exports"]["pdf"] = {
        "generated": True,
        "path": str(pdf_path),
        "updated_at": updated_at,
        "source_signature": current_signature,
    }

    save_project_state(project_name, state)

    print(f"[pdf_export] PDF généré : {pdf_path}")

    return pdf_path


# ===========================================================================
# Publication PDF — export professionnel avec gabarits et thèmes
# ===========================================================================

_PAGE_SIZES_PDF: dict[str, tuple] = {
    "letter":      letter,
    "a4":          A4,
    "six_by_nine": (6.0 * inch, 9.0 * inch),
    "digest":      (5.5 * inch, 8.5 * inch),
}

_PAGE_MARGINS_PDF: dict[str, float] = {
    "letter":      2.0 * cm,
    "a4":          2.0 * cm,
    "six_by_nine": 1.5 * cm,
    "digest":      1.5 * cm,
}

_FONT_CONFIGS_PDF: dict[str, dict] = {
    "classic": {
        "h1_font":   "Times-Bold",
        "h2_font":   "Times-Bold",
        "h3_font":   "Times-BoldItalic",
        "body_font": "Times-Roman",
        "h1_size": 22, "h2_size": 16, "h3_size": 13, "body_size": 11,
        "leading_factor": 1.4,
    },
    "modern": {
        "h1_font":   "Helvetica-Bold",
        "h2_font":   "Helvetica-Bold",
        "h3_font":   "Helvetica-BoldOblique",
        "body_font": "Helvetica",
        "h1_size": 22, "h2_size": 16, "h3_size": 13, "body_size": 11,
        "leading_factor": 1.4,
    },
    "elegant": {
        "h1_font":   "Times-Bold",
        "h2_font":   "Times-Bold",
        "h3_font":   "Times-BoldItalic",
        "body_font": "Times-Roman",
        "h1_size": 24, "h2_size": 18, "h3_size": 14, "body_size": 12,
        "leading_factor": 1.6,
    },
    "readable": {
        "h1_font":   "Helvetica-Bold",
        "h2_font":   "Helvetica-Bold",
        "h3_font":   "Helvetica-BoldOblique",
        "body_font": "Helvetica",
        "h1_size": 20, "h2_size": 15, "h3_size": 12, "body_size": 12,
        "leading_factor": 1.5,
    },
}


def _build_pub_styles(font_cfg: dict, theme_colors: dict) -> dict:
    base = getSampleStyleSheet()
    primary = theme_colors.get("primary", "#1a1a1a")
    accent = theme_colors.get("accent", "#666666")
    lf = font_cfg["leading_factor"]

    def leading(size: int) -> float:
        return size * lf

    return {
        "cover_title": ParagraphStyle(
            "PubCoverTitle",
            parent=base["Normal"],
            fontName=font_cfg["h1_font"],
            fontSize=32,
            leading=42,
            alignment=TA_CENTER,
            textColor=colors.HexColor(primary),
            spaceAfter=12,
        ),
        "cover_subtitle": ParagraphStyle(
            "PubCoverSubtitle",
            parent=base["Normal"],
            fontName=font_cfg["h2_font"],
            fontSize=18,
            leading=26,
            alignment=TA_CENTER,
            textColor=colors.HexColor(accent),
            spaceAfter=10,
        ),
        "cover_author": ParagraphStyle(
            "PubCoverAuthor",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor(primary),
            spaceAfter=4,
        ),
        "cover_meta": ParagraphStyle(
            "PubCoverMeta",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor(accent),
            spaceAfter=4,
        ),
        "cover_version": ParagraphStyle(
            "PubCoverVersion",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#aaaaaa"),
            spaceAfter=4,
        ),
        "toc_title": ParagraphStyle(
            "PubTOCTitle",
            parent=base["Normal"],
            fontName=font_cfg["h2_font"],
            fontSize=font_cfg["h2_size"],
            leading=leading(font_cfg["h2_size"]),
            textColor=colors.HexColor(primary),
            spaceAfter=10,
            spaceBefore=6,
        ),
        "toc_h1": ParagraphStyle(
            "PubTOCH1",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=12,
            leading=16,
            leftIndent=0,
            textColor=colors.HexColor(primary),
            spaceAfter=3,
        ),
        "toc_h2": ParagraphStyle(
            "PubTOCH2",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=11,
            leading=15,
            leftIndent=14,
            textColor=colors.HexColor(accent),
            spaceAfter=2,
        ),
        "toc_h3": ParagraphStyle(
            "PubTOCH3",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=10,
            leading=14,
            leftIndent=28,
            textColor=colors.HexColor(accent),
            spaceAfter=2,
        ),
        "h1": ParagraphStyle(
            "PubH1",
            parent=base["Normal"],
            fontName=font_cfg["h1_font"],
            fontSize=font_cfg["h1_size"],
            leading=leading(font_cfg["h1_size"]),
            textColor=colors.HexColor(primary),
            spaceAfter=10,
            spaceBefore=16,
        ),
        "h2": ParagraphStyle(
            "PubH2",
            parent=base["Normal"],
            fontName=font_cfg["h2_font"],
            fontSize=font_cfg["h2_size"],
            leading=leading(font_cfg["h2_size"]),
            textColor=colors.HexColor(primary),
            spaceAfter=8,
            spaceBefore=12,
        ),
        "h3": ParagraphStyle(
            "PubH3",
            parent=base["Normal"],
            fontName=font_cfg["h3_font"],
            fontSize=font_cfg["h3_size"],
            leading=leading(font_cfg["h3_size"]),
            textColor=colors.HexColor(accent),
            spaceAfter=6,
            spaceBefore=10,
        ),
        "body": ParagraphStyle(
            "PubBody",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=font_cfg["body_size"],
            leading=leading(font_cfg["body_size"]),
            spaceAfter=5,
            spaceBefore=2,
        ),
        "bullet": ParagraphStyle(
            "PubBullet",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=font_cfg["body_size"],
            leading=leading(font_cfg["body_size"]),
            spaceAfter=3,
            spaceBefore=2,
            leftIndent=18,
        ),
        "quote": ParagraphStyle(
            "PubQuote",
            parent=base["Normal"],
            fontName=font_cfg["body_font"],
            fontSize=font_cfg["body_size"],
            leading=leading(font_cfg["body_size"]),
            spaceAfter=8,
            spaceBefore=8,
            leftIndent=24,
            rightIndent=24,
            textColor=colors.HexColor("#555555"),
        ),
        "code": ParagraphStyle(
            "PubCode",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=9,
            leading=13,
            spaceAfter=8,
            spaceBefore=8,
            leftIndent=12,
            backColor=colors.HexColor("#f5f5f5"),
        ),
        "hr": ParagraphStyle(
            "PubHR",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=6,
            leading=8,
            spaceAfter=8,
            spaceBefore=8,
            textColor=colors.HexColor("#cccccc"),
        ),
    }


def _make_page_callback(settings: dict, margin: float) -> callable:
    """Retourne un callback onPage qui ajoute en-têtes, pieds de page et numéros."""
    include_page_numbers = settings.get("include_page_numbers", True)
    include_headers = settings.get("include_headers", True)
    include_footers = settings.get("include_footers", True)
    title = settings.get("title", "")
    org = settings.get("organization", "")

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#888888"))

        page_width = doc.pagesize[0]
        page_height = doc.pagesize[1]

        # Sauter la page de couverture (page 1)
        if doc.page > 1:
            if include_headers and title:
                canvas.drawCentredString(
                    page_width / 2,
                    page_height - margin * 0.7,
                    title,
                )

            if include_footers:
                footer_parts: list[str] = []
                if org:
                    footer_parts.append(org)
                if include_page_numbers:
                    footer_parts.append(f"— {doc.page} —")
                if footer_parts:
                    canvas.drawCentredString(
                        page_width / 2,
                        margin * 0.6,
                        "  ".join(footer_parts),
                    )

        canvas.restoreState()

    return _on_page


def _add_cover_story(
    story: list,
    settings: dict,
    styles: dict,
    pagesize: tuple,
) -> None:
    """Ajoute les éléments de couverture à la story ReportLab."""
    colors_theme = settings.get("theme_colors", {})
    accent = colors_theme.get("accent", "#666666")
    page_height = pagesize[1]

    # Espace supérieur (environ 1/4 de la page)
    story.append(Spacer(1, page_height * 0.22))

    # Titre
    story.append(Paragraph(_escape_xml(settings.get("title", "")), styles["cover_title"]))
    story.append(Spacer(1, 0.3 * inch))

    # Sous-titre
    subtitle = settings.get("subtitle", "")
    if subtitle:
        story.append(Paragraph(_escape_xml(subtitle), styles["cover_subtitle"]))
        story.append(Spacer(1, 0.2 * inch))

    # Séparateur décoratif
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        HRFlowable(
            width="55%",
            thickness=1.5,
            color=colors.HexColor(accent),
            hAlign="CENTER",
        )
    )
    story.append(Spacer(1, page_height * 0.15))

    # Auteur
    if settings.get("include_author", True):
        author = settings.get("author", "")
        if author:
            story.append(Paragraph(_escape_xml(author), styles["cover_author"]))

    # Organisation
    if settings.get("include_organization", True):
        org = settings.get("organization", "")
        if org:
            story.append(Paragraph(_escape_xml(org), styles["cover_meta"]))

    # Date
    if settings.get("include_date", True):
        date_display = settings.get("date") or settings.get("_generated_date", "")
        if date_display:
            story.append(
                Paragraph(_escape_xml(date_display), styles["cover_meta"])
            )

    # Version
    version = settings.get("version", "")
    if version:
        story.append(
            Paragraph(_escape_xml(f"Version {version}"), styles["cover_version"])
        )

    story.append(PageBreak())


def _draw_cover_image_on_canvas(
    canvas,
    cover_path: Path,
    page_w: float,
    page_h: float,
) -> None:
    """
    Dessine la couverture directement sur le canvas ReportLab.

    L'image remplit toute la page en conservant son ratio (preserveAspectRatio=True,
    centré). Pour les couvertures générées aux dimensions standard du format de page,
    le remplissage est exact. Pour les images importées d'un autre ratio, un léger
    letterboxing peut apparaître.

    Ne lève jamais d'exception : les erreurs sont loguées et la page reste blanche.
    """
    canvas.drawImage(
        str(cover_path),
        0,
        0,
        width=page_w,
        height=page_h,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def _add_toc_story(
    story: list,
    headings: list[dict],
    styles: dict,
) -> None:
    """Ajoute une table des matières statique à la story."""
    story.append(Paragraph("Table des matières", styles["toc_title"]))
    story.append(Spacer(1, 0.15 * inch))

    for h in headings:
        level = h["level"]
        text = _escape_xml(h["title"])
        if level == 3:
            story.append(Paragraph(f"    {text}", styles["toc_h3"]))
        elif level == 2:
            story.append(Paragraph(f"  {text}", styles["toc_h2"]))
        else:
            story.append(Paragraph(text, styles["toc_h1"]))

    story.append(PageBreak())


def _convert_markdown_to_story_pub(md_text: str, styles: dict) -> list:
    """Variante de _convert_markdown_to_story avec styles de publication."""
    story: list = []
    lines = md_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Bloc de code
        if stripped.startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if code_lines:
                code_text = _escape_xml("\n".join(code_lines)).replace("\n", "<br/>")
                story.append(Paragraph(code_text, styles["code"]))
            i += 1
            continue

        # Séparateur → ligne fine centrée
        if re.match(r"^-{3,}$", stripped) or re.match(r"^\*{3,}$", stripped):
            story.append(
                HRFlowable(
                    width="55%",
                    thickness=0.5,
                    color=colors.HexColor("#cccccc"),
                    hAlign="CENTER",
                    spaceAfter=8,
                    spaceBefore=8,
                )
            )
            i += 1
            continue

        # H1
        if stripped.startswith("# "):
            story.append(
                Paragraph(_escape_xml(stripped[2:].strip()), styles["h1"])
            )
            i += 1
            continue

        # H2
        if stripped.startswith("## "):
            story.append(
                Paragraph(_escape_xml(stripped[3:].strip()), styles["h2"])
            )
            i += 1
            continue

        # H3
        if stripped.startswith("### "):
            story.append(
                Paragraph(_escape_xml(stripped[4:].strip()), styles["h3"])
            )
            i += 1
            continue

        # Liste à puces
        if re.match(r"^[*\-] ", stripped):
            text = _escape_xml(re.sub(r"^[*\-] ", "", stripped))
            story.append(Paragraph(f"• {text}", styles["bullet"]))
            i += 1
            continue

        # Citation
        if stripped.startswith("> "):
            story.append(
                Paragraph(_escape_xml(stripped[2:].strip()), styles["quote"])
            )
            i += 1
            continue

        # Ligne vide
        if stripped == "":
            story.append(Spacer(1, 5))
            i += 1
            continue

        # Paragraphe normal
        story.append(Paragraph(_escape_xml(stripped), styles["body"]))
        i += 1

    return story


def _pub_settings_signature(settings: dict) -> str:
    relevant = {
        k: v
        for k, v in settings.items()
        if not k.startswith("_")
        and k not in ("analysis", "theme_colors")
        and isinstance(v, (str, bool, int, float))
    }
    return hashlib.md5(
        json.dumps(relevant, sort_keys=True).encode()
    ).hexdigest()


def export_publication_pdf(project_name: str) -> Path | None:
    """
    Génère final/document_publication.pdf.

    Applique :
    - Couverture pleine page (image dessinée directement sur canvas, sans frame)
      ou couverture typographique si aucune image n'est disponible
    - Table des matières statique
    - Styles selon template/theme/font_style
    - Format de page selon page_size
    - Métadonnées PDF (titre, auteur, sujet)
    - En-têtes (titre), pieds de page (organisation + numéro)

    Architecture PDF :
    - Avec image cover : BaseDocTemplate avec 2 PageTemplate
        • 'cover'   : frame pleine page, image dessinée par onPage via canvas.drawImage
        • 'content' : frame avec marges normales, en-têtes/pieds de page
    - Sans image cover : BaseDocTemplate avec 1 PageTemplate 'content'

    Ne reconstruit pas si les sources n'ont pas changé.
    """
    from app.publication_template_service import (
        resolve_publication_settings,
        extract_headings,
    )

    final_dir = SORTIE_DIR / project_name / "final"
    pub_md_path = final_dir / "document_publication.md"
    final_md_path = final_dir / "document_final.md"
    pub_pdf_path = final_dir / "document_publication.pdf"

    if not pub_md_path.exists():
        raise RuntimeError(
            f"[pdf_export] document_publication.md introuvable "
            f"pour le projet '{project_name}'. "
            "Assurez-vous que l'étape publication_markdown a réussi."
        )

    # Utiliser document_publication.md (déjà nettoyé) pour le contenu du PDF
    # Fallback sur document_clean.md, puis document_final.md
    clean_md_path = final_dir / "document_clean.md"

    if pub_md_path.exists():
        publication_content = pub_md_path.read_text(encoding="utf-8")
    elif clean_md_path.exists():
        publication_content = clean_md_path.read_text(encoding="utf-8")
    elif final_md_path.exists():
        from app.publication_cleaner import clean_publication_markdown
        publication_content = clean_publication_markdown(
            final_md_path.read_text(encoding="utf-8")
        )
    else:
        publication_content = ""

    final_content = publication_content
    settings = resolve_publication_settings(project_name, final_content)

    from app.cover_generation_service import get_cover_path

    cover_path = get_cover_path(project_name)

    if not cover_path:
        print("[cover] aucune couverture disponible")

    cover_sig = _file_hash(cover_path) if cover_path else "none"

    pub_md_sig = _file_hash(pub_md_path)
    combined_sig = f"{pub_md_sig}:{_pub_settings_signature(settings)}:{cover_sig}"

    state = load_project_state(project_name)
    pub_pdf_state = state.get("publication", {}).get("pdf", {})

    if (
        pub_pdf_path.exists()
        and pub_pdf_state.get("generated")
        and pub_pdf_state.get("source_signature") == combined_sig
    ):
        print(f"[pdf_export] PDF publication déjà à jour : {pub_pdf_path}")
        return pub_pdf_path

    font_cfg = _FONT_CONFIGS_PDF.get(
        settings["font_style"],
        _FONT_CONFIGS_PDF["modern"],
    )
    theme_colors = settings["theme_colors"]
    pagesize = _PAGE_SIZES_PDF.get(settings["page_size"], A4)
    margin = _PAGE_MARGINS_PDF.get(settings["page_size"], 2.0 * cm)

    pub_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Sujet enrichi avec mots-clés si disponibles
    subject = settings.get("subtitle", "Document de publication")
    keywords = settings.get("keywords", "")
    if keywords:
        subject = f"{subject} — {keywords}" if subject else keywords

    pub_styles = _build_pub_styles(font_cfg, theme_colors)
    on_page_cb = _make_page_callback(settings, margin)

    page_w, page_h = pagesize
    use_image_cover = bool(cover_path) and settings.get("include_cover", True)

    # ------------------------------------------------------------------
    # Frames et page templates
    # ------------------------------------------------------------------

    # Frame de contenu (avec marges) — identique au SimpleDocTemplate précédent
    content_frame = Frame(
        margin,                     # x = leftMargin
        margin * 1.2,               # y = bottomMargin
        page_w - 2 * margin,        # width
        page_h - 2.4 * margin,      # height = page_h - topMargin - bottomMargin
        id="content",
    )

    content_tpl = PageTemplate(
        id="content",
        frames=[content_frame],
        onPage=on_page_cb,
    )

    if use_image_cover:
        # Frame pleine page pour la couverture image (aucune marge)
        cover_frame = Frame(
            0, 0, page_w, page_h,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
            id="cover",
        )

        def on_cover_page(canvas, doc):
            canvas.saveState()
            try:
                _draw_cover_image_on_canvas(canvas, cover_path, page_w, page_h)
            except Exception as exc:
                print(f"[cover] erreur dessin couverture PDF : {exc}")
            canvas.restoreState()

        cover_tpl = PageTemplate(
            id="cover",
            frames=[cover_frame],
            onPage=on_cover_page,
        )
        page_templates = [cover_tpl, content_tpl]
    else:
        page_templates = [content_tpl]

    doc = BaseDocTemplate(
        str(pub_pdf_path),
        pagesize=pagesize,
        pageTemplates=page_templates,
        title=settings.get("title", project_name),
        author=settings.get("author", "TranscriptionAI"),
        subject=subject,
        creator="TranscriptionAI",
    )

    # ------------------------------------------------------------------
    # Story
    # ------------------------------------------------------------------

    story: list = []

    if settings.get("include_cover", True):
        if use_image_cover:
            # La couverture est dessinée par on_cover_page → on avance
            # simplement vers la page suivante (template 'content')
            story.append(NextPageTemplate("content"))
            story.append(PageBreak())
        else:
            # Couverture typographique dans la story
            _add_cover_story(story, settings, pub_styles, pagesize)

    # Table des matières (titres publiables uniquement)
    if settings.get("include_toc", True) and final_content:
        headings = extract_headings(final_content, publishable_only=True)
        if headings:
            _add_toc_story(story, headings, pub_styles)

    # Contenu principal (version nettoyée de publication)
    story.extend(_convert_markdown_to_story_pub(publication_content, pub_styles))

    doc.build(story)

    updated_at = datetime.now().isoformat(timespec="seconds")

    if "publication" not in state:
        state["publication"] = {}

    state["publication"]["pdf"] = {
        "generated": True,
        "path": str(pub_pdf_path),
        "source_signature": combined_sig,
        "updated_at": updated_at,
    }

    # Mise à jour de la section cover dans project_state
    if "cover" not in state:
        state["cover"] = {}

    state["cover"]["pdf_ready"] = True
    state["cover"]["inserted_into_pdf"] = use_image_cover

    save_project_state(project_name, state)

    print(f"[pdf_export] PDF publication généré : {pub_pdf_path}")
    return pub_pdf_path
