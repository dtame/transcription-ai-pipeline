from book.keyword_extractor import extract_keywords
from book.topic_similarity import keyword_similarity


SIMILARITY_THRESHOLD = 0.20
MAX_PARAGRAPHS_PER_GROUP = 4

def build_topic_groups(
    paragraphs: list[str]
) -> list[list[str]]:

    if not paragraphs:
        return []

    groups = []

    current_group = [
        paragraphs[0]
    ]

    current_keywords = extract_keywords(
        paragraphs[0],
        ignore_religious_words=True
    )

    for paragraph in paragraphs[1:]:

        paragraph_keywords = extract_keywords(
            paragraph,
            ignore_religious_words=True
        )

        score = keyword_similarity(
            current_keywords,
            paragraph_keywords
        )

        if (
            score >= SIMILARITY_THRESHOLD
            and len(current_group) < MAX_PARAGRAPHS_PER_GROUP
        ):

            current_group.append(paragraph)

            current_keywords = list(
                set(current_keywords)
                .union(paragraph_keywords)
            )

        else:

            groups.append(current_group)

            current_group = [paragraph]

            current_keywords = paragraph_keywords

    groups.append(current_group)

    return groups