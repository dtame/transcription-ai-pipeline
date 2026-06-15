from book.title_builder import build_title
from book.topic_group_builder import build_topic_groups
from book.section_builder import build_sections_from_groups


def build_outline(paragraphs: list[str]) -> dict:
    groups = build_topic_groups(paragraphs)

    return {
        "title": build_title(paragraphs),
        "subtitle": "Livret généré automatiquement",
        "sections": build_sections_from_groups(groups)
    }