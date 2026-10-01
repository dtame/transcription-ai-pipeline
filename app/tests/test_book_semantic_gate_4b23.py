"""Phase 4B.2.3 — semantic gate contracts, FakeAI, benchmark. 0 réseau."""

from __future__ import annotations

import pytest

from app.book_generation.constants import (
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_VALIDATOR_VERSION,
)
from app.book_semantic_gate_4b23.accept import apply_acceptance
from app.book_semantic_gate_4b23.architecture import architecture_payload
from app.book_semantic_gate_4b23.cache_contract import (
    cache_contract_payload,
    semantic_pass_valid,
)
from app.book_semantic_gate_4b23.claims import (
    claim_contract_payload,
    uncovered_spans,
)
from app.book_semantic_gate_4b23.constants import (
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    GRANULARITY,
    HISTORICAL_4B21_STATUS,
    HISTORICAL_4B22_STATUS,
    HISTORICAL_4B2_STATUS,
    REAL_PROVIDER_CALLS,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
    SEMANTIC_VALIDATION_TRANSPORT_VERSION,
    SEMANTIC_VALIDATOR_PROMPT_VERSION,
    THINKING_MODE,
)
from app.book_semantic_gate_4b23.fakeai import (
    all_fixtures,
    fixture_invented_example,
    fixture_missing_paragraph,
    fixture_new_causal_link,
    fixture_pure_connective,
    fixture_reference_completion,
    fixture_supported,
    fixture_uncertainty_strengthened,
    fixture_unknown_handle,
    interpret_fixture,
    run_fakeai_catalog,
)
from app.book_semantic_gate_4b23.guard import assert_offline_package
from app.book_semantic_gate_4b23.prompt import prompt_bundle
from app.book_semantic_gate_4b23.reasons import REASON_CODES, reason_codes_payload
from app.book_semantic_gate_4b23.schema import schema_identity
from app.book_semantic_gate_4b23.sufficiency import sufficiency_assessment
from app.book_semantic_gate_4b23.transport import decode_transport


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineAndIdentities:
    def test_package_offline_and_frozen_history(self):
        assert_offline_package()
        assert REAL_PROVIDER_CALLS == 0
        assert HISTORICAL_4B2_STATUS == "FAIL"
        assert HISTORICAL_4B21_STATUS == "PASS"
        assert HISTORICAL_4B22_STATUS == "PARTIAL"
        assert EXPECTED_SOURCE_MAP == (
            "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
        )
        assert EXPECTED_EDITORIAL_PLAN == (
            "01cfb86aed8d32a7228b7c10a8351e2ebc0832fbfe6051e35686b0fd84836440"
        )
        assert EXPECTED_CLEAN_TRANSCRIPT.startswith("1f33ac73")
        assert EXPECTED_CLEAN_TRANSCRIPT.endswith("739958")
        assert len(EXPECTED_CLEAN_TRANSCRIPT) == 64
        assert BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
        assert BOOK_GENERATOR_VALIDATOR_VERSION == "book-generation-validator-1.0.1"

    def test_versions_and_terra_identity(self):
        assert SEMANTIC_VALIDATOR_PROMPT_VERSION == "book-semantic-validator-1.0"
        assert SEMANTIC_VALIDATION_TRANSPORT_VERSION == (
            "book-semantic-validation-transport-1.0"
        )
        assert SEMANTIC_GATE_PROVIDER == "openai"
        assert SEMANTIC_GATE_MODEL == "gpt-5.6-terra"
        assert THINKING_MODE == "provider_default"


class TestArchitecture:
    def test_three_findings_and_gate_order(self):
        payload = architecture_payload()
        assert payload["central_finding"] == (
            "STRUCTURAL_TRACEABILITY_IS_NOT_SEMANTIC_SUPPORT"
        )
        assert payload["second_finding"] == (
            "REFERENCE_PRESENCE_IS_NOT_LICENSE_TO_COMPLETE_REFERENCE_CONTENT"
        )
        assert payload["third_finding"] == "PLAUSIBILITY_IS_NOT_SUPPORT"
        assert payload["granularity"] == GRANULARITY
        assert payload["evidence_scope"] == (
            "DECLARED_FIRST_PLUS_BOUNDED_SECTION_EVIDENCE"
        )
        assert payload["cache_requires_both_gates"] is True
        assert payload["phase_5_relationship"]["chapter_gate_replaces_phase_5"] is False
        assert payload["no_whole_book"] is True
        assert payload["no_whole_transcript"] is True
        assert payload["not_bible_specific"] is True
        assert payload["no_automatic_repair"] is True
        assert payload["thinking"]["proposed_mode"] == "provider_default"
        assert payload["thinking"]["terra_capabilities_known"] is False
        assert payload["temperature"]["policy"] == "omit"
        assert "deterministic BookGenerationValidator" in " ".join(
            payload["gate_placement"]
        )

    def test_claim_coverage_contract(self):
        payload = claim_contract_payload()
        assert payload["granularity"] == GRANULARITY
        assert payload["claim_ids_are_canonical_manuscript_ids"] is False
        assert payload["text_spans_required"] is True
        text = "Alpha because beta."
        assert uncovered_spans(
            text,
            [
                {"start_offset": 0, "end_offset": 5},
                {"start_offset": 6, "end_offset": len(text)},
            ],
        ) == []
        assert uncovered_spans(text, [{"start_offset": 0, "end_offset": 5}])

    def test_reason_codes_include_historical_expectations(self):
        payload = reason_codes_payload()
        for code in (
            "NEW_CAUSAL_LINK",
            "NEW_IMPLICATION",
            "REFERENCE_COMPLETION",
            "INVENTED_EXAMPLE",
            "NEW_ARGUMENT",
            "UNCERTAINTY_STRENGTHENED",
        ):
            assert code in REASON_CODES
            assert code in payload["definitions"]
        assert payload["bible_specific"] is False
        assert payload["historical_expectations"]["4b22_p3"]["reason_codes"] == (
            "NEW_CAUSAL_LINK",
            "NEW_IMPLICATION",
        )


class TestPromptTransportSchema:
    def test_prompt_identity_and_role(self):
        bundle = prompt_bundle()
        assert bundle["version"] == "book-semantic-validator-1.0"
        assert "evidence-bounded semantic auditor" in bundle["system"]
        assert "theologian" in bundle["system"]
        assert "chain-of-thought" in bundle["system"].lower() or "hidden" in bundle[
            "system"
        ].lower()
        assert "CH016" not in bundle["system"]
        assert bundle["prompt_sha256"]

    def test_schema_is_openai_json_object_compatible(self):
        identity = schema_identity()
        assert identity["engine_mode"] == "json_object"
        assert identity["native_json_schema_response_format"] is False
        assert identity["openai_engine_compatible"] is True
        assert identity["raw_schema_bytes"] > 0


class TestAcceptanceAndCache:
    def test_questionable_blocks_cache(self):
        result = interpret_fixture(fixture_new_causal_link())
        assert result["result"]["verdict"] == "REVIEW"
        assert result["result"]["cache_acceptance"] is False
        assert result["result"]["review_required"] is True

    def test_unsupported_blocks_cache(self):
        result = interpret_fixture(fixture_invented_example())
        assert result["result"]["verdict"] == "FAIL"
        assert result["result"]["cache_acceptance"] is False

    def test_cache_invalidation(self):
        payload = cache_contract_payload()
        assert payload["cache_acceptance_requires_semantic_pass"] is True
        assert payload["4b22_candidate_production_cache"] == "NOT ACCEPTED"
        assert (
            semantic_pass_valid(
                candidate_sha256="a",
                recorded_candidate_sha256="a",
                evidence_sha256="b",
                recorded_evidence_sha256="b",
                contract_sha256="c",
                recorded_contract_sha256="c",
            )
            is True
        )
        assert (
            semantic_pass_valid(
                candidate_sha256="a",
                recorded_candidate_sha256="changed",
                evidence_sha256="b",
                recorded_evidence_sha256="b",
                contract_sha256="c",
                recorded_contract_sha256="c",
            )
            is False
        )


class TestFakeAI:
    def test_supported_pass(self):
        result = interpret_fixture(fixture_supported())
        assert result["result"]["verdict"] == "PASS"
        assert result["result"]["cache_acceptance"] is True

    def test_new_causal_link(self):
        result = interpret_fixture(fixture_new_causal_link())
        codes = []
        for para in result["result"]["paragraph_results"]:
            codes.extend(para["reason_codes"])
            for claim in para["claim_results"]:
                codes.extend(claim["reason_codes"])
        assert "NEW_CAUSAL_LINK" in codes
        assert result["result"]["verdict"] in {"REVIEW", "FAIL"}

    def test_invented_example(self):
        result = interpret_fixture(fixture_invented_example())
        assert result["result"]["verdict"] == "FAIL"
        assert any(
            "INVENTED_EXAMPLE" in claim["reason_codes"]
            for para in result["result"]["paragraph_results"]
            for claim in para["claim_results"]
        )

    def test_reference_completion(self):
        result = interpret_fixture(fixture_reference_completion())
        codes = [
            code
            for para in result["result"]["paragraph_results"]
            for claim in para["claim_results"]
            for code in claim["reason_codes"]
        ]
        assert "REFERENCE_COMPLETION" in codes
        assert result["result"]["verdict"] in {"REVIEW", "FAIL"}

    def test_uncertainty_strengthened(self):
        result = interpret_fixture(fixture_uncertainty_strengthened())
        assert result["result"]["verdict"] == "FAIL"
        assert any(
            "UNCERTAINTY_STRENGTHENED" in claim["reason_codes"]
            for para in result["result"]["paragraph_results"]
            for claim in para["claim_results"]
        )

    def test_pure_connective(self):
        result = interpret_fixture(fixture_pure_connective())
        assert result["result"]["verdict"] == "PASS"
        assert result["result"]["paragraph_results"][0]["verdict"] in {
            "NON_SUBSTANTIVE",
            "SUPPORTED",
        }

    def test_unknown_handle_fails(self):
        result = interpret_fixture(fixture_unknown_handle())
        assert result["result"]["verdict"] == "FAIL"
        assert result["result"]["unknown_handles"]

    def test_missing_paragraph_fails(self):
        result = interpret_fixture(fixture_missing_paragraph())
        assert result["result"]["verdict"] == "FAIL"
        assert any("missing paragraph" in item for item in result["result"]["errors"])

    def test_determinism(self):
        first = interpret_fixture(fixture_supported())
        second = interpret_fixture(fixture_supported())
        assert first["canonical"] == second["canonical"]
        decoded = decode_transport(fixture_supported()["parsed"])
        again = decode_transport(fixture_supported()["parsed"])
        assert decoded == again

    def test_catalog_pass(self):
        catalog = run_fakeai_catalog()
        assert catalog["passed"] is True
        assert catalog["determinism"] is True
        assert catalog["count"] == len(all_fixtures())


