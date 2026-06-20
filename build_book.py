from app.paths import SORTIE_DIR

from book.transcript_parser import parse_transcript_file
from book.sentence_merger import merge_segments
from book.paragraph_builder import build_paragraphs
from book.paragraph_semantic_cleaner import clean_paragraphs
from book.outline_builder import build_outline
from book.markdown_builder import build_markdown


def main() -> None:
    transcript_files = sorted(
        SORTIE_DIR.glob("*.txt")
    )

    if not transcript_files:
        print(
            "Aucune transcription trouvée."
        )
        return

    transcript_file = transcript_files[0]

    print(
        f"Lecture de : {transcript_file.name}"
    )

    print("Analyse de la transcription...")
    segments = parse_transcript_file(
        transcript_file
    )

    print("Fusion des segments...")
    segments = merge_segments(
        segments
    )

    print("Construction des paragraphes...")
    paragraphs = build_paragraphs(
        segments
    )

    print(
        f"Paragraphes détectés : {len(paragraphs)}"
    )

    print(
        "Correction sémantique IA..."
    )

    paragraphs = clean_paragraphs(
        paragraphs
    )

    print(
        "Construction du plan..."
    )

    outline = build_outline(
        paragraphs
    )

    output_md = transcript_file.with_suffix(
        ".md"
    )

    print(
        "Génération du markdown..."
    )

    build_markdown(
        outline,
        output_md
    )

    print()
    print("=" * 70)
    print("LIVRET GÉNÉRÉ")
    print("=" * 70)
    print(
        f"Titre : {outline['title']}"
    )
    print(
        f"Nombre de paragraphes : {len(paragraphs)}"
    )
    print(
        f"Nombre de sections : {len(outline['sections'])}"
    )
    print(
        f"Markdown généré : {output_md}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()