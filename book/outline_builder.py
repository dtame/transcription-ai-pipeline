from book.title_builder import build_title
from book.topic_group_builder import build_topic_groups
from book.section_consolidator import consolidate_groups
from book.section_builder import build_sections_from_groups


def build_outline(paragraphs: list[str]) -> dict:
    groups = build_topic_groups(paragraphs)

    consolidated_groups = consolidate_groups(groups)

    sections = build_sections_from_groups(consolidated_groups)

    return {
        "title": build_title(paragraphs),
        "subtitle": "Livret généré automatiquement",
        "sections": sections
    }