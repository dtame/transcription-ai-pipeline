from book.local_ai_service import ask_local_ai


def clean_semantically(text: str) -> str:
    
    prompt = f"""
You are an expert editor.

You are correcting a speech-to-text transcription.

Rules:

- Correct obvious transcription errors.
- Preserve the original wording whenever possible.
- Do not paraphrase.
- Do not rewrite sentences.
- Do not add information.
- Do not infer missing ideas.
- Only correct words that are clearly wrong.
- Return only the corrected text.
- Never answer as an assistant.
- Never ask for more text.
- Only return the corrected version of the provided text.
- If the text is unclear, keep it unchanged.

Text:

{text}
"""

    try:
        result = ask_local_ai(
            prompt,
            temperature=0.1
        )

        if result:
            return result.strip()

    except Exception as ex:
        print(
            f"Erreur semantic cleaner : {ex}"
        )

    return text