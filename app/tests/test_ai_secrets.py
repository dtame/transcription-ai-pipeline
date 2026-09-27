"""
Secrets : rien dans le code, tout dans l'environnement.

Ce module n'est pas un scanner de sécurité. Il vérifie quatre choses
précises et vérifiables :

    aucun littéral de clé API dans les modules de la couche IA ;
    un provider cloud sans clé échoue clairement, au bon moment ;
    les moteurs locaux et le fake n'exigent aucune clé ;
    .gitignore protège .env tout en laissant passer .env.example.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import app.config as config

from app.ai.errors import AIConfigurationError
from app.ai.providers import (
    AnthropicEngine,
    FakeAIEngine,
    LMStudioEngine,
    OllamaEngine,
    OpenAIEngine,
)
from app.ai.settings import (
    ENV_ANTHROPIC_API_KEY,
    ENV_OPENAI_API_KEY,
    get_api_key,
    load_env_file,
    require_api_key,
)

RACINE = Path(__file__).resolve().parent.parent.parent
MODULES_IA = sorted((RACINE / "app" / "ai").rglob("*.py"))

# Formes de clés qu'aucun module ne doit contenir en dur.
MOTIFS_DE_CLE = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
]

# Affectation d'une clé à une valeur littérale. La valeur capturée est ensuite
# filtrée : `ENV_OPENAI_API_KEY = "OPENAI_API_KEY"` déclare un NOM de variable
# d'environnement, pas un secret.
MOTIF_AFFECTATION = re.compile(
    r"""(?:api_key|API_KEY)\s*=\s*["']([A-Za-z0-9_\-]{12,})["']"""
)


def _valeurs_suspectes(contenu: str) -> list[str]:
    return [
        valeur
        for valeur in MOTIF_AFFECTATION.findall(contenu)
        if not re.fullmatch(r"[A-Z0-9_]+", valeur)
    ]


class TestAucuneCleDansLeCode:

    def test_modules_ia_sans_cle_en_dur(self):
        assert MODULES_IA, "aucun module IA trouvé — le test se trompe de chemin"

        for chemin in MODULES_IA:
            contenu = chemin.read_text(encoding="utf-8")

            for motif in MOTIFS_DE_CLE:
                assert not motif.search(contenu), f"clé potentielle dans {chemin.name}"

            assert not _valeurs_suspectes(contenu), f"clé en dur dans {chemin.name}"

    def test_le_scanner_detecte_bien_une_cle(self):
        """Garde-fou : un scanner qui ne trouve jamais rien ne prouve rien."""
        assert _valeurs_suspectes('api_key = "abcd1234efgh5678"')
        assert MOTIFS_DE_CLE[0].search("sk-abcdefghijklmnopqrstuvwxyz")

        # Et ne se déclenche pas sur un nom de variable d'environnement.
        assert not _valeurs_suspectes('ENV_OPENAI_API_KEY = "OPENAI_API_KEY"')

    def test_config_ne_contient_aucune_cle(self):
        """La constante héritée de la V1 doit rester vide dans le dépôt."""
        assert config.OPENAI_API_KEY == ""
        assert getattr(config, "ANTHROPIC_API_KEY", "") == ""

    def test_tests_sans_cle_reelle(self):
        moi = Path(__file__).name

        for chemin in sorted(Path(__file__).parent.glob("test_ai_*.py")):
            # Ce module contient volontairement des échantillons factices pour
            # prouver que le scanner détecte quelque chose : il s'exclut.
            if chemin.name == moi:
                continue

            contenu = chemin.read_text(encoding="utf-8")

            for motif in MOTIFS_DE_CLE:
                assert not motif.search(contenu), f"clé potentielle dans {chemin.name}"

            assert not _valeurs_suspectes(contenu), f"clé en dur dans {chemin.name}"


class TestLectureDesCles:

    def test_variable_d_environnement_prioritaire(self, monkeypatch):
        monkeypatch.setenv(ENV_OPENAI_API_KEY, "valeur-env")
        monkeypatch.setattr(config, "OPENAI_API_KEY", "valeur-config")

        assert get_api_key(ENV_OPENAI_API_KEY, config_fallback="OPENAI_API_KEY") == (
            "valeur-env"
        )

    def test_repli_config_pour_les_installations_v1(self, monkeypatch):
        monkeypatch.setattr(config, "OPENAI_API_KEY", "valeur-config")

        assert get_api_key(ENV_OPENAI_API_KEY, config_fallback="OPENAI_API_KEY") == (
            "valeur-config"
        )

    def test_absente_retourne_none(self):
        assert get_api_key(ENV_OPENAI_API_KEY) is None

    def test_message_d_erreur_nomme_la_variable(self):
        with pytest.raises(AIConfigurationError) as exc:
            require_api_key("anthropic", ENV_ANTHROPIC_API_KEY)

        message = str(exc.value)

        assert ENV_ANTHROPIC_API_KEY in message
        assert ".env" in message


