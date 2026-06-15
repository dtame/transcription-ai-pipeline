from book.local_ai_service import ask_local_ai


def build_section_title(paragraphs: list[str], index: int) -> str:
    content = "\n\n".join(paragraphs)

    prompt = f"""
You are a professional book editor.

Create a short section title for the following content.

Rules:
- Use the same language as the content.
- Maximum 7 words.
- No quotation marks.
- No subtitle.
- Return only the title.

Content:

{content}
"""

    try:
        title = ask_local_ai(prompt, temperature=0.2).strip()

        if title:
            return title

    except Exception as ex:
        print(f"Erreur IA section {index} : {ex}")

    return f"Section {index}"


def build_sections_from_groups(groups: list[list[str]]) -> list[dict]:
    sections = []

    for index, group in enumerate(groups, start=1):
        section_title = build_section_title(group, index)

        sections.append(
            {
                "title": section_title,
                "paragraphs": group
            }
        )

    return sections