class TestBenchmarkAndSufficiency:
    def test_historical_benchmark_frozen(self):
        from app.book_semantic_gate_4b23.identity import load_json, verify_canonical_inputs
        from app.book_semantic_gate_4b23.benchmark import (
            benchmark_manifest,
            build_historical_benchmark,
        )
        from app.book_semantic_gate_4b23.paths import (
            historical_4b22_dir,
            historical_4b2_dir,
        )

        identities = verify_canonical_inputs()
        assert identities["source_map_unchanged"] is True
        assert identities["editorial_plan_unchanged"] is True
        assert identities["clean_transcript_unchanged"] is True
        assert identities["candidate_4b2_unchanged"] is True
        assert identities["candidate_4b22_unchanged"] is True
        benchmark = build_historical_benchmark(
            candidate_4b2=load_json(
                historical_4b2_dir() / "chapter_CH016_candidate.json"
            ),
            candidate_4b22=load_json(
                historical_4b22_dir() / "chapter_CH016_candidate.json"
            ),
            raw_4b2=load_json(
                historical_4b2_dir() / "book_generator_4b2_raw_structured_response.json"
            ),
        )
        manifest = benchmark_manifest(benchmark)
        assert manifest["positive_count"] >= 5
        assert manifest["negative_count"] == 4
        assert manifest["p9b_included_as_semantic_pass_fail"] is False
        assert "INVENTED_EXAMPLE" in manifest["four_known_failure_types"]
        assert "REFERENCE_COMPLETION" in manifest["four_known_failure_types"]
        assert benchmark["original_candidates_modified"] is False
        assert benchmark["terra_called"] is False
        p3 = next(item for item in benchmark["cases"] if item["case_id"] == "4b22_p3_new_causal")
        assert "because it still works" in p3["text"]
        p8 = next(
            item
            for item in benchmark["cases"]
            if item["case_id"] == "4b22_p8_reference_completion"
        )
        assert "sting long since removed from death" in p8["text"]

    def test_sufficiency_and_no_repair(self):
        payload = sufficiency_assessment()
        assert payload["classification"] == "SUFFICIENT_WITH_SEMANTIC_GATE"
        assert payload["do_not_automatically_reject"] is True
        assert payload["sample_limitation"]["real_generations"] == 2
        assert payload["4b22_candidate_production_cache"] == "NOT ACCEPTED"


class TestOfflinePayload:
    def test_openai_payload_omits_temperature_and_thinking(self):
        from app.book_semantic_gate_4b23.evidence import build_gate_input
        from app.book_semantic_gate_4b23.payload import (
            build_gate_request,
            build_offline_openai_payload,
        )

        gate_input = build_gate_input(
            candidate={
                "chapter_id": "CH016",
                "title": "Death as Gain",
                "sections": [
                    {
                        "section_id": "SEC063",
                        "paragraphs": [
                            {
                                "provider_handle": "p1",
                                "kind": "connective",
                                "text": "The question remains.",
                                "evidence_handles": [],
                            }
                        ],
                    }
                ],
            },
            evidence={
                "chapter": {"id": "CH016", "t": "Death as Gain", "p": "purpose"},
                "sections": [{"id": "SEC063"}],
                "ideas": [],
                "examples": [],
                "references": [],
                "uncertainties": [],
                "src_text": [],
                "allowed": [],
            },
            language="en",
        )
        request = build_gate_request(gate_input)
        assert request.model == "gpt-5.6-terra"
        assert request.thinking_mode is None
        assert request.temperature is None
        assert request.stage == "book_validation"
        payload = build_offline_openai_payload(gate_input)
        assert "temperature" not in payload
        assert "thinking" not in payload
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["model"] == "gpt-5.6-terra"

    def test_deterministic_validator_must_pass_first(self):
        result = apply_acceptance(
            fixture_supported()["parsed"],
            required_handles=["p2"],
            paragraph_texts={"p2": fixture_supported()["texts"]["p2"]},
            deterministic_validator_pass=False,
        )
        assert result["verdict"] == "FAIL"
        assert result["cache_acceptance"] is False
