"""
Sortie structurée : décodage, validation, échec explicite.

Règle testée de bout en bout : un JSON invalide ne se répare pas en silence
et ne retourne pas un objet vide. Il lève, avec un extrait de ce qui a été
reçu, pour que la Phase 3 sache immédiatement que le modèle a dérivé.
"""

from __future__ import annotations

import pytest

from app.ai.errors import AIStructuredOutputError
from app.ai.structured import (
    _minimal_validate,
    build_json_instruction,
    parse_json_payload,
    parse_structured_output,
    strip_code_fences,
    validate_payload,
)


class TestExtraction:

    def test_json_nu(self):
        assert parse_json_payload('{"a": 1}') == {"a": 1}

    def test_bloc_markdown_json(self):
        texte = '```json\n{"a": 1}\n```'

        assert strip_code_fences(texte) == '{"a": 1}'
        assert parse_json_payload(texte) == {"a": 1}

    def test_bloc_markdown_sans_langage(self):
        assert parse_json_payload('```\n{"a": 1}\n```') == {"a": 1}

    def test_espaces_autour(self):
        assert parse_json_payload('\n\n  {"a": 1}  \n') == {"a": 1}

    def test_tableau_accepte(self):
        assert parse_json_payload("[1, 2, 3]") == [1, 2, 3]


class TestEchecExplicite:

    def test_json_invalide_leve(self):
        with pytest.raises(AIStructuredOutputError, match="JSON invalide"):
            parse_json_payload("{ceci n'est pas du json}")

    def test_texte_libre_leve(self):
        with pytest.raises(AIStructuredOutputError):
            parse_json_payload("Bien sûr ! Voici votre analyse :")

    def test_reponse_vide_leve(self):
        with pytest.raises(AIStructuredOutputError, match="vide"):
            parse_json_payload("   ")

    def test_message_contient_un_extrait_tronque(self):
        """Assez pour diagnostiquer, pas assez pour déverser le projet."""
        bruit = "x" * 5000

        with pytest.raises(AIStructuredOutputError) as exc:
            parse_json_payload(bruit)

        assert len(str(exc.value)) < 400
        assert "…" in str(exc.value)

    def test_aucune_reparation_tentee(self):
        """Un JSON tronqué échoue : la Phase 2 ne rappelle pas un LLM pour le réparer."""
        with pytest.raises(AIStructuredOutputError):
            parse_json_payload('{"sections": [{"titre": "a"')


class TestValidationDeSchema:

    SCHEMA = {
        "type": "object",
        "required": ["titre", "sections"],
        "properties": {
            "titre": {"type": "string"},
            "sections": {"type": "array", "items": {"type": "object"}},
        },
    }

    def test_payload_conforme(self):
        payload = {"titre": "Un titre", "sections": [{"a": 1}]}

        validate_payload(payload, self.SCHEMA)
        assert parse_structured_output('{"titre": "t", "sections": []}', self.SCHEMA)

    def test_champ_obligatoire_absent(self):
        with pytest.raises(AIStructuredOutputError):
            validate_payload({"titre": "t"}, self.SCHEMA)

    def test_mauvais_type(self):
        with pytest.raises(AIStructuredOutputError):
            validate_payload({"titre": 42, "sections": []}, self.SCHEMA)

    def test_schema_absent_ne_valide_rien(self):
        validate_payload({"n'importe": "quoi"}, None)

    def test_validateur_minimal_type_racine(self):
        with pytest.raises(AIStructuredOutputError, match="type"):
            _minimal_validate([1, 2], {"type": "object"})

    def test_validateur_minimal_champ_requis(self):
        with pytest.raises(AIStructuredOutputError, match="obligatoire"):
            _minimal_validate({}, {"type": "object", "required": ["a"]})

    def test_validateur_minimal_propriete_imbriquee(self):
        schema = {
            "type": "object",
            "properties": {"bloc": {"type": "object", "required": ["x"]}},
        }

        with pytest.raises(AIStructuredOutputError, match=r"\$\.bloc\.x"):
            _minimal_validate({"bloc": {}}, schema)

    def test_validateur_minimal_items_de_tableau(self):
        schema = {"type": "array", "items": {"type": "string"}}

        with pytest.raises(AIStructuredOutputError, match=r"\[1\]"):
            _minimal_validate(["a", 2], schema)

    def test_validateur_minimal_refuse_bool_comme_nombre(self):
        with pytest.raises(AIStructuredOutputError, match="booléen"):
            _minimal_validate(True, {"type": "number"})

    def test_repli_minimal_si_jsonschema_absent(self, monkeypatch):
        """Sans jsonschema, la validation structurelle reste assurée."""
        import builtins

        vrai_import = builtins.__import__

        def _sans_jsonschema(name, *args, **kwargs):
            if name == "jsonschema":
                raise ImportError("simulé")
            return vrai_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _sans_jsonschema)

        with pytest.raises(AIStructuredOutputError, match="obligatoire"):
            validate_payload({}, {"type": "object", "required": ["a"]})


class TestConsigneJson:

    def test_consigne_sans_schema(self):
        instruction = build_json_instruction(None)

        assert "JSON" in instruction

    def test_consigne_avec_schema(self):
        instruction = build_json_instruction({"type": "object"})

        assert "JSON" in instruction
        assert '"type"' in instruction
