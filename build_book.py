from book.transcript_parser import parse_transcript_file
from book.sentence_merger import merge_segments
from book.paragraph_builder import build_paragraphs
from book.outline_builder import build_outline
from book.markdown_builder import build_markdown
from app.paths import SORTIE_DIR


def main() -> None:
    transcript_files = sorted(SORTIE_DIR.glob("*.txt"))

    if not transcript_files:
        print("Aucune transcription trouvée.")
        return

    transcript_file = transcript_files[0]

    print(f"Lecture de : {transcript_file.name}")

    segments = parse_transcript_file(transcript_file)
    segments = merge_segments(segments)
    paragraphs = build_paragraphs(segments)
    outline = build_outline(paragraphs)

    output_md = transcript_file.with_suffix(".md")
    build_markdown(outline, output_md)

    print(f"Titre : {outline['title']}")
    print(f"Nombre de paragraphes : {len(paragraphs)}")
    print(f"Nombre de sections : {len(outline['sections'])}")
    print(f"Markdown généré : {output_md}")


if __name__ == "__main__":
    main()