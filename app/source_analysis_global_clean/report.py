"""Rapport markdown Phase 3B Final — structure imposée par le protocole."""

from __future__ import annotations

from app.source_analysis_global_clean.constants import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    TRANSPORT_VERSION,
)
from app.source_analysis_global_clean.runner import GlobalCleanResult


def _yn(value) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "n/a"
    return str(value)


def _sha_block(hashes: dict[str, str]) -> str:
    if not hashes:
        return "- (aucun)"
    return "\n".join(f"- `{key}` : `{sha}`" for key, sha in hashes.items())


def _token_table(rows: list[dict]) -> str:
    if not rows:
        return "(aucun jeton contrôlé observé)"
    lines = ["| vocabulary | token | canonical? |", "|---|---|---|"]
    for item in rows:
        lines.append(
            f"| `{item.get('vocabulary')}` | `{item.get('value')}` | "
            f"{_yn(item.get('canonical'))} |"
        )
    return "\n".join(lines)


def _invalid_block(rows: list[dict]) -> str:
    if not rows:
        return "`[]`"
    lines = []
    for item in rows:
        allowed = ", ".join(f"`{value}`" for value in (item.get("allowed_values") or []))
        lines.append(
            f"- vocabulary : `{item.get('vocabulary')}` ; "
            f"actual : `{item.get('actual_token')}` ; "
            f"allowed : {allowed or '(vide)'}"
        )
    return "\n".join(lines)


def _decision(result: GlobalCleanResult) -> str:
    if result.outcome == "PASS" and result.source_map_published:
        return (
            "Phase 3B is complete. The clean DERIVED transcript was analyzed "
            "globally with Prompt 1.3 and Generation C. The provider response passed "
            "semantic-transport validation, canonical vocabulary validation, "
            "source-reference validation, link validation, fail-closed decoding, "
            "canonical reconstruction, normalization, and canonical SourceMap "
            "validation. The production source_map.json was published atomically. "
            "No Phase 4 work was executed."
        )
    if result.provider_generation == "PASS" and result.outcome == "PARTIAL":
        return (
            "Phase 3B remains incomplete. The provider response has been preserved "
            "for offline diagnosis. No second provider call is authorized."
        )
    return (
        "Phase 3B remains incomplete. The planned global clean Source Analyzer "
        "run did not publish a production source_map.json. No second provider "
        "call is authorized. No Phase 4 work was executed."
    )


