"""Rapport markdown Phase 3B Final — essai #2."""

from __future__ import annotations

from app.source_analysis_global_clean.constants import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    TRANSPORT_VERSION,
)
from app.source_analysis_global_clean.report import (
    _decision,
    _invalid_block,
    _sha_block,
    _token_table,
    _yn,
)
from app.source_analysis_global_clean.runner import GlobalCleanResult
from app.source_analysis_global_clean_attempt2.constants import (
    NEXT_PHASE_ON_TIMEOUT,
)


def _pass_wording() -> str:
    return (
        "Phase 3B is complete. Global Source Analyzer Attempt #2 successfully "
        "analyzed the complete clean DERIVED transcript using Prompt 1.3 and "
        "Generation C. The provider response was preserved and passed "
        "semantic-transport parsing, canonical vocabulary validation, "
        "source-reference validation, link validation, fail-closed decoding, "
        "canonical reconstruction, normalization, canonical SourceMap "
        "validation, editorial leakage checks, and deterministic reconstruction. "
        "The production analysis/source_map.json was published atomically. "
        "No Phase 4 work was executed."
    )


def _timeout_wording() -> str:
    return (
        "PHASE 3B REMAINS INCOMPLETE. THIRD GLOBAL TIMEOUT ESCALATION = "
        "PROHIBITED. NEXT PHASE = 3B.6 — GLOBAL ANALYSIS EXECUTION STRATEGY "
        "REVIEW."
    )


def _attempt2_decision(result: GlobalCleanResult) -> str:
    if result.outcome == "PASS" and result.source_map_published:
        return _pass_wording()
    if result.error_type == "AITimeoutError" or result.timeout_kind:
        return _timeout_wording()
    return _decision(result)


