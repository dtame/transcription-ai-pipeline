from pathlib import Path


def build_markdown(outline: dict, output_file: Path) -> None:

    lines = []

    lines.append(f"# {outline['title']}")
    lines.append("")

    if outline.get("subtitle"):
        lines.append(f"*{outline['subtitle']}*")
        lines.append("")

    for section in outline["sections"]:

        lines.append(f"## {section['title']}")
        lines.append("")

        for paragraph in section["paragraphs"]:
            lines.append(paragraph)
            lines.append("")

    output_file.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )