"""Contrats SRC V3 négatifs. Aucune normalisation. 0 réseau."""

from __future__ import annotations

import pytest

from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis_local_v3.decoder import decode_v3_transport
from app.source_analysis_local_v3.fixtures import v3_success_transport
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v13,
    build_window_system_prompt_v131,
)
from app.source_analysis_local_v3.resolver import resolve_v3_handles
from app.source_analysis_local_v3.source_refs import (
    SRC_CANONICAL_PATTERN,
    classify_src_token,
    collect_v3_source_refs,
    is_canonical_src,
)
from app.source_analysis_local_v3.validator import validate_v3_transport


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _allowed():
    return {"SRC000609", "SRC000001"}


class TestLexicalGrammar:
    def test_canonical_pattern(self):
        assert SRC_CANONICAL_PATTERN == r"^SRC[0-9]{6}$"
        assert is_canonical_src("SRC000609") is True
        assert is_canonical_src("SRc000609") is False
        assert is_canonical_src("src000609") is False
        assert is_canonical_src("SRC609") is False

    def test_no_case_normalization(self):
        errors: list[str] = []
        refs = collect_v3_source_refs(
            ["SRc000609"], "records[50]", errors, {"SRC000609"}
        )
        assert refs == []
        assert any("SRc000609" in err for err in errors)
        assert not any("SRC000609" in err and "mal formé" not in err for err in errors)
        assert classify_src_token("SRc000609") == "wrong_case"
        assert classify_src_token("src000609") == "wrong_case"


class TestDecoderNegatives:
    def _payload(self, token):
        payload = v3_success_transport()
        payload["records"][0]["s"] = [token]
        return payload

    def test_wrong_case_src_fails(self):
        with pytest.raises(WindowTransportValidationError, match="SRc000609"):
            decode_v3_transport(self._payload("SRc000609"), allowed_source_refs=_allowed())
        with pytest.raises(WindowTransportValidationError, match="src000609"):
            decode_v3_transport(self._payload("src000609"), allowed_source_refs=_allowed())

    def test_missing_zeros_fails(self):
        with pytest.raises(WindowTransportValidationError, match="SRC609"):
            decode_v3_transport(self._payload("SRC609"), allowed_source_refs=_allowed())

    def test_canonical_present_passes(self):
        payload = self._payload("SRC000609")
        decoded = decode_v3_transport(payload, allowed_source_refs=_allowed())
        assert decoded["records"][0]["s"] == ["SRC000609"]

    def test_absent_well_formed_fails(self):
        with pytest.raises(WindowTransportValidationError, match="inconnu"):
            decode_v3_transport(
                self._payload("SRC999999"), allowed_source_refs=_allowed()
            )

    def test_duplicate_src_fails(self):
        payload = v3_success_transport()
        payload["records"][0]["s"] = ["SRC000001", "SRC000001"]
        with pytest.raises(WindowTransportValidationError, match="dupliqué"):
            decode_v3_transport(payload, allowed_source_refs={"SRC000001"})

    def test_out_of_window_fails(self):
        payload = self._payload("SRC000002")
        with pytest.raises(WindowTransportValidationError, match="inconnu"):
            decode_v3_transport(payload, allowed_source_refs={"SRC000001"})

    def test_whitespace_mutated_fails(self):
        with pytest.raises(WindowTransportValidationError, match="SRC000609"):
            decode_v3_transport(
                self._payload(" SRC000609"), allowed_source_refs=_allowed()
            )
        with pytest.raises(WindowTransportValidationError):
            decode_v3_transport(
                self._payload("SRC000609 "), allowed_source_refs=_allowed()
            )


class TestPromptHardening:
    def test_v13_untouched(self):
        prompt = build_window_system_prompt_v13("en")
        assert "empty only if no local IDEA exists" in prompt
        assert "case-sensitive" not in prompt.lower()
        assert "zero padding" not in prompt.lower()

    def test_v131_contains_src_rules(self):
        prompt = build_window_system_prompt_v131("en")
        low = prompt.lower()
        assert "case-sensitive" in low
        assert "exactly" in low
        assert "from its number" in low
        assert "zero padding" in low
        assert "empty only if no local IDEA exists" not in prompt


class TestExamplePolicy:
    def test_empty_example_links_allowed_when_ideas_exist(self):
        transcript = make_transcript(
            ["Faith window teaches how a trial is crossed."],
            src_ids=("SRC000001",),
            transcript_id="TR-EX",
            content_sha256="e" * 64,
        )
        window = window_for(transcript, owned=("SRC000001",), window_id="WIN001")
        payload = v3_success_transport()
        example = next(item for item in payload["records"] if item["k"] == "EXAMPLE")
        example["l"] = []
        decoded = decode_v3_transport(payload, allowed_source_refs={"SRC000001"})
        resolved = resolve_v3_handles(decoded)
        validate_v3_transport(decoded, window)
        empty = next(item for item in resolved["records"] if item["k"] == "EXAMPLE")
        assert empty["l"] == []
