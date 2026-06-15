from urllib import response

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:7b"


def ask_local_ai(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    response = data.get("response", "").strip()

    response = response.replace('"', "")
    response = response.replace("'", "")

    return response