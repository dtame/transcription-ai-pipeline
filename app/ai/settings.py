"""
Secrets et configuration par étape.

Secrets
-------
Aucune clé API ne vit dans le code. Elles sont lues depuis l'environnement :

    OPENAI_API_KEY
    ANTHROPIC_API_KEY

Un fichier `.env` local, déjà ignoré par Git, peut les fournir ; il est lu
une seule fois et n'écrase JAMAIS une variable déjà définie dans le shell.
Le parseur est volontairement minimal (une dizaine de lignes) pour ne pas
ajouter python-dotenv en dépendance pour si peu.

`app.config.OPENAI_API_KEY` reste lu en dernier recours, uniquement pour ne
pas casser une installation V1 où quelqu'un aurait renseigné la constante en
local. Dans le dépôt elle vaut "" et doit le rester.

Configuration par étape
-----------------------
Chaque étape éditoriale choisit son fournisseur et son modèle via
`app.config.AI_STAGE_SETTINGS`. Configuration de production actuelle :

    source_analysis               anthropic / claude-sonnet-5
    source_analysis_window        anthropic / claude-sonnet-5  (3B.7.2, isolée)
    source_analysis_consolidation anthropic / claude-sonnet-5  (3B.7.4, isolée)
    editorial_planning            anthropic / claude-opus-5
    book_generation               anthropic / claude-sonnet-5
    book_validation               openai    / gpt-5.6-terra

Seuls le provider et le modèle y sont verrouillés. Température, plafond de
sortie et schéma de réponse restent le choix de l'étape appelante, qui les
passe par AIRequest : ils dépendent de prompts qui n'existent pas encore.

Une étape absente du tableau (visual_design, image_generation,
document_rendering) hérite simplement du provider global AI_PROVIDER.

Il n'y a aucun routage « intelligent » : le choix est explicite ou hérité,
jamais deviné. Résoudre cette configuration ne demande aucune clé API et
n'ouvre aucune connexion — voir `require_api_key`, appelée au moment de
l'appel réel seulement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import app.config as config

from app.ai.capabilities import default_safety_ratio, validate_safety_ratio
from app.ai.errors import AIConfigurationError
from app.ai.timeouts import optional_parsed_timeout

ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"

# Racine du dépôt : app/ai/settings.py -> app/ai -> app -> racine
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_env_file_loaded = False


# ---------------------------------------------------------------------------
# Chargement optionnel de .env
# ---------------------------------------------------------------------------

def load_env_file(path: Path | None = None, *, force: bool = False) -> int:
    """
    Charge un `.env` local dans os.environ sans écraser l'existant.

    Retourne le nombre de variables effectivement ajoutées. Ne lève jamais :
    l'absence de `.env` est le cas normal.
    """
    global _env_file_loaded

    if _env_file_loaded and not force:
        return 0

    _env_file_loaded = True
    env_path = Path(path) if path else _PROJECT_ROOT / ".env"

    if not env_path.exists():
        return 0

    added = 0

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value
            added += 1

    return added


# ---------------------------------------------------------------------------
# Clés API
# ---------------------------------------------------------------------------

def get_api_key(env_var: str, *, config_fallback: str | None = None) -> str | None:
    """Clé lue dans l'environnement, puis dans un repli de configuration V1."""
    load_env_file()

    value = os.environ.get(env_var, "").strip()

    if value:
        return value

    if config_fallback:
        legacy = str(getattr(config, config_fallback, "") or "").strip()

        if legacy:
            return legacy

    return None


def require_api_key(
    provider: str,
    env_var: str,
    *,
    config_fallback: str | None = None,
) -> str:
    """
    Clé obligatoire, avec un message qui dit quoi faire.

    Levée au moment de l'appel, pas à l'import : instancier un provider cloud
    sans clé reste possible (et testable), seul l'appel réel échoue.
    """
    key = get_api_key(env_var, config_fallback=config_fallback)

    if not key:
        raise AIConfigurationError(
            f"Clé API absente pour le fournisseur « {provider} ». "
            f"Définissez la variable d'environnement {env_var} "
            f"(ou renseignez-la dans un fichier .env local, non versionné)."
        )

    return key


# ---------------------------------------------------------------------------
# Configuration par étape
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StageSettings:
    """
    Réglages IA d'une étape du pipeline.

    `model` à None signifie « modèle par défaut du provider » : c'est le cas
    des étapes qui n'ont pas encore de modèle attribué, pas un repli deviné.
    """

    stage: str
    provider: str
    model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    context_safety_ratio: float = 0.70
    connect_timeout_seconds: float | None = None
    read_timeout_seconds: float | None = None

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "context_safety_ratio": self.context_safety_ratio,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "read_timeout_seconds": self.read_timeout_seconds,
        }


def default_provider() -> str:
    """Provider global, lu à l'appel pour rester surchargeable par les tests."""
    return str(getattr(config, "AI_PROVIDER", "ollama")).strip().lower()


def resolve_stage_settings(stage: str) -> StageSettings:
    """
    Réglages d'une étape : entrée dédiée si elle existe, défauts globaux sinon.

    Le ratio de sécurité du contexte suit la même règle : global par défaut,
    surchargeable par étape. Aucune valeur n'est universellement correcte —
    une analyse de source et une génération de livre n'ont pas le même profil.
    """
    stage = str(stage).strip()
    raw = dict((getattr(config, "AI_STAGE_SETTINGS", {}) or {}).get(stage, {}))

    ratio = raw.get("context_safety_ratio")
    ratio = default_safety_ratio() if ratio is None else validate_safety_ratio(ratio)

    return StageSettings(
        stage=stage,
        provider=str(raw.get("provider") or default_provider()).strip().lower(),
        model=raw.get("model") or None,
        temperature=raw.get("temperature"),
        max_output_tokens=raw.get("max_output_tokens"),
        context_safety_ratio=ratio,
        connect_timeout_seconds=optional_parsed_timeout(
            raw.get("connect_timeout_seconds"),
            name=f"AI_STAGE_SETTINGS[{stage}].connect_timeout_seconds",
        ),
        read_timeout_seconds=optional_parsed_timeout(
            raw.get("read_timeout_seconds"),
            name=f"AI_STAGE_SETTINGS[{stage}].read_timeout_seconds",
        ),
    )


def default_timeout_seconds() -> float:
    """
    Read timeout par défaut de la couche IA, en secondes.

    Repli legacy : AI_DEFAULT_TIMEOUT_SECONDS (300). Le connect timeout
    vit dans app.ai.timeouts.default_connect_timeout_seconds.
    """
    return float(getattr(config, "AI_DEFAULT_TIMEOUT_SECONDS", 300))