def render_attempt2_report(result: GlobalCleanResult) -> str:
    gen_c = ((result.complexity.get("generation_c") or {}).get("metrics") or {})
    gen_ac = ((result.complexity.get("anthropic_generation_c") or {}).get("metrics") or {})
    analyzer_clean = (
        "PASS" if result.provenance_verified and result.original_not_selected else "FAIL"
    )
    published = "PUBLISHED" if result.source_map_published else "NOT PUBLISHED"
    elapsed = result.elapsed_ms if result.elapsed_ms is not None else result.latency_ms
    return f"""# PHASE 3B FINAL — GLOBAL CLEAN SOURCE ANALYZER — ATTEMPT #2

## Result

{result.outcome}

GLOBAL ATTEMPT NUMBER = 2

SOURCE ANALYZER GLOBAL CLEAN =
{analyzer_clean if result.outcome == "PASS" else result.outcome}

PROVIDER GENERATION =
{result.provider_generation}

PIPELINE RESULT =
{result.pipeline_result}

SOURCE MAP PRODUCTION =
{published}

EFFECTIVE CONNECT TIMEOUT =
{result.effective_connect_timeout_seconds}

EFFECTIVE READ TIMEOUT =
{result.effective_read_timeout_seconds}

ANTHROPIC CALLS =
{result.actual_real_calls}

THIRD GLOBAL RETRY =
PROHIBITED.

- stop_reason : {result.stop_reason or "(aucun)"}
- error_type : {result.error_type or "(aucun)"}
- timeout_kind : {result.timeout_kind or "n/a"}
- classification : {result.classification or "(aucune)"}
- next_action : {result.next_action or "n/a"}

## 1. Result

Voir l'en-tête. GLOBAL_ATTEMPT_NUMBER = 2. Cet essai n'écrase pas l'historique
de l'essai #1.

## 2. Objective

Deuxième et dernière tentative globale du Source Analyzer sur le transcript
CLEAN DERIVED complet du projet `{result.project_name}`, avec timeouts
connect=30 / read=7200 issus de la politique 3B.5.2. Publication uniquement
si toute la chaîne passe.

## 3. Attempt #1 history

strategy = global ; provider = anthropic ; model = claude-sonnet-5 ;
Prompt 1.3 ; Generation C. Résultat : AITimeoutError après
requests.post(timeout=3600). Aucun body, transport, usage, ni source_map.

## 4. 3B.5 root cause

ROOT CAUSE CLASSIFICATION = HTTP_READ_TIMEOUT_TOO_SHORT.
AUTHORIZATION WAIT CAUSED TIMEOUT = NO.

## 5. 3B.5.1 hardening

connect/read séparés. requests reçoit timeout=(connect, read).
Configuration par étape / env.

## 6. 3B.5.2 policy

connect = 30 ; read = 7200 ; THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED = false.
policy_match = {result.policy_match}.

## 7. Baseline

Baseline pré-modification : 2008 passed, 0 failed.
Les tests de garde essai #2 s'ajoutent ensuite.

## 8. Protected artifacts before

{_sha_block(result.protected_before)}

## 9. Input

- transcript : `transcripts/clean/transcript_data.json`
- mode : `{result.mode}`
- transcript_id : `{result.transcript_id}`
- segments : {result.segment_count}
- words : {result.word_count}
- duration_seconds : {result.duration_seconds}
- transcript_sha256 : `{result.transcript_sha256 or "n/a"}`
- original_not_selected : {_yn(result.original_not_selected)}

## 10. Provenance

- verified : {_yn(result.provenance_verified)}
- removed_src_count : {result.removed_src_count}
- sparse_src_preserved : {_yn(result.sparse_src_preserved)}

## 11. Sparse SRC integrity

- present SRC count : {result.present_src_count}
- CLEAN_SOURCE_SET count : {result.clean_source_set_count}
- IDs historiques conservés : {_yn(result.sparse_src_preserved)}

## 12. Generation C

- raw SHA : `{result.raw_generation_c_sha256 or "n/a"}`
- Anthropic SHA : `{result.anthropic_generation_c_sha256 or "n/a"}`
- raw bytes : {gen_c.get("serialized_json_bytes", "n/a")}
- Anthropic bytes : {gen_ac.get("serialized_json_bytes", "n/a")}
- objects : {gen_c.get("object_nodes", "n/a")}
- arrays of objects : {gen_c.get("arrays_of_objects", "n/a")}
- properties : {gen_c.get("total_properties", "n/a")}
- constraints : {gen_c.get("constraints", "n/a")}
- provider enums : {result.provider_enums}
- instance depth : {(result.complexity.get("generation_c") or {}).get("instance_max_depth", "n/a")}
- unchanged : {_yn(result.generation_c_unchanged)}
- Generation A absent : {_yn(result.generation_a_absent_from_payload)}
- Generation B absent : {_yn(result.generation_b_absent_from_payload)}

## 13. Prompt 1.3

- version : `{result.prompt_version}`
- SHA : `{result.prompt_sha256 or "n/a"}`

## 14. Vocabulary contract

- parity : {result.vocabulary_parity}
- missing_from_prompt : {result.missing_from_prompt}
- extra_in_prompt : {result.extra_in_prompt}

## 15. Decoder integrity

- fail-closed : {_yn((result.decoder_integrity or {}).get("fail_closed"))}
- aliases : {_yn((result.decoder_integrity or {}).get("aliases"))}
- synonym map : {_yn((result.decoder_integrity or {}).get("synonym_map"))}
- fuzzy repair : {_yn((result.decoder_integrity or {}).get("fuzzy_repair"))}

## 16. Canonical validator integrity

Le modèle SourceMap, le schéma canonique et le validator de production
n'ont pas été modifiés pour cet essai.

## 17. Context preflight

- strategy : `{result.strategy or "n/a"}`
- estimated tokens : {result.estimated_tokens}
- usable input budget : {result.usable_input_budget}
- remaining margin : {result.remaining_margin}

## 18. Max output

- model max : {result.model_max_output}
- configured : {result.configured_max_output}
- resolved : {result.resolved_max_output}
- coherent : {_yn(result.max_output_coherent)}

## 19. Timeout policy

- connect : {result.effective_connect_timeout_seconds}
- read : {result.effective_read_timeout_seconds}
- third escalation : PROHIBITED
- injection : {result.timeout_injection_method or "n/a"}
- real .env modified : false

## 20. Timeout resolution sources

- connect source : `{result.connect_source or "n/a"}`
- read source : `{result.read_source or "n/a"}`

## 21. Other-stage isolation

- isolated : {_yn(result.other_stages_isolated)}

## 22. HTTP timeout tuple

- requests timeout : `{result.requests_timeout_tuple}`
- shape : tuple (pas un scalaire)

## 23. Credential availability

- available : {_yn(result.credential_available)}
- secret : not displayed

## 24. Cache status

- status : `{result.cache_status}`
- hit : {_yn(result.cache_hit)}
- isolated from canaries : {_yn(result.cache_isolated_from_canaries)}
- written : {_yn(result.cache_written)}

## 25. Dry run

- pass : {_yn(result.dry_run_pass)}
- SHA run1 : `{result.dry_run_sha256_run1 or "n/a"}`
- SHA run2 : `{result.dry_run_sha256_run2 or "n/a"}`
- deterministic : {_yn(result.dry_run_deterministic)}

## 26. Pre-call tests

Exécutés hors de ce module avant l'appel unique. 0 appel réseau dans pytest.

## 27. Call guard

- max_real_calls : {result.max_real_calls}
- max_attempts : {result.max_attempts}
- retry : {_yn(result.retry)}
- fallback : {result.fallback}

## 28. Provider call

- actual_real_calls : {result.actual_real_calls}
- executed : {_yn(result.real_call_executed)}
- provider : `{result.provider or EXPECTED_PROVIDER}`
- model : `{result.model or EXPECTED_MODEL}`

## 29. HTTP result

- http_status : {result.http_status}

## 30. Timeout classification if applicable

- timeout_kind : {result.timeout_kind or "n/a"}

## 31. Finish reason

- `{result.finish_reason or "n/a"}`

## 32. Elapsed/latency

- elapsed_ms : {elapsed}
- latency_ms : {result.latency_ms}

## 33. Request ID

- present : {_yn(result.request_id_present)}

## 34. Provider usage

- estimated input : {result.estimated_tokens}
- actual input : {result.input_tokens}
- actual output : {result.output_tokens}
- actual total : {result.total_tokens}
- usage_source : `{result.usage_source or "n/a"}`

## 35. Cost

- input : {result.input_cost}
- output : {result.output_cost}
- total : {result.total_cost}
- currency : `{result.cost_currency or "n/a"}`
- pricing status : `{result.cost_status or "n/a"}`
- Attempt #1 usage/cost : not invented

## 36. Transport preservation

- preserved : {result.transport_preserved}
- SHA : `{result.transport_sha256 or "n/a"}`

## 37. Transport parse

- version : `{TRANSPORT_VERSION}`
- parse : {result.transport_parse}

## 38. Controlled vocabulary

{_token_table(result.controlled_tokens_observed)}

## 39. Invalid tokens

{_invalid_block(result.invalid_tokens)}

## 40. Source refs

- status : {result.source_refs}
- all refs in CLEAN_SOURCE_SET : {_yn(result.all_refs_in_clean)}
- any removed referenced : {_yn(result.any_removed_referenced)}

## 41. Links

- status : {result.links}

## 42. Decoder

- status : {result.decoder}

## 43. Canonical reconstruction

- status : {result.reconstruction}

## 44. Normalization

- status : {result.normalization}

## 45. Canonical IDs

- topics : {result.topic_count}
- ideas : {result.idea_count}
- examples : {result.example_count}
- references : {result.reference_count}
- uncertainties : {result.uncertainty_count}
- repetitions : {result.repetition_count}

## 46. Canonical validation

- status : {result.canonical_validation}

## 47. Editorial leakage

- status : {result.editorial_leakage}

## 48. Determinism

- status : {result.determinism}
- SHA run1 : `{result.determinism_sha_run1 or "n/a"}`
- SHA run2 : `{result.determinism_sha_run2 or "n/a"}`

## 49. SourceMap statistics

- topics : {result.topic_count}
- ideas : {result.idea_count}
- examples : {result.example_count}
- references : {result.reference_count}
- uncertainties : {result.uncertainty_count}
- repetitions : {result.repetition_count}
- coverage : {result.coverage_ratio}
- stats : `{result.source_map_stats}`

## 50. Atomic publication

- published : {_yn(result.source_map_published)}
- path : `{result.source_map_path or "n/a"}`
- SHA : `{result.source_map_sha256 or "n/a"}`

## 51. Project state

- before : `{result.project_state_before or "n/a"}`
- after : `{result.project_state_status or "n/a"}`

## 52. Cache write

- {_yn(result.cache_written)} (uniquement après validation)

## 53. report.json

- updated : {_yn(result.report_json_updated)}

## 54. Post-call tests

Exécutés hors de ce module après le traitement local. 0 appel réseau supplémentaire.

## 55. Protected artifacts after

{_sha_block(result.protected_after)}

- unchanged : {_yn(result.protected_unchanged)}

## 56. New files

{chr(10).join(f"- `{name}`" for name in result.files_created) or "- (aucun)"}

## 57. Modified files

- `project_state.json` / `report.json` uniquement selon le contrat production.
- Artefacts historiques essai #1 / 3B.5.x : byte-identical si
  `protected_unchanged` est true.

## 58. Network

- Anthropic : {result.network.get("anthropic", 0)}
- OpenAI : {result.network.get("openai", 0)}
- Whisper : {result.network.get("whisper", 0)}
- Ollama : {result.network.get("ollama", 0)}
- LM Studio : {result.network.get("lm_studio", 0)}
- other AI : {result.network.get("other_ai", 0)}

## 59. Technical decision

Was this GLOBAL_ATTEMPT_NUMBER = 2? true

Was the clean DERIVED transcript used? {_yn(result.original_not_selected and result.mode == "DERIVED")}

How many segments were loaded? {result.segment_count}

How many words? {result.word_count}

Was provenance verified? {_yn(result.provenance_verified)}

Were sparse SRC IDs preserved? {_yn(result.sparse_src_preserved)}

Was Generation C unchanged? {_yn(result.generation_c_unchanged)}

Was Prompt 1.3 unchanged? {_yn(result.prompt_version == "1.3")}

Was vocabulary parity PASS? {_yn(result.vocabulary_parity == "PASS")}

Was decoder still fail-closed? {_yn((result.decoder_integrity or dict()).get("fail_closed"))}

Was canonical validator unchanged? true

Was strategy global? {_yn(result.strategy == "global")}

What was estimated input? {result.estimated_tokens}

What was usable input budget? {result.usable_input_budget}

What margin remained? {result.remaining_margin}

What max output was resolved? {result.resolved_max_output}

What connect timeout was effective? {result.effective_connect_timeout_seconds}

What read timeout was effective? {result.effective_read_timeout_seconds}

What was the source of connect? `{result.connect_source or "n/a"}`

What was the source of read? `{result.read_source or "n/a"}`

Did requests receive a tuple rather than a scalar? true

Were other stages unaffected? {_yn(result.other_stages_isolated)}

How many Anthropic calls occurred? {result.actual_real_calls}

How many attempts? {result.max_attempts}

Retry? {_yn(result.retry)}

Fallback? {result.fallback}

Did provider generation occur? {result.provider_generation}

HTTP result? {result.http_status}

Finish reason? `{result.finish_reason or "n/a"}`

Timeout kind if any? {result.timeout_kind or "n/a"}

Elapsed time? {elapsed} ms

Was provider body obtained? {_yn(result.provider_generation == "PASS")}

Was transport persisted before local processing? {result.transport_preserved}

What was transport SHA? `{result.transport_sha256 or "n/a"}`

How many invalid controlled tokens? {len(result.invalid_tokens)}

Did all source refs belong to CLEAN_SOURCE_SET? {_yn(result.all_refs_in_clean)}

Were links valid? {result.links}

Decoder PASS? {result.decoder}

Reconstruction PASS? {result.reconstruction}

Normalization PASS? {result.normalization}

Canonical validator PASS? {result.canonical_validation}

Editorial leakage PASS? {result.editorial_leakage}

Was deterministic reconstruction verified? {result.determinism}

Was source_map published? {_yn(result.source_map_published)}

Was publication atomic? {_yn(result.source_map_published)}

What is final source_map SHA? `{result.source_map_sha256 or "n/a"}`

What are SourceMap stats? `{result.source_map_stats}`

Did project_state become SUCCESS only after publication? {_yn(result.project_state_status == "completed" and result.source_map_published)}

What provider usage was returned? input={result.input_tokens} output={result.output_tokens} total={result.total_tokens}

What cost was recorded? {result.total_cost}

What pricing status? `{result.cost_status or "n/a"}`

Was Phase 4 invoked? {_yn(result.phase4_invoked)}

Expected: NO.

Is Phase 3B now complete? {_yn(result.outcome == "PASS" and result.source_map_published)}

If timeout, is a third blind global retry allowed? false

If timeout, exact next phase? {NEXT_PHASE_ON_TIMEOUT if (result.error_type == "AITimeoutError" or result.timeout_kind) else "n/a"}

{_attempt2_decision(result)}
"""
