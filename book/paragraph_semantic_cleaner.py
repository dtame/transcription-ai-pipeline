import hashlib
import json
from pathlib import Path

from book.semantic_cleaner import clean_semantically
from book.hallucination_filter import filter_hallucinations


CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "semantic_cleaner_cache.json"


def load_cache() -> dict:
    CACHE_DIR.mkdir(exist_ok=True)

    if not CACHE_FILE.exists():
        return {}

    with open(CACHE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)

    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)


def get_cache_key(text: str) -> str:
    normalized = " ".join(text.split())

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def clean_paragraphs(
    paragraphs: list[str]
) -> list[str]:

    cache = load_cache()
    cleaned_paragraphs = []

    total = len(paragraphs)

    for index, paragraph in enumerate(paragraphs, start=1):
        cache_key = get_cache_key(paragraph)

        if cache_key in cache:
            print(f"Cache IA {index}/{total}")
            cleaned_paragraphs.append(cache[cache_key])
            continue

        print(f"Nettoyage IA {index}/{total}")

        cleaned = clean_semantically(paragraph)

        cleaned = filter_hallucinations(
            paragraph,
            cleaned
        )

        cache[cache_key] = cleaned

        cleaned_paragraphs.append(cleaned)

        save_cache(cache)

    return cleaned_paragraphs