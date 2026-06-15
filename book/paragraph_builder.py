from book.text_cleaner import clean_text


MIN_WORDS_PER_PARAGRAPH = 25
MAX_WORDS_PER_PARAGRAPH = 80


def count_words(text: str) -> int:
    return len(text.split())


def build_paragraphs(
    segments: list[dict]
) -> list[str]:

    paragraphs = []

    current_sentences = []
    current_word_count = 0

    for segment in segments:

        if not segment.get("valid"):
            continue

        text = clean_text(segment["text"])

        if not text:
            continue

        sentence_words = count_words(text)

        current_sentences.append(text)
        current_word_count += sentence_words

        # Paragraphe suffisamment grand
        if current_word_count >= MIN_WORDS_PER_PARAGRAPH:

            # On clôture s'il devient très long
            if current_word_count >= MAX_WORDS_PER_PARAGRAPH:

                paragraphs.append(
                    " ".join(current_sentences)
                )

                current_sentences = []
                current_word_count = 0

    # Reste du contenu
    if current_sentences:

        paragraph = " ".join(current_sentences)

        # Si très petit, on fusionne avec le précédent
        if (
            paragraphs
            and count_words(paragraph) < MIN_WORDS_PER_PARAGRAPH
        ):
            paragraphs[-1] += " " + paragraph

        else:
            paragraphs.append(paragraph)

    return paragraphs