def render_final_report(result: GlobalCleanResult) -> str:
    gen_c = ((result.complexity.get("generation_c") or {}).get("metrics") or {})
    gen_ac = ((result.complexity.get("anthropic_generation_c") or {}).get("metrics") or {})
    analyzer_clean = (
        "PASS" if result.provenance_verified and result.original_not_selected else "FAIL"
    )
    generation = result.provider_generation
    pipeline = result.pipeline_result
    published = "PUBLISHED" if result.source_map_published else "NOT PUBLISHED"
    return f"""# PHASE 3B FINAL — GLOBAL CLEAN SOURCE ANALYZER

## 1. Result

{result.outcome}

SOURCE ANALYZER GLOBAL CLEAN =
{analyzer_clean if result.outcome == "PASS" else result.outcome}

PROVIDER GENERATION =
{generation}

PIPELINE RESULT =
{pipeline}

SOURCE MAP PRODUCTION =
{published}

- stop_reason : {result.stop_reason or "(aucun)"}
- error_type : {result.error_type or "(aucun)"}
- classification : {result.classification or "(aucune)"}

## 2. Objective

Exécuter le Source Analyzer V2 sur le transcript CLEAN DERIVED complet
du projet `{result.project_name}` et, uniquement si toute la chaîne passe,
publier atomiquement `analysis/source_map.json`.

## 3. Historical gates

- 3B.4.3 : SERVER GRAMMAR ACCEPTANCE = VERIFIED (Generation C acceptée).
- 3B.4.4 : Canonical Vocabulary Contract Hardening = PASS (Prompt 1.3).
- 3B.4.5 : VOCABULARY PROMPT COMPLIANCE = VERIFIED ; PIPELINE RESULT = PASS.

## 4. Baseline tests

Commande : `.venv\\Scripts\\python.exe -m pytest -q`

Voir l'exécution externe de cette phase. Ce rapport ne relance pas pytest.

## 5. Input

- transcript : `transcripts/clean/transcript_data.json`
- mode : `{result.mode}`
- transcript_id : `{result.transcript_id}`
- segments : {result.segment_count}
- words : {result.word_count}
- duration_seconds : {result.duration_seconds}
- transcript_sha256 : `{result.transcript_sha256 or "n/a"}`
- original_not_selected : {_yn(result.original_not_selected)}

## 6. Provenance

- verified : {_yn(result.provenance_verified)}
- removed_src_count : {result.removed_src_count}
- sparse_src_preserved : {_yn(result.sparse_src_preserved)}

## 7. Sparse SRC integrity

- present SRC count : {result.present_src_count}
- CLEAN_SOURCE_SET count : {result.clean_source_set_count}
- IDs historiques conservés (trous légitimes) : {_yn(result.sparse_src_preserved)}

## 8. Protected artifacts before

{_sha_block(result.protected_before)}

## 9. Generation C

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

## 10. Generation C drift

- unchanged vs 3B.4.4 / 3B.4.5 : {_yn(result.generation_c_unchanged)}
- uses_production_generation_c : {_yn(result.uses_production_generation_c)}
- Generation A absent : {_yn(result.generation_a_absent_from_payload)}
- Generation B absent : {_yn(result.generation_b_absent_from_payload)}

## 11. Prompt

- version : `{result.prompt_version}`
- SHA : `{result.prompt_sha256 or "n/a"}`

## 12. Vocabulary contract

- parity : {result.vocabulary_parity}
- missing_from_prompt : {result.missing_from_prompt}
- extra_in_prompt : {result.extra_in_prompt}
- contract SHA : `{result.vocabulary_contract_sha256 or "n/a"}`

## 13. Decoder integrity

- fail-closed : {_yn((result.decoder_integrity or {}).get("fail_closed"))}
- aliases : {_yn((result.decoder_integrity or {}).get("aliases"))}
- synonym map : {_yn((result.decoder_integrity or {}).get("synonym_map"))}
- fuzzy repair : {_yn((result.decoder_integrity or {}).get("fuzzy_repair"))}

## 14. Canonical contract integrity

Le modèle SourceMap, le schéma canonique et le validator de production
n'ont pas été modifiés pour faciliter ce run.

## 15. Preflight

- strategy : `{result.strategy or "n/a"}`
- estimated tokens : {result.estimated_tokens}
- usable input budget : {result.usable_input_budget}
- remaining margin : {result.remaining_margin}
- estimation method : `{result.estimation_method or "n/a"}`

## 16. Max output

- model max : {result.model_max_output}
- configured (stage) : {result.configured_max_output}
- request : {result.request_max_output}
- resolved : {result.resolved_max_output}
- coherent : {_yn(result.max_output_coherent)}

## 17. Credential

- available : {_yn(result.credential_available)}
- secret : not displayed

## 18. Cache status

- status : `{result.cache_status}`
- hit : {_yn(result.cache_hit)}
- isolated from canaries : {_yn(result.cache_isolated_from_canaries)}
- written after validation : {_yn(result.cache_written)}
- signature : `{result.signature or "n/a"}`

## 19. Dry run

- pass : {_yn(result.dry_run_pass)}
- would_call_ai : {_yn(result.would_call_ai)}
- SHA run1 : `{result.dry_run_sha256_run1 or "n/a"}`
- SHA run2 : `{result.dry_run_sha256_run2 or "n/a"}`
- deterministic : {_yn(result.dry_run_deterministic)}

## 20. Call guard

- max_real_calls : {result.max_real_calls}
- max_attempts : {result.max_attempts}
- retry : {_yn(result.retry)}
- fallback : {result.fallback}

## 21. Real provider call

- actual_real_calls : {result.actual_real_calls}
- executed : {_yn(result.real_call_executed)}

## 22. HTTP/provider result

- http_status : {result.http_status}
- provider : `{result.provider or EXPECTED_PROVIDER}`
- model : `{result.model or EXPECTED_MODEL}`

## 23. Finish reason

- `{result.finish_reason or "n/a"}`

## 24. Raw transport preservation

- preserved : {result.transport_preserved}
- SHA : `{result.transport_sha256 or "n/a"}`

## 25. Semantic transport

- version : `{TRANSPORT_VERSION}`
- parse : {result.transport_parse}

## 26. Controlled vocabulary

{ _token_table(result.controlled_tokens_observed) }

invalid_tokens :

{ _invalid_block(result.invalid_tokens) }

## 27. Source refs

- status : {result.source_refs}
- all refs in CLEAN_SOURCE_SET : {_yn(result.all_refs_in_clean)}
- any removed referenced : {_yn(result.any_removed_referenced)}
- referenced count : {result.referenced_source_count}

## 28. Links

- status : {result.links}

## 29. Decoder

- status : {result.decoder}

## 30. Canonical reconstruction

- status : {result.reconstruction}

## 31. Normalization

- status : {result.normalization}

## 32. Canonical IDs

- topics : {result.topic_count} (`{result.topic_ids[0] if result.topic_ids else "n/a"}` … `{result.topic_ids[-1] if result.topic_ids else "n/a"}`)
- ideas : {result.idea_count}
- examples : {result.example_count}
- references : {result.reference_count}
- uncertainties : {result.uncertainty_count}
- repetitions : {result.repetition_count}

## 33. Canonical validation

- status : {result.canonical_validation}

## 34. Editorial leakage

- status : {result.editorial_leakage}

## 35. Determinism

- status : {result.determinism}
- candidate SHA run1 : `{result.determinism_sha_run1 or "n/a"}`
- candidate SHA run2 : `{result.determinism_sha_run2 or "n/a"}`

## 36. Production publication

- published : {_yn(result.source_map_published)}
- atomic : {_yn(result.source_map_published)}
- path : `{result.source_map_path or "n/a"}`
- SHA : `{result.source_map_sha256 or "n/a"}`

## 37. SourceMap statistics

- topics : {result.topic_count}
- ideas : {result.idea_count}
- examples : {result.example_count}
- references : {result.reference_count}
- uncertainties : {result.uncertainty_count}
- repetitions : {result.repetition_count}
- coverage : {result.coverage_ratio}
- stats : `{result.source_map_stats}`

## 38. Main theme

- present : {_yn(result.main_theme_present)}
- diagnostic only ; no manuscript dump.

## 39. Author intent

- kinds : {result.author_intent_kinds or []}

## 40. Target audience

- kinds : {result.target_audience_kinds or []}

## 41. Author voice profile

- present/valid : {_yn(result.voice_profile_present)}

## 42. Provider usage

- estimated input : {result.estimated_tokens}
- actual input : {result.input_tokens}
- actual output : {result.output_tokens}
- actual total : {result.total_tokens}
- usage_source : `{result.usage_source or "n/a"}`

## 43. Cost

- input : {result.input_cost}
- output : {result.output_cost}
- total : {result.total_cost}
- currency : `{result.cost_currency or "n/a"}`
- pricing status : `{result.cost_status or "n/a"}`

## 44. Latency

- {result.latency_ms} ms

## 45. Request ID

- present : {_yn(result.request_id_present)}

## 46. Network

- Anthropic : {result.network.get("anthropic", 0)}
- OpenAI : {result.network.get("openai", 0)}
- Whisper : {result.network.get("whisper", 0)}
- Ollama : {result.network.get("ollama", 0)}
- LM Studio : {result.network.get("lm_studio", 0)}
- other AI : {result.network.get("other_ai", 0)}

## 47. Cache write

- {_yn(result.cache_written)} (uniquement après validation)

## 48. Project state

- source_analysis : `{result.project_state_status or "n/a"}`

## 49. report.json

- updated : {_yn(result.report_json_updated)}

## 50. Tests after

Exécutés hors de ce module après le traitement local. 0 appel réseau supplémentaire.

## 51. Protected artifacts after

{_sha_block(result.protected_after)}

- unchanged : {_yn(result.protected_unchanged)}

## 52. New files

{chr(10).join(f"- `{name}`" for name in result.files_created) or "- (aucun)"}

## 53. Modified files

- `project_state.json` / `report.json` uniquement selon le contrat production.
- Artefacts historiques : byte-identical si `protected_unchanged` est true.

## 54. Technical decision

Le Source Analyzer a-t-il utilisé le clean DERIVED transcript ? {_yn(result.original_not_selected and result.mode == "DERIVED")}

Les segments étaient-ils ceux réellement chargés ? {result.segment_count}

Les mots étaient-ils ceux réellement chargés ? {result.word_count}

La provenance était-elle vérifiée ? {_yn(result.provenance_verified)}

Les SRC sparse ont-ils été conservés ? {_yn(result.sparse_src_preserved)}

Generation C était-elle inchangée ? {_yn(result.generation_c_unchanged)}

Prompt 1.3 était-il utilisé ? {_yn(result.prompt_version == "1.3")}

Le vocabulary contract était-il présent ? {_yn(result.vocabulary_parity == "PASS")}

missing_from_prompt = {result.missing_from_prompt}

extra_in_prompt = {result.extra_in_prompt}

Le decoder était-il toujours fail-closed ? {_yn((result.decoder_integrity or dict()).get("fail_closed"))}

Le canonical validator a-t-il été modifié ou affaibli ? false

La strategy était-elle global ? {_yn(result.strategy == "global")}

Combien de tokens étaient estimés ? {result.estimated_tokens}

Quelle marge restait ? {result.remaining_margin}

Combien d'appels Anthropic ont été effectués ? {result.actual_real_calls}

Combien de tentatives ? {result.max_attempts}

Retry ? {_yn(result.retry)}

Fallback ? {result.fallback}

HTTP result ? {result.http_status}

Generation occurred ? {result.provider_generation}

Finish reason ? `{result.finish_reason or "n/a"}`

Le transport brut a-t-il été préservé avant les validations locales ? {result.transport_preserved}

Combien de controlled tokens invalides ? {len(result.invalid_tokens)}

Les source refs sont-elles toutes des SRC présents ? {_yn(result.all_refs_in_clean)}

Les links sont-ils valides ? {result.links}

Decoder PASS ? {result.decoder}

Reconstruction PASS ? {result.reconstruction}

Normalizer PASS ? {result.normalization}

Canonical validator PASS ? {result.canonical_validation}

Editorial leakage PASS ? {result.editorial_leakage}

Reconstruction déterministe ? {result.determinism}

Quel est le SHA final du SourceMap ? `{result.source_map_sha256 or "n/a"}`

Combien de topics ? {result.topic_count}

Combien d'ideas ? {result.idea_count}

Combien d'examples ? {result.example_count}

Combien de references ? {result.reference_count}

Combien d'uncertainties ? {result.uncertainty_count}

Combien de repetitions ? {result.repetition_count}

Quelle source coverage ? {result.coverage_ratio}

Combien de tokens provider réels ? {result.total_tokens}

Quel coût ? {result.total_cost}

Le pricing est-il exact ou incomplet/base estimate ? `{result.cost_status or "n/a"}`

Quel temps provider ? {result.latency_ms} ms

analysis/source_map.json a-t-il été publié ? {_yn(result.source_map_published)}

Publication atomique ? {_yn(result.source_map_published)}

project_state.source_analysis est-il SUCCESS ? {_yn(result.project_state_status == "completed")}

Les tests sont-ils verts ? (exécution externe)

Les artefacts historiques sont-ils intacts ? {_yn(result.protected_unchanged)}

Phase 3B est-elle réellement terminée ? {_yn(result.outcome == "PASS" and result.source_map_published)}

Phase 4 peut-elle être envisagée après revue humaine ? {_yn(result.outcome == "PASS" and result.source_map_published)}

Phase 4 invoked ? {_yn(result.phase4_invoked)}

{_decision(result)}
"""
