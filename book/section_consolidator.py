from book.keyword_extractor import extract_keywords
from book.topic_similarity import keyword_similarity


SECTION_SIMILARITY_THRESHOLD = 0.15
MAX_GROUPS_PER_SECTION = 4


def group_keywords(group: list[str]) -> list[str]:
    text = " ".join(group)

    return extract_keywords(
        text,
        max_keywords=20,
        ignore_religious_words=True
    )


def consolidate_groups(
    groups: list[list[str]]
) -> list[list[str]]:

    if not groups:
        return []

    sections = []

    current_section = groups[0]

    current_keywords = group_keywords(
        current_section
    )

    current_group_count = 1

    for group in groups[1:]:

        group_kw = group_keywords(group)

        similarity = keyword_similarity(
            current_keywords,
            group_kw
        )

        if (
            similarity >= SECTION_SIMILARITY_THRESHOLD
            and current_group_count < MAX_GROUPS_PER_SECTION
        ):

            current_section.extend(group)

            current_keywords = list(
                set(current_keywords)
                .union(group_kw)
            )

            current_group_count += 1

        else:

            sections.append(current_section)

            current_section = group

            current_keywords = group_kw

            current_group_count = 1

    sections.append(current_section)

    return sections