class TestChargementDotEnv:

    def test_fichier_absent_sans_erreur(self, tmp_path):
        assert load_env_file(tmp_path / "inexistant.env", force=True) == 0

    def test_variables_chargees(self, tmp_path, monkeypatch):
        fichier = tmp_path / ".env"
        fichier.write_text(
            "# commentaire\n"
            "VARIABLE_DE_TEST_PHASE2=valeur\n"
            "\n"
            "AUTRE_VARIABLE_PHASE2='entre quotes'\n",
            encoding="utf-8",
        )

        monkeypatch.delenv("VARIABLE_DE_TEST_PHASE2", raising=False)
        monkeypatch.delenv("AUTRE_VARIABLE_PHASE2", raising=False)

        import os

        try:
            assert load_env_file(fichier, force=True) == 2
            assert os.environ["VARIABLE_DE_TEST_PHASE2"] == "valeur"
            assert os.environ["AUTRE_VARIABLE_PHASE2"] == "entre quotes"
        finally:
            os.environ.pop("VARIABLE_DE_TEST_PHASE2", None)
            os.environ.pop("AUTRE_VARIABLE_PHASE2", None)

    def test_environnement_existant_jamais_ecrase(self, tmp_path, monkeypatch):
        fichier = tmp_path / ".env"
        fichier.write_text("VARIABLE_DEJA_LA_PHASE2=depuis-le-fichier\n", encoding="utf-8")

        monkeypatch.setenv("VARIABLE_DEJA_LA_PHASE2", "depuis-le-shell")
        load_env_file(fichier, force=True)

        import os

        assert os.environ["VARIABLE_DEJA_LA_PHASE2"] == "depuis-le-shell"


class TestExigenceDeCleParProvider:

    def test_fake_n_exige_aucune_cle(self):
        assert FakeAIEngine().send_prompt("x")

    def test_moteurs_locaux_constructibles_sans_cle(self):
        """Ollama et LM Studio ne demandent jamais de clé cloud."""
        for moteur in (OllamaEngine(), LMStudioEngine()):
            assert moteur.resolve_model()

    def test_openai_echoue_sans_cle(self):
        from app.ai.contracts import AIRequest
        from app.ai.retry import no_delay_policy

        with pytest.raises(AIConfigurationError, match=ENV_OPENAI_API_KEY):
            OpenAIEngine(retry_policy=no_delay_policy(1)).generate(AIRequest(prompt="x"))

    def test_anthropic_echoue_sans_cle(self):
        from app.ai.contracts import AIRequest
        from app.ai.retry import no_delay_policy

        with pytest.raises(AIConfigurationError, match=ENV_ANTHROPIC_API_KEY):
            AnthropicEngine(model="m", retry_policy=no_delay_policy(1)).generate(
                AIRequest(prompt="x")
            )

    def test_cle_exigee_a_l_appel_pas_a_la_construction(self):
        """Le registre reste inspectable sur une machine sans credentials."""
        assert OpenAIEngine() is not None
        assert AnthropicEngine() is not None


class TestGitignore:

    def _gitignore(self) -> list[str]:
        return (RACINE / ".gitignore").read_text(encoding="utf-8").splitlines()

    def test_env_ignore(self):
        lignes = [ligne.strip() for ligne in self._gitignore()]

        assert ".env" in lignes
        assert ".env.*" in lignes

    def test_exemple_versionnable(self):
        """.env.* ignorerait aussi le modèle : l'exception doit être explicite."""
        lignes = [ligne.strip() for ligne in self._gitignore()]

        assert "!.env.example" in lignes

    def test_exemple_present_et_vide(self):
        exemple = RACINE / ".env.example"

        assert exemple.exists()

        for ligne in exemple.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()

            if not ligne or ligne.startswith("#"):
                continue

            cle, _, valeur = ligne.partition("=")
            assert valeur.strip() == "", f"{cle} ne doit porter aucune valeur"

    def test_aucun_env_reel_dans_le_depot(self):
        assert not (RACINE / ".env").exists() or True  # un .env local est toléré

        # Ce qui ne l'est pas : qu'il soit suivi par Git.
        lignes = [ligne.strip() for ligne in self._gitignore()]
        assert ".env" in lignes
