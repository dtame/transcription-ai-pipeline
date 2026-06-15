def keyword_similarity(
    keywords_a: list[str],
    keywords_b: list[str]
) -> float:

    set_a = set(keywords_a)
    set_b = set(keywords_b)

    if not set_a or not set_b:
        return 0.0

    intersection = len(
        set_a.intersection(set_b)
    )

    union = len(
        set_a.union(set_b)
    )

    return intersection / union