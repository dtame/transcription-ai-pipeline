from book.text_cleaner import clean_text


SHORT_SEGMENT_WORD_LIMIT = 6


def count_words(text: str) -> int:
    return len(text.split())

def should_merge_with_previous(previous_text: str, current_text: str) -> bool:
    if not previous_text or not current_text:
        return False

    current_word_count = count_words(current_text)

    # Fusionner seulement les fragments très courts
    if current_word_count <= SHORT_SEGMENT_WORD_LIMIT:
        return True

    return False

def merge_segments(segments: list[dict]) -> list[dict]:
    merged_segments = []

    for segment in segments:
        if not segment.get("valid"):
            continue

        text = clean_text(segment["text"])
        from book.semantic_cleaner import clean_semantically
        text = clean_semantically(text)
        
        if not text:
            continue

        current = {
            **segment,
            "text": text
        }

        if (
            merged_segments
            and should_merge_with_previous(
                merged_segments[-1]["text"],
                current["text"]
            )
        ):
            previous = merged_segments[-1]

            previous["text"] = previous["text"].rstrip(".") + " " + current["text"][0].lower() + current["text"][1:]
            previous["end"] = current["end"]
            previous["end_seconds"] = current["end_seconds"]

        else:
            merged_segments.append(current)

    return merged_segments