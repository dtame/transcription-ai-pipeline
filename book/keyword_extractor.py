import re
from collections import Counter

from book.title_builder import (
    STOP_WORDS,
    RELIGIOUS_STOP_WORDS
)


def extract_keywords(
    text: str,
    max_keywords: int = 10,
    ignore_religious_words: bool = False
) -> list[str]:

    words = re.findall(
        r"[a-zA-ZÀ-ÿ']+",
        text.lower()
    )

    excluded = set(STOP_WORDS)

    if ignore_religious_words:
        excluded.update(RELIGIOUS_STOP_WORDS)

    words = [
        word
        for word in words
        if len(word) > 2 and word not in excluded
    ]

    counter = Counter(words)

    return [
        word
        for word, _ in counter.most_common(max_keywords)
    ]