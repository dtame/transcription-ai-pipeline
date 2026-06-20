"""
Moteurs IA pour le traitement des chunks de transcription.

Architecturés autour d'une interface commune BaseAIEngine,
les moteurs sont découplés de l'orchestration (ai_processor.py).

Moteurs disponibles :
- FakeAIEngine  : simulation locale pour les tests
- OllamaEngine  : moteur principal (Ollama local, ex. qwen3:8b)
- LMStudioEngine: moteur alternatif (LM Studio, API compatible OpenAI)
- OpenAIEngine  : moteur cloud (OpenAI, optionnel)

Commandes utiles :
    ollama pull qwen3:8b       # modèle principal recommandé
    ollama pull llama3.1:8b    # modèle alternatif stable
    ollama pull mistral:7b     # modèle léger de secours
"""

from abc import ABC, abstractmethod

import requests

from app.config import (
    AI_PROVIDER,
    AI_TASK,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_OPTIONS,
    LMSTUDIO_BASE_URL,
    LMSTUDIO_MODEL,
)
from app.prompt_manager import build_prompt as _build_prompt


class BaseAIEngine(ABC):
    """Interface commune pour tous les moteurs IA."""

    @abstractmethod
    def process(self, text: str, project_name: str | None = None) -> str:
        """Traite un texte brut et retourne un contenu Markdown structuré."""
        ...

    def build_prompt(self, text: str, project_name: str | None = None) -> str:
        """
        Construit le prompt final.

        Priorité :
            1. depot/<project_name>/prompt.md si project_name fourni
            2. template AI_TASK défini dans config.py
        """
        return _build_prompt(AI_TASK, text, project_name=project_name)


class FakeAIEngine(BaseAIEngine):
    """
    Moteur simulé pour les tests et le développement.
    Ne nécessite aucune API ni modèle local.
    Activer avec : AI_PROVIDER = "fake"
    """

    def process(self, text: str, project_name: str | None = None) -> str:
        return f"""# Traitement IA simulé

> Ce chunk a été traité par le moteur IA simulé (FakeAIEngine).
> Aucune transformation réelle n'a été appliquée.

## Contenu original

{text}
"""


class OllamaEngine(BaseAIEngine):
    """
    Moteur IA principal basé sur Ollama (local).
    Activer avec : AI_PROVIDER = "ollama"

    Modèle par défaut : qwen3:8b
    URL par défaut    : http://localhost:11434

    Prérequis :
        - Ollama installé et lancé
        - Modèle téléchargé : ollama pull qwen3:8b
    """

    def process(self, text: str, project_name: str | None = None) -> str:
        prompt = self.build_prompt(text, project_name=project_name)

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": OLLAMA_OPTIONS,
        }

        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
            return data["response"].strip()

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Impossible de joindre Ollama sur {OLLAMA_BASE_URL}. "
                "Vérifiez qu'Ollama est bien lancé (`ollama serve`)."
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"Ollama n'a pas répondu dans les délais (modèle : {OLLAMA_MODEL}). "
                "Augmentez le timeout ou essayez un modèle plus léger."
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Erreur HTTP Ollama : {e}")
        except KeyError:
            raise RuntimeError(
                "Réponse Ollama inattendue : champ 'response' absent. "
                f"Réponse reçue : {response.text[:200]}"
            )


class LMStudioEngine(BaseAIEngine):
    """
    Moteur IA basé sur LM Studio (API compatible OpenAI).
    Activer avec : AI_PROVIDER = "lmstudio"

    URL par défaut    : http://localhost:1234/v1
    Modèle par défaut : local-model

    Prérequis :
        - LM Studio installé et serveur local démarré
        - Un modèle chargé dans LM Studio
    """

    def process(self, text: str, project_name: str | None = None) -> str:
        prompt = self.build_prompt(text, project_name=project_name)

        payload = {
            "model": LMSTUDIO_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
        }

        try:
            response = requests.post(
                f"{LMSTUDIO_BASE_URL}/chat/completions",
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Impossible de joindre LM Studio sur {LMSTUDIO_BASE_URL}. "
                "Vérifiez que le serveur local LM Studio est démarré."
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                "LM Studio n'a pas répondu dans les délais. "
                "Augmentez le timeout ou essayez un modèle plus léger."
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Erreur HTTP LM Studio : {e}")
        except (KeyError, IndexError):
            raise RuntimeError(
                "Réponse LM Studio inattendue : structure de réponse invalide. "
                f"Réponse reçue : {response.text[:200]}"
            )


class OpenAIEngine(BaseAIEngine):
    """
    Moteur IA basé sur l'API OpenAI (cloud).
    Activer avec : AI_PROVIDER = "openai"

    Nécessite : OPENAI_API_KEY configurée dans config.py
    Modèle par défaut : gpt-4o-mini

    Note : le package `openai` est importé uniquement à l'appel de process()
    pour ne pas rendre la dépendance obligatoire.
    """

    def process(self, text: str, project_name: str | None = None) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "Le package 'openai' n'est pas installé. "
                "Installez-le avec : pip install openai"
            )

        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY n'est pas configurée dans app/config.py."
            )

        prompt = self.build_prompt(text, project_name=project_name)
        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )

        return response.choices[0].message.content.strip()


def get_ai_engine() -> BaseAIEngine:
    """
    Fabrique le moteur IA selon AI_PROVIDER défini dans config.py.

    Valeurs supportées :
        "ollama"    -> OllamaEngine   (défaut recommandé, modèle qwen3:8b)
        "lmstudio"  -> LMStudioEngine
        "openai"    -> OpenAIEngine
        "fake"      -> FakeAIEngine   (tests uniquement)

    Raises:
        ValueError: si AI_PROVIDER est inconnu.
    """
    provider = AI_PROVIDER.strip().lower()

    engines = {
        "ollama": OllamaEngine,
        "lmstudio": LMStudioEngine,
        "openai": OpenAIEngine,
        "fake": FakeAIEngine,
    }

    if provider not in engines:
        raise ValueError(
            f"AI_PROVIDER inconnu : '{AI_PROVIDER}'. "
            f"Valeurs acceptées : {list(engines.keys())}"
        )

    return engines[provider]()
